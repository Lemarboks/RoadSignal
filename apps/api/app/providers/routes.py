from abc import ABC, abstractmethod

import httpx


class RouteProvider(ABC):
    @abstractmethod
    async def alternatives(self, origin: str, destination: str) -> list[dict]: ...


def _step(instruction: str, maneuver: str, street_name: str, distance_meters: float, duration_seconds: float, location: list[float]) -> dict:
    latitude, longitude = location
    return {
        "instruction": instruction,
        "maneuver": maneuver,
        "street_name": street_name,
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "location": {"latitude": latitude, "longitude": longitude},
    }


class MockCapeTownRouteProvider(RouteProvider):
    """Network-independent resilience provider used when open services are unavailable."""

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        return [
            {
                "id": "route-balanced", "name": "Balanced Route", "duration_minutes": 29, "distance_km": 18.7,
                "geometry": [[-33.9249, 18.4241], [-33.936, 18.443], [-33.951, 18.473], [-33.970, 18.505], [-33.981, 18.531]],
                "steps": [
                    _step("Head southeast on Buitengracht Street", "depart", "Buitengracht Street", 1400, 180, [-33.9249, 18.4241]),
                    _step("Turn left onto Somerset Road", "turn-left", "Somerset Road", 2600, 300, [-33.936, 18.443]),
                    _step("Continue onto the N1", "straight", "N1", 6800, 420, [-33.951, 18.473]),
                    _step("Take the N2 exit toward the airport", "slight-right", "N2", 5200, 360, [-33.970, 18.505]),
                    _step("Arrive at Cape Town International Airport", "arrive", "", 0, 0, [-33.981, 18.531]),
                ],
            },
            {
                "id": "route-safest", "name": "Safest Route", "duration_minutes": 33, "distance_km": 20.4,
                "geometry": [[-33.9249, 18.4241], [-33.918, 18.455], [-33.931, 18.489], [-33.955, 18.520], [-33.981, 18.531]],
                "steps": [
                    _step("Head northeast on Riebeek Street", "depart", "Riebeek Street", 1900, 240, [-33.9249, 18.4241]),
                    _step("Turn right onto Victoria Road", "turn-right", "Victoria Road", 3100, 300, [-33.918, 18.455]),
                    _step("Continue onto Liesbeek Parkway", "straight", "Liesbeek Parkway", 4200, 330, [-33.931, 18.489]),
                    _step("Turn slight left onto the N2", "slight-left", "N2", 6500, 420, [-33.955, 18.520]),
                    _step("Arrive at Cape Town International Airport", "arrive", "", 0, 0, [-33.981, 18.531]),
                ],
            },
            {
                "id": "route-fastest", "name": "Fastest Route", "duration_minutes": 24, "distance_km": 17.1,
                "geometry": [[-33.9249, 18.4241], [-33.941, 18.452], [-33.963, 18.478], [-33.976, 18.505], [-33.981, 18.531]],
                "steps": [
                    _step("Head south on Long Street", "depart", "Long Street", 1600, 180, [-33.9249, 18.4241]),
                    _step("Turn left onto the N2", "turn-left", "N2", 8300, 480, [-33.941, 18.452]),
                    _step("Continue straight on the N2", "straight", "N2", 4600, 300, [-33.963, 18.478]),
                    _step("Keep right toward the airport", "slight-right", "", 2900, 210, [-33.976, 18.505]),
                    _step("Arrive at Cape Town International Airport", "arrive", "", 0, 0, [-33.981, 18.531]),
                ],
            },
        ]


_OSRM_MODIFIER_TEXT = {
    "uturn": "Make a U-turn",
    "sharp right": "Turn sharp right",
    "right": "Turn right",
    "slight right": "Turn slightly right",
    "straight": "Continue straight",
    "slight left": "Turn slightly left",
    "left": "Turn left",
    "sharp left": "Turn sharp left",
}
_OSRM_MODIFIER_MANEUVER = {
    "uturn": "uturn",
    "sharp right": "sharp-right",
    "right": "turn-right",
    "slight right": "slight-right",
    "straight": "straight",
    "slight left": "slight-left",
    "left": "turn-left",
    "sharp left": "sharp-left",
}
_OSRM_ROUNDABOUT_TYPES = {"roundabout", "rotary", "roundabout turn", "exit rotary", "exit roundabout"}


