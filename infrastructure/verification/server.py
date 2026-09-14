"""Internal, CPU-only decision-support workers. Outputs never verify truth.

No source URLs are fetched. Uploaded frames are decoded in memory and discarded.
Tracking IDs are short-lived vehicle-box associations, not real-world identities.
"""
import base64
import binascii
import hmac
import io
import logging
import os
import threading
import time
import warnings
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

ROLE = os.getenv("MODEL_ROLE", "verification")
MODELS = {
    "verification": ("MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"),
    "vision": ("PekingU/rtdetr_r18vd", "ac77a11ff0170a41b771c03264987f8ce2b0d753"),
}
MODEL_ID, MODEL_REVISION = MODELS.get(ROLE, ("", ""))
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "")
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_BODY_BYTES = 3 * 1024 * 1024
MAX_PIXELS = 1920 * 1080
MAX_SESSIONS = 8
SESSION_TTL = 120
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck", "train"}
state = {"model": None, "processor": None, "error": False}
sessions = {}
inference_lock = threading.Lock()
logger = logging.getLogger("verification")


def load_model():
    try:
        import torch
        torch.set_num_threads(2)
        if ROLE == "verification":
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            processor = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False)
            model = AutoModelForSequenceClassification.from_pretrained(
                MODEL_ID, revision=MODEL_REVISION, trust_remote_code=False, use_safetensors=True,
            ).eval()
            if set(model.config.id2label.values()) != {"entailment", "neutral", "contradiction"}:
                raise ValueError("Unexpected NLI labels")
        else:
            from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
            processor = RTDetrImageProcessor.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
            model = RTDetrForObjectDetection.from_pretrained(
                MODEL_ID, revision=MODEL_REVISION, use_safetensors=True, disable_custom_kernels=True,
            ).eval()
            # Import at startup so /ready also certifies that tracking can run.
            import supervision  # noqa: F401
        state.update(model=model, processor=processor, error=False)
    except Exception as exc:
        state["error"] = True
        logger.error("Model load failed (%s); check model cache/network and restart.", type(exc).__name__)


@asynccontextmanager
async def lifespan(app):
    if ROLE not in MODELS:
        raise RuntimeError("MODEL_ROLE must be verification or vision")
    threading.Thread(target=load_model, daemon=True).start()
    stop_sweeper = threading.Event()

    def sweep_idle():
        while not stop_sweeper.wait(10):
            if inference_lock.acquire(blocking=False):
                try:
                    prune_sessions(time.monotonic())
                finally:
                    inference_lock.release()

    threading.Thread(target=sweep_idle, daemon=True).start()
    yield
    stop_sweeper.set()
    sessions.clear()


app = FastAPI(title="RoadSignal evidence and vehicle analysis", lifespan=lifespan)


