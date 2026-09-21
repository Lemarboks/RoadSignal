import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from .config import settings
from .events import event_bus
from .providers.cameras import ResilientCameraProvider
from .providers.cctv import CctvCameraProvider
from .providers.itraffic import ITrafficCameraProvider
from .providers.crash_history import CrashHistoryProvider
from .providers.crime_precincts import CrimePrecinctProvider
from .providers.hazard_avoidance import HazardAvoidanceBuilder
from .providers.piper_voice import PiperVoiceProvider
from .providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider
from .providers.severe_events import SevereEventHazardProvider
from .providers.valhalla import ValhallaRouteProvider
from .providers.weather import OpenMeteoWeatherProvider
from .providers.wildfire import WildfireHazardProvider
from .repositories import repository, serialise
from .risk.engine import RiskIncident

route_analysis_cache: dict[tuple[str, str, str, str], tuple[float, dict]] = {}
route_analysis_lock = asyncio.Lock()

fallback_provider = MockCapeTownRouteProvider()
open_route_provider = ResilientRouteProvider(
    OpenRouteProvider(
        settings.nominatim_url,
        settings.osrm_url,
        settings.provider_timeout_seconds,
        settings.provider_user_agent,
    ),
    fallback_provider,
)
if settings.route_provider == "valhalla":
    route_provider = ResilientRouteProvider(
        ValhallaRouteProvider(
            settings.nominatim_url,
            settings.valhalla_url,
            settings.provider_timeout_seconds,
            settings.provider_user_agent,
        ),
        open_route_provider,
    )
else:
    route_provider = open_route_provider if settings.route_provider == "open" else fallback_provider
weather_provider = OpenMeteoWeatherProvider(settings.open_meteo_url, settings.provider_timeout_seconds)
hazard_bbox = (settings.hazard_bbox_south, settings.hazard_bbox_north, settings.hazard_bbox_west, settings.hazard_bbox_east)
wildfire_provider = WildfireHazardProvider(settings.provider_timeout_seconds, hazard_bbox)
severe_event_provider = SevereEventHazardProvider(settings.eonet_url, settings.provider_timeout_seconds, hazard_bbox)
# Prefer the data owner's official API; keep the keyless aggregator as a
# fallback for deployments without a developer key.
opencctv_provider = CctvCameraProvider(settings.cctv_timeout_seconds, hazard_bbox)
itraffic_provider = ITrafficCameraProvider(
    settings.itraffic_api_key, hazard_bbox, settings.cctv_timeout_seconds
)
cctv_provider = ResilientCameraProvider(itraffic_provider, opencctv_provider)
crime_precinct_provider = CrimePrecinctProvider()
# Shares the crime layer's precinct polygons rather than carrying a second copy:
# same boundaries, same point-in-polygon code.
crash_history_provider = CrashHistoryProvider(crime_precinct_provider)
hazard_avoidance_builder = HazardAvoidanceBuilder(
    wildfire_provider,
    severe_event_provider,
    crime_precinct_provider,
    wildfire_radius_km=settings.hazard_avoid_wildfire_radius_km,
    severe_event_radius_km=settings.hazard_avoid_severe_event_radius_km,
    crime_percentile=settings.hazard_avoid_crime_percentile,
    circumference_budget_m=settings.hazard_avoid_circumference_budget_m,
)


piper_voice_provider = PiperVoiceProvider(
    settings.piper_binary, settings.piper_voice_model, settings.piper_timeout_seconds
)


def supports_hazard_avoidance() -> bool:
    """Only Valhalla can exclude areas during pathfinding; OSRM cannot."""
    provider = getattr(route_provider, "primary", route_provider)
    return settings.hazard_avoidance_enabled and hasattr(provider, "valhalla_url")


def clear_route_analysis_cache() -> None:
    route_analysis_cache.clear()


def publish(kind: str, payload: dict) -> None:
    event = {
        "id": str(uuid4()),
        "type": kind,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": serialise(payload),
    }
    event_bus.publish(event)
    repository.append_audit(kind, payload)


def active_risk_incidents() -> list[RiskIncident]:
    category = {
        "Robbery": "crime",
        "Hijacking attempt": "crime",
        "Accident": "accident",
        "Flooding": "weather",
        "Pothole": "road_condition",
        "Broken traffic light": "traffic",
        "Road closure": "traffic",
        "Protest": "community",
    }
    incidents = []
    for item in repository.list_incidents():
        if item["status"] != "active":
            continue
        occurred_at = item["occurred_at"]
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        incidents.append(
            RiskIncident(
                category.get(item["incident_type"], "community"),
                item["severity"],
                item["confidence"],
                occurred_at,
                item["location"]["latitude"],
                item["location"]["longitude"],
            )
        )
    return incidents