def _osrm_step(step: dict) -> dict | None:
    maneuver = step.get("maneuver") or {}
    location = maneuver.get("location")
    if not isinstance(location, list) or len(location) != 2:
        return None
    longitude, latitude = location
    name = step.get("ref") or step.get("name") or ""
    step_type = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    if step_type == "depart":
        instruction = f"Head toward {name}" if name else "Head toward your destination"
        code = "depart"
    elif step_type == "arrive":
        instruction = "Arrive at your destination"
        code = "arrive"
    elif step_type in _OSRM_ROUNDABOUT_TYPES:
        instruction = f"Take the roundabout onto {name}" if name else "Take the roundabout"
        code = "roundabout"
    else:
        base = _OSRM_MODIFIER_TEXT.get(modifier, "Continue")
        instruction = f"{base} onto {name}" if name else base
        code = _OSRM_MODIFIER_MANEUVER.get(modifier, "straight")
    return {
        "instruction": instruction,
        "maneuver": code,
        "street_name": name,
        "distance_meters": round(float(step.get("distance", 0)), 1),
        "duration_seconds": round(float(step.get("duration", 0)), 1),
        "location": {"latitude": latitude, "longitude": longitude},
    }


class OpenRouteProvider(RouteProvider):
    """Nominatim geocoding plus OSRM routing, both configurable for self-hosting."""

    def __init__(self, nominatim_url: str, osrm_url: str, timeout: float, user_agent: str):
        self.nominatim_url = nominatim_url.rstrip("/")
        self.osrm_url = osrm_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}

    async def _geocode(self, client: httpx.AsyncClient, query: str) -> tuple[float, float]:
        response = await client.get(
            f"{self.nominatim_url}/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "za"},
            headers=self.headers,
        )
        response.raise_for_status()
        matches = response.json()
        if not matches:
            raise ValueError(f"No location matched {query!r}")
        return float(matches[0]["lat"]), float(matches[0]["lon"])

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            origin_point = await self._geocode(client, origin)
            destination_point = await self._geocode(client, destination)
            coordinates = ";".join(
                f"{longitude},{latitude}" for latitude, longitude in (origin_point, destination_point)
            )
            response = await client.get(
                f"{self.osrm_url}/route/v1/driving/{coordinates}",
                params={"alternatives": 3, "steps": "true", "overview": "full", "geometries": "geojson"},
                headers=self.headers,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") != "Ok" or not body.get("routes"):
                raise ValueError(body.get("message", "No driveable route was found"))

        routes = []
        for index, route in enumerate(body["routes"][:3], start=1):
            names = []
            steps = []
            for leg in route.get("legs", []):
                for step in leg.get("steps", []):
                    name = step.get("ref") or step.get("name")
                    if name and name not in names:
                        names.append(name)
                    parsed = _osrm_step(step)
                    if parsed:
                        steps.append(parsed)
            routes.append({
                "id": f"open-route-{index}",
                "name": " / ".join(names[:2]) or f"Road Alternative {index}",
                "duration_minutes": max(1, round(route["duration"] / 60)),
                "distance_km": round(route["distance"] / 1000, 1),
                "geometry": [[latitude, longitude] for longitude, latitude in route["geometry"]["coordinates"]],
                "steps": steps,
            })
        if not routes:
            raise ValueError("OSRM returned no routes")
        return routes


class ResilientRouteProvider(RouteProvider):
    def __init__(self, primary: RouteProvider, fallback: RouteProvider):
        self.primary = primary
        self.fallback = fallback
        self.last_source = "open"

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        try:
            routes = await self.primary.alternatives(origin, destination)
            self.last_source = getattr(self.primary, "last_source", "open")
            return routes
        except (httpx.HTTPError, ValueError):
            routes = await self.fallback.alternatives(origin, destination)
            self.last_source = getattr(self.fallback, "last_source", "fallback")
            return routes
