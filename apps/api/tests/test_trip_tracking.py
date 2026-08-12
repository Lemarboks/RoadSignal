from fastapi.testclient import TestClient

import app.main as main
from app.main import app


class ClearWeather:
    async def penalty(self, latitude: float, longitude: float):
        return 0.0, []


main.provider = main.fallback_provider
main.weather_provider = ClearWeather()
client = TestClient(app)


def start_trip() -> dict:
    client.post(
        "/api/v1/routes/analyse",
        json={
            "origin": "Cape Town CBD",
            "destination": "Airport",
            "preference": "balanced",
            "departure_time": "2026-08-12T12:00:00Z",
            "vehicle_type": "car",
        },
    )
    return client.post("/api/v1/routes/route-balanced/start").json()


def test_trip_locations_are_persisted_and_returned_in_order():
    trip = start_trip()
    trip_path = f"/api/v1/trips/{trip['id']}"

    first = client.post(f"{trip_path}/location", json={"location": {"latitude": -33.925, "longitude": 18.424}})
    assert first.status_code == 200
    second = client.post(f"{trip_path}/location", json={"location": {"latitude": -33.930, "longitude": 18.430}})
    assert second.status_code == 200

    locations = client.get(f"{trip_path}/locations").json()["items"]
    assert len(locations) == 2
    assert locations[0]["latitude"] == -33.925
    assert locations[0]["longitude"] == 18.424
    assert locations[1]["latitude"] == -33.930


def test_nearby_incidents_are_filtered_by_radius():
    close = client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "Pothole",
            "severity": 2,
            "description": "Right next to the query point",
            "location": {"latitude": -33.9000, "longitude": 18.4000},
            "occurred_at": "2026-08-12T12:00:00Z",
        },
    ).json()
    far = client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "Pothole",
            "severity": 2,
            "description": "Far away in Johannesburg",
            "location": {"latitude": -26.2041, "longitude": 28.0473},
            "occurred_at": "2026-08-12T12:00:00Z",
        },
    ).json()

    nearby = client.get("/api/v1/incidents/nearby", params={"latitude": -33.9000, "longitude": 18.4000, "radius_km": 5}).json()
    nearby_ids = {item["id"] for item in nearby["items"]}
    assert close["id"] in nearby_ids
    assert far["id"] not in nearby_ids


def test_fleet_analytics_reflects_actual_trips():
    before = client.get("/api/v1/fleets/demo-fleet/analytics").json()
    trip = start_trip()
    after_start = client.get("/api/v1/fleets/demo-fleet/analytics").json()
    assert after_start["active_drivers"] >= before["active_drivers"]

    client.post(f"/api/v1/trips/{trip['id']}/end")
    after_end = client.get("/api/v1/fleets/demo-fleet/analytics").json()
    assert after_end["trips_completed_today"] >= before["trips_completed_today"] + 1
