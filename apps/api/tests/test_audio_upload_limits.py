import asyncio

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.middleware import BoundedAudioUploadMiddleware


def test_multipart_remains_blocked_on_non_audio_endpoints():
    response = TestClient(app).post("/api/v1/incidents", files={"file": ("x.wav", b"test", "audio/wav")})
    assert response.status_code == 415


def test_audio_upload_can_exceed_json_limit_but_requires_authentication():
    response = TestClient(app).post("/api/v1/assistant/transcribe", files={"file": ("x.wav", b"x" * 1_100_000, "audio/wav")})
    assert response.status_code == 401


def test_chunked_audio_is_bounded_before_parsing(monkeypatch):
    monkeypatch.setattr(settings, "ai_max_audio_bytes", 2)
    messages = []
    async def forbidden(scope, receive, send):
        raise AssertionError("Oversized audio reached application")
    chunks = iter([
        {"type": "http.request", "body": b"x" * 65536, "more_body": True},
        {"type": "http.request", "body": b"xxx", "more_body": False},
    ])
    async def receive():
        return next(chunks)
    async def send(message):
        messages.append(message)
    asyncio.run(BoundedAudioUploadMiddleware(forbidden)(
        {"type": "http", "path": "/api/v1/assistant/transcribe", "method": "POST"}, receive, send,
    ))
    assert messages[0]["status"] == 413
