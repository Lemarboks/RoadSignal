from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_critical_flow():
    response=client.post("/api/v1/routes/analyse",json={"origin":"Cape Town CBD","destination":"Airport","preference":"balanced","departure_time":"2026-07-17T12:00:00Z","vehicle_type":"car"})
    assert response.status_code==200
    routes=response.json()["routes"]; assert len(routes)==3
    balanced=next(r for r in routes if r["id"]=="route-balanced"); assert balanced["recommended"]
    trip=client.post("/api/v1/routes/route-balanced/start").json(); original=trip["safety_score"]
    incident=client.post("/api/v1/incidents",json={"incident_type":"Accident","severity":5,"description":"Test collision","location":{"latitude":-33.951,"longitude":18.473},"occurred_at":"2026-07-17T12:05:00Z"}).json()
    updated=client.get(f"/api/v1/trips/{trip['id']}").json(); assert updated["safety_score"] < original; assert updated["alerts"]
    assert client.post(f"/api/v1/incidents/{incident['id']}/confirm").status_code==200
    assert client.post(f"/api/v1/trips/{trip['id']}/end").json()["status"]=="completed"
