from fastapi.testclient import TestClient
from app.main import app
import app.main as main

class ClearWeather:
    async def penalty(self, latitude: float, longitude: float):
        return 0.0, []

main.provider = main.fallback_provider
main.weather_provider = ClearWeather()
client=TestClient(app)
def test_critical_flow():
    main.route_analysis_cache.clear()
    response=client.post("/api/v1/routes/analyse",json={"origin":"Cape Town CBD","destination":"Airport","preference":"balanced","departure_time":"2026-07-17T12:00:00Z","vehicle_type":"car"})
    assert response.status_code==200
    routes=response.json()["routes"]; assert len(routes)==3
    balanced=next(r for r in routes if r["id"]=="route-balanced"); assert balanced["recommended"]
    trip=client.post("/api/v1/routes/route-balanced/start").json(); original=trip["safety_score"]
    incident=client.post("/api/v1/incidents",json={"incident_type":"Accident","severity":5,"description":"Test collision","location":{"latitude":-33.951,"longitude":18.473},"occurred_at":"2026-07-17T12:05:00Z"}).json()
    updated=client.get(f"/api/v1/trips/{trip['id']}").json(); assert updated["safety_score"] < original; assert updated["alerts"]
    assert client.post(f"/api/v1/incidents/{incident['id']}/confirm").status_code==200
    assert client.post(f"/api/v1/trips/{trip['id']}/end").json()["status"]=="completed"

def test_route_analysis_cache_is_invalidated_by_new_incident():
    main.route_analysis_cache.clear()
    payload={"origin":"Cape Town CBD","destination":"Airport","preference":"balanced","departure_time":"2026-07-17T12:00:00Z","vehicle_type":"car"}
    assert client.post("/api/v1/routes/analyse",json=payload).status_code==200
    assert main.route_analysis_cache
    assert client.post("/api/v1/incidents",json={"incident_type":"Road closure","severity":4,"description":"Cache invalidation test","location":{"latitude":-33.951,"longitude":18.473}}).status_code==200
    assert not main.route_analysis_cache
