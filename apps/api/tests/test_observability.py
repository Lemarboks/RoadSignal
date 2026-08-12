import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter


client = TestClient(app)


def test_request_id_is_bounded_and_metrics_use_route_templates():
    supplied = "portfolio-check-42"
    response = client.get("/api/v1/health?secret=must-not-be-a-label", headers={"X-Request-ID": supplied})
    assert response.headers["X-Request-ID"] == supplied

    metrics = client.get("/metrics/").text
    assert 'route="/api/v1/health"' in metrics
    assert "must-not-be-a-label" not in metrics


def test_invalid_request_id_is_replaced():
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad request\nforged"})
    assert response.headers["X-Request-ID"] != "bad request\nforged"
    assert len(response.headers["X-Request-ID"]) <= 64


def test_json_logs_include_operational_fields_without_sensitive_values():
    record = logging.LogRecord("saferoute", logging.INFO, "", 0, "http_request", (), None)
    record.request_id = "request-1"
    record.method = "GET"
    record.route = "/api/v1/auth/me"
    record.status = 401
    record.duration_ms = 2.5
    payload = json.loads(JsonFormatter().format(record))
    assert payload["route"] == "/api/v1/auth/me"
    assert payload["status"] == 401
    assert "authorization" not in payload
    assert "query" not in payload


def test_degraded_readiness_returns_service_unavailable(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "storage_backend", "mysql")
    monkeypatch.setattr(main, "database_ready", lambda: False)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"

def test_metrics_can_require_a_scrape_token(monkeypatch):
    from app.config import settings

    token = "test-prometheus-token-that-is-long-enough"
    monkeypatch.setattr(settings, "metrics_bearer_token", token)
    assert client.get("/metrics/").status_code == 401
    assert client.get("/metrics/", headers={"Authorization": f"Bearer {token}"}).status_code == 200