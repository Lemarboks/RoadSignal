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
