from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.config import settings
from app.repositories import MySQLRepository

pytestmark = pytest.mark.skipif(settings.storage_backend != "mysql", reason="requires MySQL 8 spatial")


def test_mysql_repository_round_trip():
    assert settings.storage_backend == "mysql"
    repository = MySQLRepository()
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
    repository.save_trip_location(trip["id"], {"latitude": -33.9249, "longitude": 18.4241}, datetime.now(timezone.utc))
    repository.save_trip_location(trip["id"], {"latitude": -33.94, "longitude": 18.45}, datetime.now(timezone.utc))
    breadcrumbs = repository.list_trip_locations(trip["id"])
    assert len(breadcrumbs) == 2
    assert breadcrumbs[0]["latitude"] == -33.9249
    event = repository.append_audit("integration.verified", {"route_id": route["id"]})
    assert any(item["id"] == event["id"] for item in repository.list_audit())


def test_mysql_auth_session_round_trip():
    from app.auth import authenticate_user, create_refresh_token, register_user, rotate_refresh_token
    from app.database.session import session_factory

    with session_factory()() as db:
        email = f"mysql-{uuid4().hex}@example.com"
        user = register_user(email, "MySQL Integration", "Correct-Horse-MySQL-2026", "driver", db)
        assert authenticate_user(email, "Correct-Horse-MySQL-2026", db).id == user.id
        refresh = create_refresh_token(user, db)
        access, replacement, expires_in = rotate_refresh_token(refresh, db)
        assert access and replacement and expires_in > 0
