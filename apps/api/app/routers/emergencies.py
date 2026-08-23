from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends

from ..auth import require_roles_when_enabled, require_when_enabled
from ..repositories import serialise
from ..schemas import EmergencyCreate
from ..services import publish

router = APIRouter(prefix="/api/v1/emergencies", tags=["emergencies"])


@router.post("")
def emergency(payload: EmergencyCreate, principal=Depends(require_when_enabled)):
    event = {
        "id": str(uuid4()),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "location": payload.location.model_dump(),
        "user_id": str(principal.id) if principal else None,
    }
    publish("emergency.created", event)
    return serialise(event)


@router.post("/{event_id}/cancel")
def cancel_emergency(event_id: str, principal=Depends(require_when_enabled)):
    publish("emergency.cancelled", {"id": event_id})
    return {"id": event_id, "status": "cancelled"}


@router.post("/{event_id}/resolve")
def resolve_emergency(event_id: str, principal=Depends(require_roles_when_enabled("administrator", "fleet_manager"))):
    publish("emergency.resolved", {"id": event_id})
    return {"id": event_id, "status": "resolved"}
