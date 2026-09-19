import time

import httpx

# NASA FIRMS' pre-generated global rolling-24h files; no API key required.
# VIIRS (finer resolution) is tried first, MODIS as a fallback.
_FIRMS_SOURCES = [
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv",
]


def _parse_firms_csv(text: str, bbox: tuple[float, float, float, float]) -> list[dict]:
    """Parse FIRMS' CSV, keeping only rows inside bbox = (south, north, west, east)."""
    south, north, west, east = bbox
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return []
    header = lines[0].split(",")
    try:
        lat_index = header.index("latitude")
        lon_index = header.index("longitude")
        frp_index = header.index("frp")
        confidence_index = header.index("confidence")
        date_index = header.index("acq_date")
        time_index = header.index("acq_time")
    except ValueError:
        return []
    hotspots = []
    for line in lines[1:]:
        columns = line.split(",")
        if len(columns) <= max(lat_index, lon_index, frp_index, confidence_index, date_index, time_index):
            continue
        try:
            latitude = float(columns[lat_index])
            longitude = float(columns[lon_index])
        except ValueError:
            continue
        if not (south <= latitude <= north and west <= longitude <= east):
            continue
        try:
            frp = float(columns[frp_index])
        except ValueError:
            frp = 0.0
        hotspots.append({
            "latitude": latitude,
            "longitude": longitude,
            "frp": frp,
            "confidence": columns[confidence_index],
            "acquired_at": f"{columns[date_index]}T{columns[time_index].zfill(4)[:2]}:{columns[time_index].zfill(4)[2:]}:00Z",
        })
    return hotspots


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


# After a failure, retry this soon rather than sitting on it for the whole TTL.
_RETRY_AFTER_SECONDS = 120.0


def _describe(error: Exception) -> str:
    """A short, safe reason for the UI -- no upstream response bodies."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"source returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "source unreachable"
    return "source returned unexpected data"


class WildfireHazardProvider:
    """NASA FIRMS active-fire detections, scoped to a region, as a route hazard."""

    def __init__(self, timeout: float, bbox: tuple[float, float, float, float], cache_seconds: float = 1800):
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

    async def hotspots(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        hotspots: list[dict] = []
        # Zero active fires is the normal case for Cape Town, so "fetched
        # successfully and found none" must be distinguishable from "could not
        # reach FIRMS at all" -- otherwise a dead feed looks like good news.
        fetched = False
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for url in _FIRMS_SOURCES:
                try:
                    response = await client.get(url, headers={"User-Agent": "RoadSignal/1.0 (wildfire hazard layer)"})
                    response.raise_for_status()
                    hotspots = _parse_firms_csv(response.text, self.bbox)
                    fetched = True
                    break
                except (httpx.HTTPError, ValueError) as error:
                    last_error = error
                    continue
        if not fetched:
            self._reachable = False
            self._last_error = _describe(last_error) if last_error else "source unreachable"
            kept = self._cache[1] if self._cache else []
            self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, kept)
            return kept
        self._reachable = True
        self._last_error = None
        self._cache = (now, hotspots)
        return hotspots

    async def near_route(self, geometry: list[tuple[float, float]], radius_km: float = 15.0) -> list[dict]:
        if not geometry:
            return []
        hotspots = await self.hotspots()
        matches = []
        for hotspot in hotspots:
            point = (hotspot["latitude"], hotspot["longitude"])
            if any(_haversine_km(point, vertex) <= radius_km for vertex in geometry):
                matches.append(hotspot)
        return matches

    async def penalty(self, geometry: list[tuple[float, float]]) -> tuple[float, list[str]]:
        matches = await self.near_route(geometry)
        if not matches:
            return 0.0, []
        strongest = max(match["frp"] for match in matches)
        penalty = min(20.0, len(matches) * 2.5 + strongest * 0.04)
        return round(penalty, 1), ["Active wildfire nearby"]
