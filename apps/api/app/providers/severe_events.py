import time

import httpx

# Event categories that plausibly affect road conditions or passability.
# Excludes categories NASA EONET tracks that don't (volcanoes, sea/lake ice,
# water colour, manmade, drought) or that RoadSignal already covers elsewhere
# (wildfires, via the dedicated FIRMS-backed WildfireHazardProvider).
_ROAD_RELEVANT_CATEGORIES = {"floods", "landslides", "severeStorms", "dustHaze", "snow", "tempExtremes"}


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def _event_point(event: dict) -> tuple[float, float] | None:
    geometry = event.get("geometry") or []
    if not geometry:
        return None
    latest = geometry[-1]
    coordinates = latest.get("coordinates")
    if latest.get("type") != "Point" or not coordinates or len(coordinates) != 2:
        return None
    longitude, latitude = coordinates
    return latitude, longitude


# After a failure, retry this soon rather than sitting on it for the whole TTL.
_RETRY_AFTER_SECONDS = 120.0


def _describe(error: Exception) -> str:
    """A short, safe reason for the UI -- no upstream response bodies."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"source returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "source unreachable"
    return "source returned unexpected data"


class SevereEventHazardProvider:
    """NASA EONET open natural-hazard events, scoped to a region, as a route hazard."""

    def __init__(self, url: str, timeout: float, bbox: tuple[float, float, float, float], cache_seconds: float = 1800):
        self.url = url
        self.timeout = timeout
        self.bbox = bbox
        self.cache_seconds = cache_seconds
        self._cache: tuple[float, list[dict]] | None = None
        self._reachable = True
        self._last_error: str | None = None

    @property
    def reachable(self) -> bool:
        return self._reachable

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def events(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        south, north, west, east = self.bbox
        matches: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(
                    self.url,
                    params={"status": "open", "limit": 200},
                    headers={"User-Agent": "RoadSignal/1.0 (severe weather hazard layer)"},
                )
                response.raise_for_status()
                body = response.json()
            for event in body.get("events", []):
                categories = {category.get("id") for category in event.get("categories", [])}
                if not categories & _ROAD_RELEVANT_CATEGORIES:
                    continue
                point = _event_point(event)
                if not point:
                    continue
                latitude, longitude = point
                if not (south <= latitude <= north and west <= longitude <= east):
                    continue
                matches.append({
                    "id": event.get("id"),
                    "title": event.get("title"),
                    "category": next(iter(categories & _ROAD_RELEVANT_CATEGORIES)),
                    "latitude": latitude,
                    "longitude": longitude,
                })
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
            self._reachable = False
            self._last_error = _describe(error)
            # Keep any previously good result and retry soon, rather than
            # caching a blank layer for the full TTL.
            kept = self._cache[1] if self._cache else []
            self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, kept)
            return kept
        self._reachable = True
        self._last_error = None
        self._cache = (now, matches)
        return matches

    async def near_route(self, geometry: list[tuple[float, float]], radius_km: float = 50.0) -> list[dict]:
        if not geometry:
            return []
        events = await self.events()
        matches = []
        for event in events:
            point = (event["latitude"], event["longitude"])
            if any(_haversine_km(point, vertex) <= radius_km for vertex in geometry):
                matches.append(event)
        return matches

    async def penalty(self, geometry: list[tuple[float, float]]) -> tuple[float, list[str]]:
        matches = await self.near_route(geometry)
        if not matches:
            return 0.0, []
        factors = sorted({match["category"] for match in matches})
        label = {
            "floods": "Flooding nearby",
            "landslides": "Landslide risk nearby",
            "severeStorms": "Severe storm nearby",
            "dustHaze": "Dust/haze nearby",
            "snow": "Snow event nearby",
            "tempExtremes": "Extreme temperature nearby",
        }
        penalty = min(20.0, len(matches) * 5.0)
        return round(penalty, 1), [label.get(category, category) for category in factors]
