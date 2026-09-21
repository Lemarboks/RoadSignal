"""Open municipal service requests that affect driving conditions.

Unlike the crash dataset, which is six years of history shipped in the repo,
these are current conditions and are fetched at runtime: a street light
reported out last week is only useful while it is still out.

The City of Cape Town publishes 5.3 million service requests with a
completion date, so "still open" is knowable rather than guessed. Three
categories affect a driver:

  * Street lights out -- a dark road. Gated on darkness, because a broken
    light is a hazard at 21:00 and irrelevant at noon. This compounds with
    the vehicle-crime baseline the risk engine already carries.
  * Traffic controller without power -- a dead traffic light at a junction
    that normally has one, which is exactly the situation drivers handle
    worst.
  * Water leaking into the roadway -- standing water and undermined surface.

Road closures are deliberately absent. The City's "Closure of Roads" type
holds 39 records in total and none currently open, so it is not a usable
feed; claiming a closures layer from it would be a layer that never fires.

Positions arrive in the South African Lo system and are converted by
lo_projection. Roughly a quarter of the table stores 0,0 for "no location";
those records are dropped rather than plotted off the African coast.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from .lo_projection import field_pair_to_wgs84
from .solar import darkness_factor

SERVICE_URL = (
    "https://services6.arcgis.com/nyYfO9SxHU2ChQd9/arcgis/rest/services/"
    "Service_Requests_2023_until_20_May_2026/FeatureServer/0/query"
)
SOURCE = "City of Cape Town open service requests"

# Complaint types as the City spells them, grouped into what a driver cares
# about. Verified against the live distinct-value list; types with no open
# records (traffic sign damage, road potholes) are left out rather than
# queried for nothing.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "street_light": (
        "Street Lights - All Lights Out",
        "Street Lights - Single Light Out",
        "Street Lights - High Mast",
    ),
    "traffic_signal": ("Traffic Controller: No Power",),
    "road_water": ("WAT: Leak in Road/Pavement/Undergr",),
}
CATEGORY_LABELS = {
    "street_light": "Street light out",
    "traffic_signal": "Traffic light without power",
    "road_water": "Water leak in roadway",
}
# Explicit plurals: these labels pluralise inside the phrase, not by adding an
# "s" at the end ("street lights out", not "street light outs").
CATEGORY_PLURALS = {
    "street_light": "street lights out",
    "traffic_signal": "traffic lights without power",
    "road_water": "water leaks in the roadway",
}
CATEGORY_SINGULARS = {
    "street_light": "street light out",
    "traffic_signal": "traffic light without power",
    "road_water": "water leak in the roadway",
}

_RETRY_AFTER_SECONDS = 300.0
_PAGE_SIZE = 1000
_MAX_PAGES = 5  # bounds a runtime fetch; the layer is context, not a census
_NEAR_ROUTE_KM = 0.25

# A dead traffic light at a junction is the sharpest of the three: drivers
# handle an unsignalled intersection badly. A single dark street light is
# mild on its own, which is why it is also scaled by darkness.
_PENALTY_PER_ITEM = {"traffic_signal": 3.0, "street_light": 0.6, "road_water": 1.2}
_PENALTY_CEILING = {"traffic_signal": 9.0, "street_light": 6.0, "road_water": 4.0}


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"source returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "source unreachable"
    return "source returned unexpected data"


class ServiceRequestProvider:
    """Open road-affecting service requests for the configured area."""

    source = SOURCE

    def __init__(
        self,
        bbox: tuple[float, float, float, float],
        timeout: float = 25.0,
        cache_seconds: float = 10_800,  # 3h: the City publishes daily at most
        window_days: int = 30,
    ):
        self.bbox = bbox
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self.window_days = window_days
        self._cache: tuple[float, list[dict]] | None = None
        self._reachable = True
        self._last_error: str | None = None

    @property
    def reachable(self) -> bool:
        return self._reachable

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _where(self) -> str:
        types = ", ".join(
            "'" + name.replace("'", "''") + "'"
            for names in CATEGORIES.values()
            for name in names
        )
        return (
            f"C3_Complaint_Type IN ({types}) "
            "AND Completed_Date IS NULL "
            "AND X_Y_Co_ordinate_1 <> 0 "
            f"AND Created_On_Date > CURRENT_TIMESTAMP - INTERVAL '{self.window_days}' DAY"
        )

    def _category_of(self, complaint: str) -> str | None:
        for category, names in CATEGORIES.items():
            if complaint in names:
                return category
        return None

    def _to_entry(self, attributes: dict) -> dict | None:
        position = field_pair_to_wgs84(
            attributes.get("X_Y_Co_ordinate_1"), attributes.get("X_Y_Co_ordinate_2")
        )
        if not position:
            return None
        latitude, longitude = position
        south, north, west, east = self.bbox
        if not (south <= latitude <= north and west <= longitude <= east):
            return None
        complaint = (attributes.get("C3_Complaint_Type") or "").strip()
        category = self._category_of(complaint)
        if not category:
            return None
        reported = attributes.get("Created_On_Date")
        reported_iso = None
        if reported:
            try:  # ArcGIS returns epoch milliseconds
                reported_iso = datetime.fromtimestamp(
                    float(reported) / 1000, tz=timezone.utc
                ).isoformat()
            except (TypeError, ValueError, OSError, OverflowError):
                reported_iso = None
        return {
            "id": str(attributes.get("Notification") or attributes.get("ObjectId") or ""),
            "category": category,
            "label": CATEGORY_LABELS[category],
            "complaint_type": complaint,
            "suburb": (attributes.get("Suburb") or "").strip().title() or None,
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "reported_at": reported_iso,
        }

    async def _fetch(self) -> list[dict]:
        entries: list[dict] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for page in range(_MAX_PAGES):
                response = await client.get(
                    SERVICE_URL,
                    params={
                        "where": self._where(),
                        "outFields": "Notification,C3_Complaint_Type,Suburb,"
                                     "X_Y_Co_ordinate_1,X_Y_Co_ordinate_2,Created_On_Date",
                        "resultOffset": page * _PAGE_SIZE,
                        "resultRecordCount": _PAGE_SIZE,
                        "f": "json",
                    },
                )
                response.raise_for_status()
                body = response.json()
                if "error" in body:
                    raise ValueError(body["error"])
                features = body.get("features", [])
                for feature in features:
                    entry = self._to_entry(feature.get("attributes", {}))
                    if entry:
                        entries.append(entry)
                if not body.get("exceededTransferLimit") or not features:
                    break
        return entries

    async def requests(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        try:
            entries = await self._fetch()
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as error:
            self._reachable = False
            self._last_error = _describe(error)
            # Keep the last good result and retry sooner than the full window.
            kept = self._cache[1] if self._cache else []
            self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, kept)
            return kept
        self._reachable = True
        self._last_error = None
        self._cache = (now, entries)
        return entries

    async def penalty(
        self, geometry: list[tuple[float, float]], when: datetime | None = None
    ) -> tuple[float, list[str]]:
        """Risk penalty and factors for requests sitting on this route."""
        entries = await self.requests()
        if not entries or not geometry:
            return 0.0, []
        # Sample the route rather than testing every vertex against every
        # request: a few hundred vertices times a few thousand points is
        # needless work for a 250m proximity test.
        step = max(1, len(geometry) // 60)
        sampled = geometry[::step]
        counts: dict[str, int] = {}
        for entry in entries:
            position = (entry["latitude"], entry["longitude"])
            if any(_haversine_km(point, position) <= _NEAR_ROUTE_KM for point in sampled):
                counts[entry["category"]] = counts.get(entry["category"], 0) + 1
        if not counts:
            return 0.0, []
        when = when or datetime.now(timezone.utc)
        midpoint = geometry[len(geometry) // 2]
        darkness = darkness_factor(midpoint[0], midpoint[1], when)
        penalty = 0.0
        factors: list[str] = []
        for category, count in sorted(counts.items(), key=lambda item: -item[1]):
            weight = _PENALTY_PER_ITEM[category] * count
            if category == "street_light":
                # A dark street light is a hazard only in the dark.
                weight *= darkness
                if darkness <= 0:
                    continue
            contribution = min(_PENALTY_CEILING[category], weight)
            if contribution <= 0:
                continue
            penalty += contribution
            noun = CATEGORY_PLURALS[category] if count > 1 else CATEGORY_SINGULARS[category]
            factors.append(f"{count} {noun} reported")
        return round(penalty, 1), factors

    async def layer(self) -> dict:
        """Map layer payload, with the honesty fields the other layers use."""
        entries = await self.requests()
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["category"]] = counts.get(entry["category"], 0) + 1
        return {
            "requests": entries,
            "count": len(entries),
            "by_category": counts,
            "labels": CATEGORY_LABELS,
            "window_days": self.window_days,
            "source": SOURCE,
            "status": "ok" if self.reachable else "unavailable",
            "detail": self.last_error,
        }
