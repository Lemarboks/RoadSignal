"""Offline tests for authorization, bounds and truthful model proxy labels."""
import base64
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import Principal, current_principal
from app.config import settings
from app.main import app
from app.routers import monitoring_models as models

PREFIX = "/api/v1/monitoring"
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0ioAAAAASUVORK5CYII="


@pytest.fixture
def proxy(monkeypatch):
    monkeypatch.setattr(settings, "vision_base_url", "http://vision:8080")
    monkeypatch.setattr(settings, "verification_base_url", "http://verification:8080")
    monkeypatch.setattr(settings, "model_worker_token_file", "")
    monkeypatch.setattr(settings, "require_auth", False)
    calls = []
    result = {"status": "ready", "role": "vision", "source": "demo", "tracks": [], "counts": {},
              "frame_index": 0, "requires_review": False, "verified": True}

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if isinstance(result.get("error"), Exception):
                raise result["error"]
            return httpx.Response(result.get("status_code", 200), json=result,
                                  request=httpx.Request(method, url))

    monkeypatch.setattr(models.httpx, "AsyncClient", Client)
    app.dependency_overrides.pop(current_principal, None)
    yield TestClient(app), calls, result
    app.dependency_overrides.pop(current_principal, None)


def become(role="driver"):
    principal = Principal(uuid4(), "demo@example.com", "Demo", role)
    app.dependency_overrides[current_principal] = lambda: principal
    return principal


def frame(**changes):
    return {"session_id": "demo-camera", "frame_index": 0, "image_base64": PNG, "source": "demo", **changes}


def evidence(**changes):
    return {"claim": "The example road is closed", "evidence": [{"text": "A synthetic closure report",
            "source_url": "https://example.com/report"}], **changes}


def test_auth_is_required_even_when_global_auth_is_disabled(proxy):
    client, calls, _ = proxy
    assert client.get(PREFIX + "/vision/status").status_code == 401
    assert client.post(PREFIX + "/vision/frames", json=frame()).status_code == 401
    assert client.post(PREFIX + "/evidence/compare", json=evidence()).status_code == 401
    assert not calls


def test_status_checks_readiness_without_implying_accuracy(proxy):
    client, _, result = proxy
    become()
    body = client.get(PREFIX + "/vision/status").json()
    assert body["available"] is True and body["requires_review"] is True
    assert body["authorized_frames_allowed"] is False
    result["status_code"] = 503
    assert client.get(PREFIX + "/vision/status").json()["available"] is False


def test_user_sessions_are_scoped_and_source_cannot_be_upgraded(proxy):
    client, calls, _ = proxy
    first_user = become()
    body = client.post(PREFIX + "/vision/frames", json=frame()).json()
    assert body["source"] == "demo" and body["requires_review"] is True and "verified" not in body
    assert body["retained_images"] is False and body["session_id"] == "demo-camera"
    first_scope = calls[-1][2]["json"]["session_id"]
    assert first_scope == models.scoped_session(first_user, "demo-camera")
    become()
    assert client.post(PREFIX + "/vision/frames", json=frame()).status_code == 200
    assert calls[-1][2]["json"]["session_id"] != first_scope


@pytest.mark.parametrize("role,expected", [("driver", 403), ("fleet_manager", 403),
                                         ("administrator", 200), ("incident_moderator", 200)])
def test_authorized_frames_require_operator_role(proxy, role, expected):
    client, calls, _ = proxy
    become(role)
    response = client.post(PREFIX + "/vision/frames", json=frame(source="authorized", authorization_confirmed=True))
    assert response.status_code == expected
    if expected == 403:
        assert not calls


def test_real_frames_require_explicit_permission_and_reject_unknown_sources(proxy):
    client, calls, _ = proxy
    become("administrator")
    for changes in [{"source": "authorized"}, {"source": "live"}, {"source": "authorized", "authorization_confirmed": "true"}]:
        assert client.post(PREFIX + "/vision/frames", json=frame(**changes)).status_code == 422
    assert not calls


def test_image_limits_are_checked_before_forwarding_and_not_echoed(proxy):
    client, calls, _ = proxy
    become()
    for image in ["https://example.com/frame.jpg", "AAAA", base64.b64encode(b"x" * (models.MAX_IMAGE_BYTES + 1)).decode()]:
        response = client.post(PREFIX + "/vision/frames", json=frame(image_base64=image))
        assert response.status_code == 422
        assert len(response.text) < 250
    assert not calls


def test_chunked_payload_is_bounded_without_content_length(proxy):
    client, calls, _ = proxy
    become()
    chunks = iter([b" " * (models.MAX_FRAME_BODY // 2), b" " * (models.MAX_FRAME_BODY // 2 + 1)])
    response = client.post(PREFIX + "/vision/frames", content=chunks, headers={"Content-Type": "application/json"})
    assert response.status_code == 413 and not calls


def test_compare_is_operator_only_and_never_publishes(proxy):
    client, calls, result = proxy
    become()
    assert client.post(PREFIX + "/evidence/compare", json=evidence()).status_code == 403
    assert not calls
    become("incident_moderator")
    result.update(sources=[], warnings=[])
    response = client.post(PREFIX + "/evidence/compare", json=evidence())
    assert response.status_code == 200
    body = response.json()
    assert body["assessment"] == "textual_consistency_only" and body["requires_review"] is True
    assert body["incident_published"] is False and "verified" not in body
    assert calls[-1][1] == "http://verification:8080/verify"


def test_compare_rejects_unbounded_evidence_before_forwarding(proxy):
    client, calls, _ = proxy
    become("administrator")
    assert client.post(PREFIX + "/evidence/compare", json=evidence(claim="x" * 501)).status_code == 422
    assert client.post(PREFIX + "/evidence/compare", json=evidence(evidence=evidence()["evidence"] * 6)).status_code == 422
    assert not calls


@pytest.mark.parametrize("worker_status,api_status", [(429, 429), (409, 409), (413, 413), (422, 422), (500, 503), (302, 503)])
def test_errors_are_sanitized_and_redirects_not_followed(proxy, worker_status, api_status):
    client, _, result = proxy
    become()
    result.update(status_code=worker_status, detail="private-token-and-input")
    response = client.post(PREFIX + "/vision/frames", json=frame())
    assert response.status_code == api_status
    assert "private-token" not in response.text


def test_worker_timeout_is_unavailable_not_demo_fallback(proxy):
    client, _, result = proxy
    become()
    result["error"] = httpx.ReadTimeout("private-worker-address")
    response = client.post(PREFIX + "/vision/frames", json=frame())
    assert response.status_code == 503 and "tracks" not in response.json()


def test_delete_only_targets_callers_scoped_session(proxy):
    client, calls, _ = proxy
    principal = become()
    assert client.delete(PREFIX + "/vision/sessions/demo-camera").status_code == 200
    assert calls[-1][0] == "DELETE"
    assert calls[-1][1].endswith("/sessions/" + models.scoped_session(principal, "demo-camera"))
