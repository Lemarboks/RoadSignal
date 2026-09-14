from fastapi import APIRouter, Query

from ..geo.cells import incident_cells
from ..repositories import repository


router = APIRouter(prefix="/api/v1/map", tags=["map"])


@router.get("/cells")
def cells(resolution: int = Query(default=7, ge=5, le=9)):
    return incident_cells(repository.list_incidents(), resolution)
