from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..auth import require_roles_when_enabled
from ..repositories import repository, serialise

router = APIRouter(prefix="/api/v1", tags=["fleet"])

DRIVER_NAMES = [
    "Ayanda Ndlovu", "Liam Jacobs", "Thandi Mokoena", "Ethan Williams", "Naledi Dlamini",
    "Luke Daniels", "Zanele Khumalo", "Mia Smith", "Sibusiso Nkosi", "Noah Adams",
]


@router.get("/fleets/demo-fleet/drivers")
def drivers(principal=Depends(require_roles_when_enabled("administrator", "fleet_manager"))):
    return {
        "items": [
            {"id": f"driver-{index}", "name": name, "status": "en_route" if index < 3 else "available", "safety_score": 88 - index * 2}
            for index, name in enumerate(DRIVER_NAMES)
        ]
    }


@router.get("/fleets/demo-fleet/trips")
def fleet_trips(principal=Depends(require_roles_when_enabled("administrator", "fleet_manager"))):
    return {"items": serialise(repository.list_trips()), "completed_today": 20}


@router.get("/fleets/demo-fleet/incidents")
def fleet_incidents(principal=Depends(require_roles_when_enabled("administrator", "fleet_manager", "incident_moderator"))):
    items = repository.list_incidents()
    return {"items": serialise(items), "total": len(items)}


def _as_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value


@router.get("/fleets/demo-fleet/analytics")
def analytics(principal=Depends(require_roles_when_enabled("administrator", "fleet_manager"))):
    trips = repository.list_trips()
    active_trips = [trip for trip in trips if trip["status"] == "active"]
    active_driver_ids = {trip["user_id"] for trip in active_trips if trip.get("user_id")}
    today = datetime.now(timezone.utc).date()
    completed_today = sum(
        1 for trip in trips
        if trip["status"] == "completed" and _as_datetime(trip["started_at"]).date() == today
    )
    average_score = round(sum(trip["safety_score"] for trip in trips) / len(trips), 1) if trips else 0
    return {
        "active_drivers": len(active_driver_ids) or len(active_trips),
        "high_risk_drivers": sum(1 for trip in trips if trip["safety_score"] < 60),
        "average_safety_score": average_score,
        "active_incidents": sum(1 for incident in repository.list_incidents() if incident["status"] == "active"),
        "trips_completed_today": completed_today,
        "alerts": repository.list_audit(10),
        "risk_by_area": [{"area": "Cape Town CBD", "score": 82}, {"area": "Woodstock", "score": 71}, {"area": "Pinelands", "score": 88}, {"area": "Athlone", "score": 64}],
        "hourly_scores": [78, 81, 84, 86, 83, 79, 74, 69],
    }


@router.get("/audit-logs")
def audit_logs(principal=Depends(require_roles_when_enabled("administrator", "incident_moderator"))):
    return {"items": repository.list_audit(100)}
