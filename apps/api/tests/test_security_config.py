import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_production_rejects_demo_security_configuration():
    with pytest.raises(ValidationError):
        Settings(environment="production", storage_backend="memory", event_backend="memory", require_auth=False)


def test_production_accepts_hardened_configuration():
    configured = Settings(
        environment="production",
        storage_backend="mysql",
        event_backend="redis",
        require_auth=True,
        jwt_secret="a-secure-random-secret-with-more-than-32-characters",
        cors_origins="https://fleet.example.com",
        metrics_bearer_token="a-random-prometheus-scrape-token-over-32-chars",
    )
    assert configured.allowed_origins == ["https://fleet.example.com"]


def test_production_mode_protects_mutations_and_roles():
    original = settings.require_auth
    settings.require_auth = True
    try:
        assert client.post("/api/v1/incidents", json={
            "incident_type": "Accident", "severity": 3, "description": "Test",
            "location": {"latitude": -33.9, "longitude": 18.4},
        }).status_code == 401
        registration = client.post("/api/v1/auth/register", json={
            "email": "role-test@example.com", "password": "Correct-Horse-Role-2026", "name": "Role Test",
        }).json()
        headers = {"Authorization": f"Bearer {registration['access_token']}"}
        incident = client.post("/api/v1/incidents", headers=headers, json={
            "incident_type": "Accident", "severity": 3, "description": "Test",
            "location": {"latitude": -33.9, "longitude": 18.4},
        })
        assert incident.status_code == 200
        assert client.post(f"/api/v1/incidents/{incident.json()['id']}/resolve", headers=headers).status_code == 403
    finally:
        settings.require_auth = original
