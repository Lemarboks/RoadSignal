from datetime import datetime, timezone
from uuid import uuid4

from .config import settings
from .events import event_bus
from .providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider
from .providers.weather import OpenMeteoWeatherProvider
from .repositories import repository, serialise
from .risk.engine import RiskIncident

fallback_provider = MockCapeTownRouteProvider()
route_provider = (
    ResilientRouteProvider(
        OpenRouteProvider(
            settings.nominatim_url,
            settings.osrm_url,
            settings.provider_timeout_seconds,
            settings.provider_user_agent,
        ),
        fallback_provider,
    )
    if settings.route_provider == "open"
    else fallback_provider
)
weather_provider = OpenMeteoWeatherProvider(settings.open_meteo_url, settings.provider_timeout_seconds)


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
