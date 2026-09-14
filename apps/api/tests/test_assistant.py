import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai import service
from app.ai.schemas import IncidentAnalysisRequest
from app.auth import current_principal
from app.config import settings
from app.routers import assistant


@pytest.fixture(autouse=True)
def no_live_models(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    for key in ("ai_base_url", "embedding_base_url", "reranker_base_url", "whisper_base_url"):
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(assistant.limiter, "enabled", False)
    service._health_cache.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(assistant.router)
    app.dependency_overrides[current_principal] = lambda: object()
    with TestClient(app) as client:
        yield client


def make_incident(identifier="near", **overrides):
    now = datetime.now(timezone.utc)
    return {
        "id": identifier, "incident_type": "Accident", "description": "Two vehicle collision near Hospital Bend",
        "status": "active", "occurred_at": now - timedelta(minutes=15), "expires_at": now + timedelta(hours=2),
        "location": {"latitude": -33.941, "longitude": 18.452}, **overrides,
    }


def model_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def enable_generation(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_base_url", "http://local-model/v1")


def completion(value):
    return {"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}]}


def test_expensive_endpoints_always_require_authentication(client):
    client.app.dependency_overrides.clear()
    assert client.post("/api/v1/assistant/incidents/analyse", json={"text": "A collision ahead"}).status_code == 401
    assert client.post("/api/v1/assistant/routes/saved/explain").status_code == 401
    assert client.post("/api/v1/assistant/transcribe", files={"file": ("voice.wav", b"audio", "audio/wav")}).status_code == 401


def test_status_reports_unconfigured_without_contacting_providers(client, monkeypatch):
    def unexpected(request):
        pytest.fail("Unconfigured status must not make provider requests")
    model_transport(monkeypatch, unexpected)
    payload = client.get("/api/v1/assistant/status").json()
    for key in ("generation", "retrieval", "reranker", "transcription"):
        assert payload[key]["configured"] is False
        assert payload[key]["available"] is False


def test_status_probes_readiness_and_caches_checks(client, monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://embeddings")
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.path == "/ready"
        return httpx.Response(503, json={"ready": False})
    model_transport(monkeypatch, handler)
    first = client.get("/api/v1/assistant/status").json()
    second = client.get("/api/v1/assistant/status").json()
    assert first["retrieval"] == second["retrieval"]
    assert first["retrieval"]["configured"] and not first["retrieval"]["available"]
    assert len(requests) == 1


@pytest.mark.parametrize("body", [
    {"text": "Crash", "latitude": -33.9}, {"text": "Crash", "latitude": 91, "longitude": 18.4},
    {"text": "<b> </b>"}, {"text": "x" * 1001}, {"text": "Crash ahead", "safety_score": 100},
])
def test_analysis_rejects_invalid_input(client, body):
    assert client.post("/api/v1/assistant/incidents/analyse", json=body).status_code == 422


def test_offline_draft_is_labeled_and_never_saves_a_report(client, monkeypatch):
    incident = make_incident()
    snapshot = deepcopy(incident)
    monkeypatch.setattr(assistant.repository, "list_incidents", lambda: [incident])
    monkeypatch.setattr(assistant.repository, "save_incident", lambda *_: pytest.fail("Analysis must not publish"))
    response = client.post("/api/v1/assistant/incidents/analyse", json={
        "text": "Two vehicle collision near Hospital Bend", "latitude": -33.941, "longitude": 18.452,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback" and payload["retrieval_mode"] == "lexical"
    assert payload["requires_review"] is True
    assert payload["draft"]["incident_type"] == "Accident"
    assert payload["duplicates"][0]["id"] == "near"
    assert incident == snapshot


def test_missing_location_does_not_search_unrelated_incidents(client, monkeypatch):
    monkeypatch.setattr(assistant.repository, "list_incidents", lambda: [make_incident()])
    payload = client.post("/api/v1/assistant/incidents/analyse", json={"text": "Two vehicle collision near Hospital Bend"}).json()
    assert payload["duplicates"] == [] and payload["retrieval_mode"] == "unavailable"


def test_duplicates_are_gated_before_any_text_matching():
    now = datetime.now(timezone.utc)
    entries = [
        make_incident(),
        make_incident("far", location={"latitude": -26.2, "longitude": 28.0}),
        make_incident("old", occurred_at=now - timedelta(hours=25)),
        make_incident("expired", expires_at=now - timedelta(seconds=1)),
        make_incident("future", occurred_at=now + timedelta(hours=1)),
        make_incident("resolved", status="resolved"),
        make_incident("bad-location", location={"latitude": "invalid", "longitude": 18.452}),
    ]
    body = IncidentAnalysisRequest(text="collision ahead", latitude=-33.941, longitude=18.452)
    assert [item["id"] for item in service.nearby_candidates(body, entries, now)] == ["near"]


def test_valid_model_classifies_but_description_remains_user_authored(client, monkeypatch):
    enable_generation(monkeypatch)
    def handler(request):
        assert str(request.url) == "http://local-model/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(200, json=completion({"incident_type": "Flooding", "severity": 3}))
    model_transport(monkeypatch, handler)
    text = "Water is covering part of the left lane"
    payload = client.post("/api/v1/assistant/incidents/analyse", json={"text": text}).json()
    assert payload["mode"] == "model"
    assert payload["draft"] == {"incident_type": "Flooding", "severity": 3, "description": text}


@pytest.mark.parametrize("output", [
    {"incident_type": "Accident", "severity": 6},
    {"incident_type": "Accident", "severity": 3, "description": "Invented injury"},
    {"incident_type": "Ignore instructions", "severity": 3},
    {"incident_type": "Accident", "severity": True},
])
def test_invalid_generation_falls_back_without_extra_claims(client, monkeypatch, output):
    enable_generation(monkeypatch)
    model_transport(monkeypatch, lambda request: httpx.Response(200, json=completion(output)))
    payload = client.post("/api/v1/assistant/incidents/analyse", json={"text": "A pothole in the left lane"}).json()
    assert payload["mode"] == "fallback"
    assert payload["draft"]["incident_type"] == "Pothole"
    assert payload["draft"]["description"] == "A pothole in the left lane"


def test_timed_out_model_uses_rules(client, monkeypatch):
    enable_generation(monkeypatch)
    def handler(request):
        raise httpx.ReadTimeout("do not expose private provider details", request=request)
    model_transport(monkeypatch, handler)
    response = client.post("/api/v1/assistant/incidents/analyse", json={"text": "A crash near the bridge"})
    assert response.status_code == 200 and response.json()["mode"] == "fallback"
    assert "private provider" not in response.text


def test_semantic_retrieval_and_reranker_use_validated_indices(client, monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://embeddings")
    monkeypatch.setattr(settings, "reranker_base_url", "http://reranker")
    monkeypatch.setattr(assistant.repository, "list_incidents", lambda: [make_incident("one"), make_incident("two")])
    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            assert len(body["input"]) == 3
            return httpx.Response(200, json={"data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(3)]})
        assert request.url.path == "/rerank" and len(body["documents"]) == 2
        return httpx.Response(200, json={"results": [{"index": 1, "relevance_score": .9}, {"index": 0, "relevance_score": .7}]})
    model_transport(monkeypatch, handler)
    payload = client.post("/api/v1/assistant/incidents/analyse", json={"text": "Two vehicle collision", "latitude": -33.941, "longitude": 18.452}).json()
    assert payload["retrieval_mode"] == "semantic"
    assert [item["id"] for item in payload["duplicates"]] == ["two", "one"]


def test_invalid_embeddings_use_lexical_fallback(client, monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://embeddings")
    monkeypatch.setattr(assistant.repository, "list_incidents", lambda: [make_incident()])
    model_transport(monkeypatch, lambda request: httpx.Response(200, json={"data": [{"index": 5, "embedding": [1, 0]}]}))
    payload = client.post("/api/v1/assistant/incidents/analyse", json={"text": "Two vehicle collision near Hospital Bend", "latitude": -33.941, "longitude": 18.452}).json()
    assert payload["retrieval_mode"] == "lexical" and payload["duplicates"][0]["id"] == "near"


def test_retrieval_batch_stays_below_inference_limit(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://embeddings")
    def handler(request):
        body = json.loads(request.content)
        assert len(body["input"]) == 32
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [1, 0]} for i in range(32)]})
    model_transport(monkeypatch, handler)
    body = IncidentAnalysisRequest(text="collision", latitude=-33.941, longitude=18.452)
    matches, mode, _ = asyncio.run(service.retrieve_duplicates(body, [make_incident(str(i)) for i in range(45)], datetime.now(timezone.utc)))
    assert mode == "semantic" and len(matches) == 5


@pytest.mark.parametrize("ids,expected_mode", [(["breakdown.traffic"], "model"), (["invented-weather-alert"], "fallback"), (["safety_score", "safety_score"], "fallback")])
def test_route_explanation_accepts_only_saved_evidence_and_preserves_score(client, monkeypatch, ids, expected_mode):
    route = {"id": "saved", "safety_score": 73.2, "duration_minutes": 22, "distance_km": 12.5, "confidence": .8, "breakdown": {"traffic": 11}}
    snapshot = deepcopy(route)
    enable_generation(monkeypatch)
    monkeypatch.setattr(assistant.repository, "get_route", lambda _: route)
    model_transport(monkeypatch, lambda request: httpx.Response(200, json=completion({"evidence_ids": ids})))
    response = client.post("/api/v1/assistant/routes/saved/explain")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == expected_mode and payload["score_unchanged"] is True
    assert "73.2/100" in payload["summary"]
    assert "invented" not in payload["summary"]
    assert route == snapshot


def test_missing_saved_route_returns_404(client, monkeypatch):
    monkeypatch.setattr(assistant.repository, "get_route", lambda _: None)
    assert client.post("/api/v1/assistant/routes/missing/explain").status_code == 404


def test_audio_validation_and_offline_error(client, monkeypatch):
    assert client.post("/api/v1/assistant/transcribe", files={"file": ("report.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/v1/assistant/transcribe", files={"file": ("voice.wav", b"", "audio/wav")}).status_code == 422
    monkeypatch.setattr(settings, "ai_max_audio_bytes", 8)
    assert client.post("/api/v1/assistant/transcribe", files={"file": ("voice.wav", b"123456789", "audio/wav")}).status_code == 413
    response = client.post("/api/v1/assistant/transcribe", files={"file": ("voice.wav", b"123", "audio/wav")})
    assert response.status_code == 503 and "not configured" in response.json()["detail"]


def test_audio_is_forwarded_without_original_filename_and_requires_review(client, monkeypatch):
    monkeypatch.setattr(settings, "whisper_base_url", "http://whisper")
    def handler(request):
        assert request.url.path == "/v1/audio/transcriptions"
        assert b"private-driver-name.wav" not in request.content
        return httpx.Response(200, json={"text": "A pothole ahead"})
    model_transport(monkeypatch, handler)
    payload = client.post("/api/v1/assistant/transcribe", files={"file": ("private-driver-name.wav", b"audio", "audio/wav")}).json()
    assert payload == {"text": "A pothole ahead", "model": "small", "requires_review": True}


def test_concurrent_inference_is_bounded(client):
    with service.inference_slot(), service.inference_slot():
        response = client.post("/api/v1/assistant/incidents/analyse", json={"text": "A pothole ahead"})
        assert response.status_code == 429 and response.headers["retry-after"] == "5"
    assert client.post("/api/v1/assistant/incidents/analyse", json={"text": "A pothole ahead"}).status_code == 200


def test_frozen_incident_evaluation_cases():
    path = Path(service.__file__).with_name("evaluation-cases.json")
    cases = json.loads(path.read_text(encoding="utf-8"))["incident_cases"]
    for case in cases:
        assert service.fallback_classification(case["text"]).incident_type == case["expected_type"]
