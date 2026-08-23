from fastapi import APIRouter, Response

from ..config import settings
from ..database.session import database_ready
from ..events import event_bus
from ..risk.evidence import risk_evidence

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health")
def health():
    return {"status": "healthy", "service": "roadsignal-api"}


@router.get("/risk/evidence")
def get_risk_evidence():
    return risk_evidence()


@router.get("/ready")
def ready(response: Response):
    database = database_ready()
    events = event_bus.ready()
    storage_ready = settings.storage_backend == "memory" or database
    events_ready = settings.event_backend == "memory" or events
    is_ready = storage_ready and events_ready
    if not is_ready:
        response.status_code = 503
    return {
        "status": "ready" if is_ready else "degraded",
        "storage": settings.storage_backend,
        "database": database,
        "events": settings.event_backend,
        "event_bus": events,
    }
