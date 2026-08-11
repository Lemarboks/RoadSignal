from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.config import settings
from app.repositories import PostgresRepository

pytestmark = pytest.mark.skipif(settings.storage_backend != "postgres", reason="requires PostGIS")


def test_postgis_repository_round_trip():
    assert settings.storage_backend == "postgres"
    repository = PostgresRepository()
    suffix = uuid4().hex[:8]
    incident = {
        "id": str(uuid4()), "incident_type": "Road closure", "severity": 3,
        "source_type": "integration-test", "verification_status": "verified", "confidence": 0.8,
        "description": "Migration-backed integration evidence", "occurred_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "location": {"latitude": -33.9249, "longitude": 18.4241},
        "confirmations": 1, "disputes": 0, "status": "active", "abuse_flags": [],
    }
    repository.save_incident(incident)
    stored_incident = repository.get_incident(incident["id"])
    assert stored_incident["location"] == {"latitude": -33.9249, "longitude": 18.4241}

    route = {
        "id": f"integration-{suffix}", "name": "Integration route", "duration_minutes": 10,
        "distance_km": 5.2, "safety_score": 82, "confidence": 0.8, "risk_level": "low",
        "recommended": True, "difference_from_fastest": 0,
        "breakdown": {"crime": 1, "accident": 1, "traffic": 1, "weather": 1, "road_condition": 1, "community": 1},
        "factors": ["Traffic"], "explanation": "Integration evidence", "segment_scores": [82, 83],
        "geometry": [{"latitude": -33.9249, "longitude": 18.4241}, {"latitude": -33.94, "longitude": 18.45}],
    }
    repository.save_route(route)
    assert repository.get_route(route["id"])["geometry"] == route["geometry"]
    trip = repository.create_trip(route)
    trip["progress"] = 25
    repository.save_trip(trip)
    assert repository.get_trip(trip["id"])["progress"] == 25
    event = repository.append_audit("integration.verified", {"route_id": route["id"]})
    assert any(item["id"] == event["id"] for item in repository.list_audit())
