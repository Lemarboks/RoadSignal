import time

import httpx

_MARKERS_URL = "https://opencctv.org/api/cameras/markers"
_BATCH_URL = "https://opencctv.org/api/cameras/batch"
_BATCH_SIZE = 50


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
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            cameras = []
        self._cache = (now, cameras)
        return cameras
