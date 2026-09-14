"""Contract/limit tests do not download or load model weights."""
import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location("inference_server", Path(__file__).parents[1] / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
client = TestClient(server.app)


def test_readiness_does_not_claim_unloaded_weights_available(monkeypatch):
    monkeypatch.setitem(server.state, "model", None)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.post("/v1/embeddings", json={"input": ["Pothole"]}).status_code == 503


def test_inference_rejects_unbounded_text():
    assert client.post("/v1/embeddings", json={"input": ["x"] * 33}).status_code == 422
    assert client.post("/v1/embeddings", json={"input": ["x" * 4001]}).status_code == 422
    assert client.post("/rerank", json={"query": "accident", "documents": [" "], "top_n": 1}).status_code == 422


def test_worker_rejects_wrong_role_and_model(monkeypatch):
    monkeypatch.setitem(server.state, "model", object())
    assert client.post("/v1/embeddings", json={"model": "not-configured", "input": ["Pothole"]}).status_code == 400
    assert client.post("/rerank", json={"query": "Pothole", "documents": ["Pothole"]}).status_code == 404


def test_chunked_upload_limit_stops_before_model_or_multipart_parser(monkeypatch):
    monkeypatch.setattr(server, "MAX_AUDIO_BYTES", 2)
    called, messages = [], []
    async def inner(scope, receive, send):
        called.append(True)
    chunks = iter([
        {"type": "http.request", "body": b"a" * 65536, "more_body": True},
        {"type": "http.request", "body": b"bbb", "more_body": False},
    ])
    async def receive():
        return next(chunks)
    async def send(message):
        messages.append(message)
    asyncio.run(server.BodyLimit(inner)({"type": "http", "method": "POST"}, receive, send))
    assert not called
    assert messages[0]["status"] == 413
