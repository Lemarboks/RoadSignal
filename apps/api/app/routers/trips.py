from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_when_enabled
from ..config import settings
from ..repositories import repository, serialise
from ..schemas import TripLocation
from ..services import publish

router = APIRouter(prefix="/api/v1", tags=["trips"])


def authorize_trip(trip: dict, principal) -> None:
    if not settings.require_auth:
        return
    owner = str(trip.get("user_id") or "")
    if principal and (owner == str(principal.id) or principal.role in {"administrator", "fleet_manager"}):
        return
    raise HTTPException(403, "This trip belongs to another account")


def owned_trip(trip_id: str, principal) -> dict:
    trip = repository.get_trip(trip_id)
    if not trip:
        raise HTTPException(404, "Trip not found")
    authorize_trip(trip, principal)
    return trip


@router.post("/routes/{route_id}/start")
def start_route(route_id: str, principal=Depends(require_when_enabled)):
    route = repository.get_route(route_id)
    if not route:
        raise HTTPException(404, "Route not found; analyse routes first")
    trip = repository.create_trip(route, principal.id if principal else None)
    publish("trip.started", trip)
    return serialise(trip)


@router.post("/trips/{trip_id}/location")
def update_location(trip_id: str, location: TripLocation, principal=Depends(require_when_enabled)):
    trip = owned_trip(trip_id, principal)
    repository.save_trip_location(trip_id, location.location.model_dump(), location.recorded_at)
    trip["progress"] = min(100, trip["progress"] + 5)
    repository.save_trip(trip)
    publish(
        "driver.location",
        {
            "trip_id": trip_id,
            "progress": trip["progress"],
            "latitude": location.location.latitude,
            "longitude": location.location.longitude,
        },
    )
    return serialise(trip)


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str, principal=Depends(require_when_enabled)):
    return serialise(owned_trip(trip_id, principal))


@router.get("/trips/{trip_id}/locations")
def trip_locations(trip_id: str, principal=Depends(require_when_enabled)):
    owned_trip(trip_id, principal)
    return {"items": serialise(repository.list_trip_locations(trip_id))}


@router.get("/trips/{trip_id}/alerts")
def trip_alerts(trip_id: str, principal=Depends(require_when_enabled)):
    return {"items": owned_trip(trip_id, principal).get("alerts", [])}


@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: str, principal=Depends(require_when_enabled)):
    trip = owned_trip(trip_id, principal)
    trip["status"] = "completed"
    repository.save_trip(trip)
    publish("trip.ended", trip)
    return serialise(trip)
