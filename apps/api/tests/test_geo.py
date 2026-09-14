from datetime import datetime, timedelta, timezone

import h3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.geo.cells import incident_cells
from app.routers import map as map_router


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def incident(**overrides):
    return {
        "id": "report-1",
        "status": "active",
        "occurred_at": NOW - timedelta(minutes=10),
        "expires_at": NOW + timedelta(hours=1),
        "location": {"latitude": -33.941, "longitude": 18.452},
        "severity": 4,
        "confidence": 0.8,
        "abuse_flags": ["demo_sample"],
        **overrides,
    }


def test_cells_group_current_incidents_in_real_h3_geojson_polygons():
    reports = [incident(), incident(id="report-2", severity=2, confidence=0.6)]
    result = incident_cells(reports, now=NOW)
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    feature = result["features"][0]
    properties = feature["properties"]
    assert h3.is_valid_cell(properties["cell_id"])
    assert h3.get_resolution(properties["cell_id"]) == 7
    assert properties["incident_count"] == 2
    assert properties["max_severity"] == 4
    assert properties["average_confidence"] == 0.7
    assert properties["provenance"] == "demo"
    assert properties["demo_incident_count"] == 2
    ring = feature["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert all(18 < longitude < 19 and -34 < latitude < -33 for longitude, latitude in ring)
    assert result["metadata"]["incident_count"] == 2


def test_cells_exclude_expired_resolved_future_and_invalid_reports():
    result = incident_cells([
        incident(),
        incident(expires_at=NOW),
        incident(status="resolved"),
        incident(occurred_at=NOW + timedelta(minutes=1)),
        incident(location={"latitude": float("nan"), "longitude": 18.4}),
        incident(confidence=1.2),
        incident(severity=2.5),
    ], now=NOW)
    assert result["metadata"]["incident_count"] == 1
    assert result["metadata"]["excluded_invalid"] == 3


def test_cells_handle_utc_database_timestamps_and_mixed_provenance():
    result = incident_cells([
        incident(occurred_at="2026-09-11T11:50:00", expires_at="2026-09-11T13:00:00"),
        incident(abuse_flags=["community_report"]),
    ], now=NOW)
    assert result["features"][0]["properties"]["provenance"] == "mixed"
    assert result["metadata"]["provenance"] == "mixed"
    unknown = incident_cells([incident(abuse_flags=[])], now=NOW)
    assert unknown["metadata"]["provenance"] == "unknown"


def test_empty_cells_do_not_imply_safety_or_invent_conditions():
    result = incident_cells([], now=NOW)
    assert result["features"] == []
    assert result["metadata"]["cell_count"] == 0
    assert result["metadata"]["incident_count"] == 0
    assert "weather" not in result["metadata"]
    assert "safety_score" not in result["metadata"]


def test_map_endpoint_validates_resolution_and_reads_repository(monkeypatch):
    application = FastAPI()
    application.include_router(map_router.router)
    client = TestClient(application)
    monkeypatch.setattr(map_router.repository, "list_incidents", lambda: [incident(
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )])
    response = client.get("/api/v1/map/cells?resolution=8")
    assert response.status_code == 200
    assert response.json()["metadata"]["resolution"] == 8
    assert response.json()["metadata"]["incident_count"] == 1
    assert client.get("/api/v1/map/cells?resolution=15").status_code == 422
    with pytest.raises(ValueError, match="resolution"):
        incident_cells([], resolution=2)
