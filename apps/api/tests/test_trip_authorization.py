from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main
import app.services as services
from app.config import settings
from app.main import app


client = TestClient(app)


class ClearWeather:
    async def penalty(self, latitude: float, longitude: float):
        return 0.0, []


def register_driver(label: str) -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{label}-{uuid4().hex}@example.com",
            "name": label,
            "password": "Correct-Horse-Battery-2026",
        },
    ).json()


def test_drivers_cannot_read_or_mutate_another_drivers_trip():
    original_auth = settings.require_auth
    original_provider = services.route_provider
    original_weather = services.weather_provider
    settings.require_auth = True
    main.limiter._storage.reset()
    services.route_provider = services.fallback_provider
    services.weather_provider = ClearWeather()
    try:
        owner = register_driver("Trip Owner")
        stranger = register_driver("Other Driver")
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
        client.post(
            "/api/v1/routes/analyse",
            json={
                "origin": "Cape Town CBD",
                "destination": "Airport",
                "preference": "balanced",
                "departure_time": "2026-08-11T18:00:00Z",
                "vehicle_type": "car",
            },
        )
        trip = client.post("/api/v1/routes/route-balanced/start", headers=owner_headers).json()
        trip_path = f"/api/v1/trips/{trip['id']}"

        assert client.get(trip_path).status_code == 401
        assert client.get(trip_path, headers=stranger_headers).status_code == 403
        assert client.get(f"{trip_path}/alerts", headers=stranger_headers).status_code == 403
        assert client.post(f"{trip_path}/location", headers=stranger_headers, json={
            "location": {"latitude": -33.92, "longitude": 18.42},
        }).status_code == 403
        assert client.post(f"{trip_path}/end", headers=stranger_headers).status_code == 403
        assert client.get(trip_path, headers=owner_headers).status_code == 200
        assert client.post(f"{trip_path}/end", headers=owner_headers).status_code == 200
    finally:
        settings.require_auth = original_auth
        services.route_provider = original_provider
        services.weather_provider = original_weather
