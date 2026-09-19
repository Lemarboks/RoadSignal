import time

import httpx

_MARKERS_URL = "https://opencctv.org/api/cameras/markers"
_BATCH_URL = "https://opencctv.org/api/cameras/batch"
_BATCH_SIZE = 50
# After a failure, retry this soon rather than sitting on it for the whole TTL.
_RETRY_AFTER_SECONDS = 120.0


def _describe(error: Exception) -> str:
    """A short, safe reason for the UI -- no upstream response bodies."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"source returned HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "source unreachable"
    return "source returned unexpected data"


class CctvCameraProvider:
    """Public traffic cameras near a region, indexed via opencctv.org.

    opencctv.org aggregates ~145k cameras republished from official traffic
    authorities worldwide (for Cape Town: the Western Cape Government's
    i-traffic network). This provider narrows that index to a bounding box
    and the "traffic" category, then resolves full records for the matches.
    """

    def __init__(self, timeout: float, bbox: tuple[float, float, float, float], cache_seconds: float = 3600):
        self.timeout = timeout
        self.bbox = bbox
        self.cache_seconds = cache_seconds
        self._cache: tuple[float, list[dict]] | None = None
        # An upstream failure and a genuinely empty region both used to produce
        # [], so callers could not tell "no cameras here" from "the source is
        # down". opencctv.org put its API behind auth and started returning
        # 403, which surfaced as "0 traffic cameras" -- indistinguishable from
        # working correctly. Track the outcome so the API can say which it is.
        self._reachable = True
        self._last_error: str | None = None

    async def _matching_ids(self, client: httpx.AsyncClient) -> list[str]:
        south, north, west, east = self.bbox
        response = await client.get(_MARKERS_URL, headers={"User-Agent": "RoadSignal/1.0 (traffic camera layer)"})
        response.raise_for_status()
        body = response.json()
        ids, lats, lngs = body.get("ids") or [], body.get("lats") or [], body.get("lngs") or []
        return [
            camera_id
            for camera_id, latitude, longitude in zip(ids, lats, lngs)
            if south <= latitude <= north and west <= longitude <= east
        ]

    @property
    def reachable(self) -> bool:
        return self._reachable

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def cameras(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        cameras: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                candidate_ids = await self._matching_ids(client)
                for start in range(0, len(candidate_ids), _BATCH_SIZE):
                    batch_ids = candidate_ids[start:start + _BATCH_SIZE]
                    response = await client.post(
                        _BATCH_URL,
                        json={"ids": batch_ids},
                        headers={"User-Agent": "RoadSignal/1.0 (traffic camera layer)"},
                    )
                    response.raise_for_status()
                    for record in response.json():
                        if record.get("category") != "traffic" or not record.get("active"):
                            continue
                        cameras.append({
                            "id": record.get("id"),
                            "name": record.get("name") or record.get("id"),
                            "latitude": record.get("lat"),
                            "longitude": record.get("lng"),
                            "feed_url": record.get("feed_url"),
                            "feed_type": record.get("feed_type"),
                            "source": record.get("source"),
                        })
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
            self._reachable = False
            self._last_error = _describe(error)
            # Deliberately do NOT cache a failure for the full hour, and do not
            # discard a previously good result: a brief upstream blip should not
            # blank the layer until the TTL expires.
            if self._cache:
                self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, self._cache[1])
                return self._cache[1]
            self._cache = (now - self.cache_seconds + _RETRY_AFTER_SECONDS, [])
            return []
        self._reachable = True
        self._last_error = None
        self._cache = (now, cameras)
        return cameras
