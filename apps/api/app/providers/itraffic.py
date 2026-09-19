"""Traffic cameras from the official i-TRAFFIC developer API.

Why this exists: cameras previously came from opencctv.org, an aggregator that
re-published i-TRAFFIC's data. That aggregator put its API behind auth and now
returns 403, which killed the layer.

The obvious workaround -- scraping i-TRAFFIC's public map -- is not available
to us, and deliberately so. Their terms prohibit using "any robot, spider or
other similar kind of automatic program ... to monitor, copy, summarize, or
otherwise extract information from this website", and robots.txt disallows the
bulk data path (/list/getdata/). So instead this uses the route they actually
provide for exactly this purpose:

    GET https://www.i-traffic.co.za/api/getcameras?key={key}&format=json

which is documented at /developers/help as enabling developers "to create
mobile traffic apps for South Africa". Each record carries a Url documented as
"The url to fetch the camera image", plus Name, RoadwayName,
DirectionOfTravel, Latitude/Longitude and Disabled/Blocked flags. Going
through the sanctioned API also settles the republication question that
hotlinking from a scraped list would have raised.

Two constraints from their documentation are respected here:
  * A developer key is required, and there is no self-serve signup -- it is
    requested through their contact form. Without a key this provider reports
    itself unavailable rather than pretending to work.
  * Throttling is 10 calls per 60 seconds. One call per cache window is far
    inside that, and a failure is not retried tightly.
"""
from __future__ import annotations

import time

import httpx

API_URL = "https://www.i-traffic.co.za/api/getcameras"
SITE_BASE = "https://www.i-traffic.co.za"
_RETRY_AFTER_SECONDS = 300.0
_USER_AGENT = "RoadSignal/1.0 (+https://github.com/Lemarboks/RoadSignal) traffic camera layer"


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"source returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "source unreachable"
    return "source returned unexpected data"


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ITrafficCameraProvider:
    """Western Cape / national traffic cameras via the official i-TRAFFIC API."""

    source = "i-traffic.co.za"

    def __init__(
        self,
        api_key: str,
        bbox: tuple[float, float, float, float],
        timeout: float = 25.0,
        cache_seconds: float = 3600,
    ):
        self.api_key = (api_key or "").strip()
        self.bbox = bbox
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self._cache: tuple[float, list[dict]] | None = None
        self._reachable = True
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def reachable(self) -> bool:
        # An unconfigured provider is not "reachable"; callers should say so
        # rather than render an empty layer as though the region had no cameras.
        return self.configured and self._reachable

    @property
    def last_error(self) -> str | None:
        if not self.configured:
            return "no i-TRAFFIC developer key configured (set ITRAFFIC_API_KEY)"
        return self._last_error

    def _to_camera(self, record: dict) -> dict | None:
        if record.get("Disabled") or record.get("Blocked"):
            return None
        latitude, longitude = _number(record.get("Latitude")), _number(record.get("Longitude"))
        if latitude is None or longitude is None:
            return None
        south, north, west, east = self.bbox
        if not (south <= latitude <= north and west <= longitude <= east):
            return None
        url = (record.get("Url") or "").strip()
        if not url:
            return None
        # Documented as "the url to fetch the camera image", but the published
        # sample is placeholder text so the form is not guaranteed absolute.
        # The web client drops this straight into an <img src>, where a bare
        # path would silently fail to load.
        if not url.lower().startswith(("http://", "https://")):
            url = f"{SITE_BASE}/{url.lstrip('/')}"
        identifier = str(record.get("ID") or "").strip()
        name = (record.get("Name") or "").strip() or identifier
        roadway = (record.get("RoadwayName") or "").strip()
        direction = (record.get("DirectionOfTravel") or "").strip()
        # Roadway and direction are the useful part of a camera's identity for a
        # driver ("N2 Eastbound"), so fold them into the label when present.
        detail = " ".join(part for part in (roadway, direction) if part and part != "None")
        return {
            "id": f"itraffic-{identifier}" if identifier else name,
            "name": f"{name} ({detail})" if detail else name,
            "latitude": latitude,
            "longitude": longitude,
            "feed_url": url,
            "feed_type": "image",
            "source": "itraffic",
        }

    async def cameras(self) -> list[dict]:
        if not self.configured:
            return []
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(
                    API_URL,
                    params={"key": self.api_key, "format": "json"},
                    headers={"User-Agent": _USER_AGENT},
                )
                response.raise_for_status()
                body = response.json()
            records = body if isinstance(body, list) else (body.get("Cameras") or [])
            cameras = [camera for camera in (self._to_camera(record) for record in records) if camera]
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as error:
            self._reachable = False
            self._last_error = _describe(error)
            # Keep the last good result and retry sooner than the full window,
            # but not tightly -- their documented limit is 10 calls per minute.
            kept = self._cache[1] if self._cache else []
            self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, kept)
            return kept
        self._reachable = True
        self._last_error = None
        self._cache = (now, cameras)
        return cameras