class RequestGuard:
    """Authenticate before reading and cap actual bytes, including chunked bodies."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {"POST", "DELETE"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if WORKER_TOKEN and not hmac.compare_digest(
            headers.get(b"x-worker-token", b""), WORKER_TOKEN.encode(),
        ):
            return await JSONResponse({"detail": "Invalid worker credential"}, 401)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_BODY_BYTES:
                return await JSONResponse({"detail": "Request exceeds 3 MiB limit"}, 413)(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay, send)


app.add_middleware(RequestGuard)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=3000)
    source_url: AnyHttpUrl
    observed_at: datetime | None = None

    @field_validator("source_url")
    @classmethod
    def safe_source(cls, value):
        if len(str(value)) > 2048 or urlsplit(str(value)).username is not None:
            raise ValueError("Source URL must be bounded and contain no credentials")
        return value

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Observation time requires a timezone")
        return value


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    claim: str = Field(min_length=1, max_length=500)
    evidence: list[Evidence] = Field(min_length=1, max_length=5)


class FrameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    frame_index: int = Field(ge=0, lt=1800)
    image_base64: str = Field(min_length=4, max_length=2796204)
    source: Literal["demo", "authorized"]
    authorization_confirmed: bool = False
    frame_rate: int = Field(default=5, ge=1, le=30)

    @model_validator(mode="after")
    def require_authorization(self):
        if self.source == "authorized" and not self.authorization_confirmed:
            raise ValueError("Confirm permission to process this camera's frames")
        return self


@app.get("/health")
def health():
    return {"status": "running", "role": ROLE}


@app.get("/ready")
def ready():
    if state["model"] is None:
        return JSONResponse({"status": "error" if state["error"] else "loading", "role": ROLE}, 503)
    return {"status": "ready", "role": ROLE, "model": MODEL_ID, "revision": MODEL_REVISION}


def require_model(role):
    if ROLE != role:
        raise HTTPException(404, "Endpoint is not available for this worker role")
    if state["model"] is None:
        raise HTTPException(503, "Model is not ready")


def nli_scores(claim, evidence):
    import torch
    tokenizer, model = state["processor"], state["model"]
    if len(tokenizer.encode(claim, add_special_tokens=False)) > 192:
        raise HTTPException(422, "Claim exceeds 192 model tokens; shorten the claim")
    results = []
    for source in evidence:
        token_count = len(tokenizer(source.text, claim, add_special_tokens=True)["input_ids"])
        encoded = tokenizer(source.text, claim, truncation="only_first", max_length=512, return_tensors="pt")
        with torch.inference_mode():
            scores = model(**encoded).logits.softmax(dim=-1)[0].tolist()
        results.append({
            "source_url": str(source.source_url),
            "observed_at": source.observed_at.isoformat() if source.observed_at else None,
            "scores": {model.config.id2label[index]: round(score, 6) for index, score in enumerate(scores)},
            "evidence_truncated": token_count > 512,
        })
    return results


def verify_request(request):
    if not inference_lock.acquire(blocking=False):
        raise HTTPException(429, "Worker busy; retry later", headers={"Retry-After": "2"})
    try:
        return {
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "assessment": "textual_consistency_only",
            "sources": nli_scores(request.claim, request.evidence),
            "requires_review": True,
            "warnings": [
                "NLI scores measure agreement with supplied text, not factual truth or source reliability.",
                "Sources, independence, timestamps and location still require operator verification.",
            ],
        }
    finally:
        inference_lock.release()


@app.post("/verify")
async def verify(request: VerificationRequest):
    require_model("verification")
    return await run_in_threadpool(verify_request, request)


def decode_frame(value):
    from PIL import Image, UnidentifiedImageError
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Frame must be plain base64-encoded PNG or JPEG") from None
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Decoded frame exceeds 2 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as decoded:
                width, height = decoded.size
                if decoded.format not in {"PNG", "JPEG"} or getattr(decoded, "n_frames", 1) != 1:
                    raise HTTPException(422, "Only single-frame PNG or JPEG is supported")
                if width * height > MAX_PIXELS or max(width, height) > 2048:
                    raise HTTPException(413, "Frame exceeds 2,073,600 pixels or 2048 pixels per side")
                return decoded.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(422, "Frame could not be decoded safely") from None


def vehicle_detections(frame):
    import torch
    processor, model = state["processor"], state["model"]
    encoded = processor(images=frame, return_tensors="pt")
    with torch.inference_mode():
        outputs = model(**encoded)
    result = processor.post_process_object_detection(
        outputs, target_sizes=torch.tensor([[frame.height, frame.width]]), threshold=0.1,
    )[0]
    detections = []
    for score, label_id, box in zip(result["scores"], result["labels"], result["boxes"]):
        label = model.config.id2label[int(label_id)]
        if label not in VEHICLE_CLASSES:
            continue
        x1, y1, x2, y2 = [float(value) for value in box]
        bbox = [max(0, min(frame.width, x1)), max(0, min(frame.height, y1)),
                max(0, min(frame.width, x2)), max(0, min(frame.height, y2))]
        if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
            detections.append({"label": label, "score": float(score), "bbox": bbox})
    return sorted(detections, key=lambda item: item["score"], reverse=True)[:100]


def track_detections(session, detections):
    import numpy as np
    import supervision as sv
    tracked = []
    # Separate trackers per class prevent a car-to-truck classification change
    # from silently keeping the same track identity.
    for label in sorted(VEHICLE_CLASSES):
        tracker = session["trackers"].setdefault(label, sv.ByteTrack(
            frame_rate=session["frame_rate"], track_activation_threshold=0.35,
            lost_track_buffer=15, minimum_consecutive_frames=1,
        ))
        items = [item for item in detections if item["label"] == label]
        current = sv.Detections(
            xyxy=np.asarray([item["bbox"] for item in items], dtype=np.float32).reshape(-1, 4),
            confidence=np.asarray([item["score"] for item in items], dtype=np.float32),
            class_id=np.zeros(len(items), dtype=int),
        )
        result = tracker.update_with_detections(current)
        # Removed tracks are historical bookkeeping, not needed for association.
        tracker.removed_tracks = tracker.removed_tracks[-300:]
        for box, confidence, track_id in zip(result.xyxy, result.confidence, result.tracker_id):
            tracked.append({"track_id": f"{label}-{int(track_id)}", "label": label,
                            "confidence": round(float(confidence), 5),
                            "bbox": [round(float(value), 2) for value in box]})
    return tracked


def prune_sessions(now):
    for session_id in list(sessions):
        if now - sessions[session_id]["last_seen"] >= SESSION_TTL:
            del sessions[session_id]


def process_frame(request):
    if not inference_lock.acquire(blocking=False):
        raise HTTPException(429, "Worker busy; retry later", headers={"Retry-After": "2"})
    try:
        now = time.monotonic()
        prune_sessions(now)
        session = sessions.get(request.session_id)
        if session is not None:
            if request.frame_index != session["last_index"] + 1:
                raise HTTPException(409, "Frames must arrive once, in consecutive order")
            if request.source != session["source"] or request.frame_rate != session["frame_rate"]:
                raise HTTPException(409, "Source and frame rate cannot change within a session")
        else:
            if request.frame_index != 0:
                raise HTTPException(409, "New or expired sessions must start at frame 0")
            if len(sessions) >= MAX_SESSIONS:
                raise HTTPException(429, "Session capacity reached; delete a session or wait for expiry")
            session = {"last_index": -1, "last_seen": now, "source": request.source,
                       "frame_rate": request.frame_rate, "trackers": {}}
        frame = decode_frame(request.image_base64)
        try:
            detections = vehicle_detections(frame)
            tracked = track_detections(session, detections)
            size = {"width": frame.width, "height": frame.height}
        finally:
            frame.close()
        session.update(last_index=request.frame_index, last_seen=time.monotonic())
        sessions[request.session_id] = session
        return {
            "model": MODEL_ID, "revision": MODEL_REVISION, "tracker": "ByteTrack (supervision 0.27.0)",
            "session_id": request.session_id, "frame_index": request.frame_index,
            "source": request.source, "frame_size": size, "tracks": tracked,
            "counts": {label: sum(item["label"] == label for item in tracked) for label in sorted(VEHICLE_CLASSES)},
            "requires_review": True, "retained_images": False,
            "warnings": ["Per-frame tracked vehicle counts are model estimates, not measured traffic flow.",
                         "No identity, number-plate, speed, crash or incident verification is performed."],
        }
    finally:
        inference_lock.release()


@app.post("/frames")
async def frames(request: FrameRequest):
    require_model("vision")
    return await run_in_threadpool(process_frame, request)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    require_model("vision")
    with inference_lock:
        sessions.pop(session_id, None)
    return {"deleted": True}
