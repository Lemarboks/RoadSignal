from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_roles_when_enabled, require_when_enabled
from ..incidents.confidence import ConfidenceEvidence, calculate_confidence
from ..repositories import repository, serialise
from ..risk.engine import haversine_km
from ..schemas import IncidentCreate
from ..services import publish

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("")
def incidents():
    items = repository.list_incidents()
    return {"items": serialise(items), "total": len(items)}


@router.get("/nearby")
def nearby(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=10, gt=0, le=500),
):
    items = [
        item for item in repository.list_incidents()
        if haversine_km(
            (latitude, longitude),
            (item["location"]["latitude"], item["location"]["longitude"]),
        ) <= radius_km
    ]
    return {"items": serialise(items), "total": len(items)}


@router.post("")
def create_incident(body: IncidentCreate, principal=Depends(require_when_enabled)):
    confidence, flags = calculate_confidence(
        ConfidenceEvidence(gps_distance_km=0 if not body.reporter_location else 0.2)
    )
    incident = {
        "id": str(uuid4()),
        "incident_type": body.incident_type,
        "severity": body.severity,
        "source_type": "anonymous" if body.anonymous else "community",
        "verification_status": "unverified",
        "confidence": confidence,
        "description": body.description,
        "occurred_at": body.occurred_at,
        "expires_at": body.occurred_at + timedelta(hours=6),
        "location": body.location.model_dump(),
        "confirmations": 0,
        "disputes": 0,
        "status": "active",
        "abuse_flags": flags,
    }
    repository.save_incident(incident)
    publish("incident.created", incident)
    for trip in repository.list_trips():
        if trip["status"] == "active" and body.severity >= 4:
            trip["safety_score"] = max(20, round(trip["safety_score"] - 18.5, 1))
            trip["alerts"].append("High-severity incident detected ahead. A safer alternative is available.")
            repository.save_trip(trip)
            publish("route.risk_changed", {"trip_id": trip["id"], "safety_score": trip["safety_score"], "reroute": "route-safest"})
    return serialise(incident)


def moderate(incident_id: str, action: str):
    incident = repository.get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    if action == "confirm":
        incident["confirmations"] += 1
    elif action == "dispute":
        incident["disputes"] += 1
    else:
        incident.update(status="resolved", verification_status="resolved")
    if action != "resolve":
        incident["confidence"], _ = calculate_confidence(
            ConfidenceEvidence(
                confirmations=incident["confirmations"],
                disputes=incident["disputes"],
                reporter_trust=0.5,
                account_age_days=180,
                previous_accuracy=0.7,
            )
        )
    repository.save_incident(incident)
    publish(f"incident.{action}", incident)
    return serialise(incident)


@router.post("/{incident_id}/confirm")
def confirm(incident_id: str, principal=Depends(require_when_enabled)):
    return moderate(incident_id, "confirm")


@router.post("/{incident_id}/dispute")
def dispute(incident_id: str, principal=Depends(require_when_enabled)):
    return moderate(incident_id, "dispute")


@router.post("/{incident_id}/resolve")
def resolve(incident_id: str, principal=Depends(require_roles_when_enabled("administrator", "incident_moderator"))):
    return moderate(incident_id, "resolve")
