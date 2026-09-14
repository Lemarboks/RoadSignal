"""Offline contract tests: never download model weights or contact real feeds."""
import asyncio
import base64
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location("verification_server", Path(__file__).parents[1] / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
client = TestClient(server.app)


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(server, "ROLE", "verification")
    monkeypatch.setattr(server, "WORKER_TOKEN", "")
    monkeypatch.setitem(server.state, "model", object())
    server.sessions.clear()
    yield
    server.sessions.clear()


def evidence_payload():
    return {"claim": "Example road closed", "evidence": [{"text": "Example road closed", "source_url": "https://example.com/report"}]}


def frame_payload(**overrides):
    return {"session_id": "test", "frame_index": 0, "image_base64": "AAAA", "source": "demo", **overrides}


def mock_frames(monkeypatch):
    monkeypatch.setattr(server, "ROLE", "vision")
    monkeypatch.setattr(server, "decode_frame", lambda _: SimpleNamespace(width=100, height=50, close=lambda: None))
    monkeypatch.setattr(server, "vehicle_detections", lambda _: [])
    monkeypatch.setattr(server, "track_detections", lambda session, items: [])


def test_readiness_is_honest(monkeypatch):
    monkeypatch.setitem(server.state, "model", None)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.post("/verify", json=evidence_payload()).status_code == 503


def test_authentication_happens_before_parsing(monkeypatch):
    monkeypatch.setattr(server, "WORKER_TOKEN", "test-secret")
    assert client.post("/verify", content="not-json").status_code == 401
    assert client.post("/verify", content="not-json", headers={"X-Worker-Token": "test-secret"}).status_code == 422


def test_nli_result_never_claims_verification(monkeypatch):
    monkeypatch.setattr(server, "nli_scores", lambda *args: [{"scores": {"entailment": 0.99, "neutral": 0.005, "contradiction": 0.005}}])
    result = client.post("/verify", json=evidence_payload())
    assert result.status_code == 200
    body = result.json()
    assert body["requires_review"] is True
    assert body["assessment"] == "textual_consistency_only"
    assert "verified" not in body
    assert len(body["warnings"]) == 2


def test_verification_limits_and_provenance():
    payload = evidence_payload()
    for bad in [{**payload, "claim": " "}, {**payload, "claim": "x" * 501},
                {**payload, "evidence": payload["evidence"] * 6},
                {**payload, "evidence": [{"text": "x", "source_url": "file:///secret"}]},
                {**payload, "evidence": [{"text": "x", "source_url": "https://secret@example.com"}]},
                {**payload, "evidence": [{"text": "x", "source_url": "https://example.com", "observed_at": "2026-01-01T12:00:00"}]}]:
        assert client.post("/verify", json=bad).status_code == 422


def test_nli_premise_hypothesis_order_labels_and_truncation(monkeypatch):
    calls = []

    class Tokenizer:
        def encode(self, text, **kwargs):
            return [1]

        def __call__(self, premise, hypothesis, **kwargs):
            calls.append((premise, hypothesis, kwargs))
            return {"input_ids": list(range(600))}

    class Tensor:
        def softmax(self, **kwargs):
            return [self]

        def tolist(self):
            return [0.8, 0.15, 0.05]

    class Model:
        config = SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})

        def __call__(self, **kwargs):
            return SimpleNamespace(logits=Tensor())

    from contextlib import nullcontext
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setitem(server.state, "processor", Tokenizer())
    monkeypatch.setitem(server.state, "model", Model())
    evidence = [server.Evidence(text="Supplied passage", source_url="https://example.com")]
    result = server.nli_scores("The claim", evidence)
    assert calls[0][:2] == ("Supplied passage", "The claim")
    assert calls[1][2]["truncation"] == "only_first"
    assert result[0]["evidence_truncated"] is True
    assert result[0]["scores"]["entailment"] == 0.8


def test_wrong_role_busy_and_authorization(monkeypatch):
    assert client.post("/frames", json=frame_payload()).status_code == 404
    assert client.post("/frames", json=frame_payload(source="authorized")).status_code == 422
    server.inference_lock.acquire()
    try:
        assert client.post("/verify", json=evidence_payload()).status_code == 429
    finally:
        server.inference_lock.release()


def test_tracking_order_source_and_deletion(monkeypatch):
    mock_frames(monkeypatch)
    response = client.post("/frames", json=frame_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "demo" and body["retained_images"] is False
    assert body["requires_review"] is True and all(value == 0 for value in body["counts"].values())
    assert client.post("/frames", json=frame_payload()).status_code == 409
    assert client.post("/frames", json=frame_payload(frame_index=2)).status_code == 409
    assert client.post("/frames", json=frame_payload(frame_index=1, source="authorized", authorization_confirmed=True)).status_code == 409
    assert client.post("/frames", json=frame_payload(frame_index=1)).status_code == 200
    assert client.delete("/sessions/test").status_code == 200
    assert client.post("/frames", json=frame_payload()).status_code == 200


def test_tracking_capacity_and_idle_expiry(monkeypatch):
    mock_frames(monkeypatch)
    for index in range(server.MAX_SESSIONS):
        assert client.post("/frames", json=frame_payload(session_id=f"test-{index}")).status_code == 200
    assert client.post("/frames", json=frame_payload(session_id="too-many")).status_code == 429
    for session in server.sessions.values():
        session["last_seen"] -= server.SESSION_TTL + 1
    assert client.post("/frames", json=frame_payload(session_id="fresh")).status_code == 200
    assert list(server.sessions) == ["fresh"]


def test_frame_decoding_format_and_pixel_limits():
    Image = pytest.importorskip("PIL.Image")
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        server.decode_frame("https://example.com/frame.png")
    buffer = io.BytesIO()
    Image.new("RGB", (2050, 1)).save(buffer, format="PNG")
    with pytest.raises(HTTPException) as error:
        server.decode_frame(base64.b64encode(buffer.getvalue()).decode())
    assert error.value.status_code == 413
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="PNG")
    frame = server.decode_frame(base64.b64encode(buffer.getvalue()).decode())
    assert frame.size == (10, 10)
    frame.close()


def test_chunked_body_limit(monkeypatch):
    monkeypatch.setattr(server, "MAX_BODY_BYTES", 3)
    messages, called = [], []
    chunks = iter([{"type": "http.request", "body": b"aa", "more_body": True},
                   {"type": "http.request", "body": b"aa", "more_body": False}])

    async def inner(*args):
        called.append(True)

    async def receive():
        return next(chunks)

    async def send(message):
        messages.append(message)

    asyncio.run(server.RequestGuard(inner)({"type": "http", "method": "POST", "headers": []}, receive, send))
    assert not called and messages[0]["status"] == 413
