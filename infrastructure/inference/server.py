"""Small internal CPU workers for Qwen retrieval and Whisper transcription.

One model per container. Only /ready advertises loaded weights. No raw content
is written to disk, logged, or sent to a hosted inference API.
"""
import io
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

ROLE = os.getenv("MODEL_ROLE", "embedding")
DEFAULTS = {"embedding": "Qwen/Qwen3-Embedding-0.6B", "reranker": "Qwen/Qwen3-Reranker-0.6B", "whisper": "small"}
MODEL_ID = os.getenv("MODEL_ID", DEFAULTS.get(ROLE, ""))
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 90
state = {"model": None, "tokenizer": None, "error": False}
inference_lock = threading.Lock()
logger = logging.getLogger("inference")


def load_model():
    try:
        if ROLE == "whisper":
            from faster_whisper import WhisperModel
            state["model"] = WhisperModel(MODEL_ID, device="cpu", compute_type="int8", cpu_threads=2)
        else:
            import torch
            from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer
            torch.set_num_threads(2)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, padding_side="left", trust_remote_code=False)
            factory = AutoModel if ROLE == "embedding" else AutoModelForCausalLM
            model = factory.from_pretrained(MODEL_ID, trust_remote_code=False, torch_dtype=torch.float32).eval()
            # Dynamic int8 linear layers keep CPU memory within a showcase budget.
            model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8, inplace=True)
            state.update(tokenizer=tokenizer, model=model)
    except Exception as exc:
        state["error"] = True
        logger.error("Model load failed (%s). Check model cache and network, then restart.", type(exc).__name__)


@asynccontextmanager
async def lifespan(app):
    if ROLE not in DEFAULTS:
        raise RuntimeError("MODEL_ROLE must be embedding, reranker, or whisper")
    threading.Thread(target=load_model, daemon=True).start()
    yield


app = FastAPI(title="RoadSignal internal inference", lifespan=lifespan)


class BodyLimit:
    """Enforce a real byte limit, including chunked multipart bodies."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_AUDIO_BYTES + 65536:
                return await JSONResponse({"detail": "Request exceeds the upload limit"}, 413)(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0
        async def replay():
            nonlocal index
            if index < len(chunks):
                item = chunks[index]
                index += 1
                return item
            return await receive()
        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.get("/health")
def health():
    return {"status": "running", "role": ROLE}


@app.get("/ready")
def ready():
    if state["model"] is None:
        return JSONResponse({"status": "failed" if state["error"] else "loading", "model": MODEL_ID}, 503)
    return {"status": "ready", "model": MODEL_ID, "role": ROLE}


def require_model(role, supplied):
    if ROLE != role:
        raise HTTPException(404, "This worker does not provide that capability")
    if supplied and supplied != MODEL_ID:
        raise HTTPException(400, "Requested model is not configured on this worker")
    if state["model"] is None:
        raise HTTPException(503, "Model is not ready; check /ready")


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = None
    input: list[str] = Field(min_length=1, max_length=32)

    @field_validator("input")
    @classmethod
    def bounded_text(cls, values):
        if any(not value.strip() or len(value) > 4000 for value in values):
            raise ValueError("Each input must contain 1–4000 characters")
        return values


@app.post("/v1/embeddings")
def embed(body: EmbeddingRequest):
    require_model("embedding", body.model)
    import torch
    import torch.nn.functional as F
    with inference_lock, torch.inference_mode():
        vectors = []
        for text in body.input:
            encoded = state["tokenizer"]([text], max_length=1024, truncation=True, padding=True, return_tensors="pt")
            hidden = state["model"](**encoded).last_hidden_state[:, -1]
            vectors.append(F.normalize(hidden, p=2, dim=1)[0].tolist())
    return {"object": "list", "model": MODEL_ID, "data": [
        {"object": "embedding", "index": i, "embedding": vector} for i, vector in enumerate(vectors)
    ]}


class RerankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = None
    query: str = Field(min_length=1, max_length=4000)
    documents: list[str] = Field(min_length=1, max_length=24)
    top_n: int = Field(default=5, ge=1, le=24)

    @field_validator("documents")
    @classmethod
    def bounded_documents(cls, values):
        return EmbeddingRequest.bounded_text(values)


@app.post("/rerank")
def rerank(body: RerankRequest):
    require_model("reranker", body.model)
    import torch
    tokenizer = state["tokenizer"]
    # Official Qwen yes/no ranking format, keeping the final answer prefix intact.
    prefix = "<|im_start|>system\nJudge whether the Document describes the same road incident as the Query. Answer only yes or no.<|im_end|>\n<|im_start|>user\n"
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    results = []
    with inference_lock, torch.inference_mode():
        for index, document in enumerate(body.documents):
            content = f"<Instruct>: Find reports describing the same incident, not merely the same incident type.\n<Query>: {body.query}\n<Document>: {document}"
            ids = tokenizer.encode(prefix, add_special_tokens=False) + tokenizer.encode(content, add_special_tokens=False)[:900] + tokenizer.encode(suffix, add_special_tokens=False)
            tensor = torch.tensor([ids])
            logits = state["model"](input_ids=tensor, attention_mask=torch.ones_like(tensor)).logits[0, -1]
            selected = logits[[tokenizer.convert_tokens_to_ids("no"), tokenizer.convert_tokens_to_ids("yes")]]
            score = torch.softmax(selected.float(), dim=0)[1].item()
            results.append({"index": index, "relevance_score": score})
    return {"model": MODEL_ID, "results": sorted(results, key=lambda row: row["relevance_score"], reverse=True)[:body.top_n]}


def decode_bounded_audio(data):
    import av
    import numpy as np
    frames, samples = [], 0
    try:
        with av.open(io.BytesIO(data)) as container:
            if not container.streams.audio:
                raise HTTPException(422, "The file has no audio track")
            stream = container.streams.audio[0]
            if stream.duration and stream.time_base and float(stream.duration * stream.time_base) > MAX_AUDIO_SECONDS:
                raise HTTPException(413, "Audio must be 90 seconds or shorter")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for decoded in container.decode(stream):
                for frame in resampler.resample(decoded):
                    samples += frame.samples
                    if samples > MAX_AUDIO_SECONDS * 16000:
                        raise HTTPException(413, "Audio must be 90 seconds or shorter")
                    frames.append(frame.to_ndarray().flatten())
            for frame in resampler.resample(None):
                samples += frame.samples
                if samples > MAX_AUDIO_SECONDS * 16000:
                    raise HTTPException(413, "Audio must be 90 seconds or shorter")
                frames.append(frame.to_ndarray().flatten())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Audio could not be decoded; use WAV, MP3, M4A, OGG, or WebM") from None
    if not frames:
        raise HTTPException(422, "The audio file is empty")
    return np.concatenate(frames).astype(np.float32) / 32768.0


def transcribe_audio(data, language):
    audio = decode_bounded_audio(data)
    with inference_lock:
        segments, info = state["model"].transcribe(audio, language=language or None, beam_size=1, vad_filter=True, condition_on_previous_text=False)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    return {"text": text, "language": info.language, "model": MODEL_ID, "duration": round(len(audio) / 16000, 2)}


@app.post("/v1/audio/transcriptions")
async def transcribe(file: UploadFile = File(...), model: str | None = Form(None), language: str | None = Form(None)):
    require_model("whisper", model)
    if language and (len(language) > 8 or not language.isalpha()):
        raise HTTPException(422, "Use a supported language code")
    try:
        data = await file.read(MAX_AUDIO_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio file exceeds 10 MB")
    return await run_in_threadpool(transcribe_audio, data, language)
