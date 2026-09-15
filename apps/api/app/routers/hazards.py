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
