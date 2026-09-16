from fastapi import APIRouter

from .. import services

router = APIRouter(prefix="/api/v1/hazards", tags=["hazards"])


@router.get("/wildfires")
async def wildfires():
    hotspots = await services.wildfire_provider.hotspots()
    return {"hotspots": hotspots, "source": "NASA FIRMS", "count": len(hotspots)}


@router.get("/severe-weather")
async def severe_weather():
    events = await services.severe_event_provider.events()
    return {"events": events, "source": "NASA EONET", "count": len(events)}


@router.get("/cameras")
async def cameras():
    entries = await services.cctv_provider.cameras()
    return {"cameras": entries, "source": "opencctv.org", "count": len(entries)}


@router.get("/avoidance-zones")
async def avoidance_zones(include_crime: bool = False):
    """Exclusion rings that hazard-aware routing would avoid.

    Lets an operator see exactly what would be excluded before enabling it,
    rather than discovering it through a surprising detour. Crime precincts
    are opt-in: excluding whole residential areas from routing is a much
    heavier intervention than avoiding an active fire.
    """
    polygons, reasons = await services.hazard_avoidance_builder.build(include_crime=include_crime)
    return {
        "polygons": polygons,
        "count": len(polygons),
        "reasons": reasons,
        "include_crime": include_crime,
        "supported_by_router": services.supports_hazard_avoidance(),
        "note": (
            "Roads intersecting these rings are avoided during pathfinding. "
            "Requires the Valhalla router; OSRM cannot exclude areas."
        ),
    }


@router.get("/crime-precincts")
def crime_precincts():
    """Reported vehicle-crime exposure per police precinct.

    Area-level reported crime over a fixed window, published by SAPS. It is
    decision support about roads, not a prediction and not a statement about
    the people who live there.
    """
    precincts = services.crime_precinct_provider.layer()
    return {
        "precincts": precincts,
        "count": len(precincts),
        **services.crime_precinct_provider.metadata,
    }
