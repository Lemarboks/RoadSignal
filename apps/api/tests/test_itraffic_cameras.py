"""Cameras via the official i-TRAFFIC developer API.

The previous source (opencctv.org, an aggregator) put its API behind auth and
returns 403. Scraping i-TRAFFIC's map instead is not an option: their terms
prohibit automated extraction and robots.txt disallows the bulk data path.
These tests cover the sanctioned route -- GET /api/getcameras?key=&format=json
-- and the reporting that keeps a missing key from looking like an empty city.
"""
import asyncio

import httpx

from app.providers.cameras import ResilientCameraProvider
from app.providers.itraffic import ITrafficCameraProvider

CAPE_TOWN_BBOX = (-35.0, -32.5, 17.5, 20.0)
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock(monkeypatch, handler):
    def factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)
    monkeypatch.setattr(httpx, "AsyncClient", factory)


# Field names follow the published GetCameras response. The documented sample
# body is placeholder text ("sample string 5"), so URLs here reflect only what
# the field description promises: "The url to fetch the camera image".
SAMPLE = [
    {
        "ID": "1--4", "Name": "N2 201B", "DirectionOfTravel": "Eastbound",
        "RoadwayName": "N2", "Url": "https://www.i-traffic.co.za/Content/Images/cctv/1--4.jpg",
        "Disabled": False, "Blocked": False, "Latitude": -33.9465, "Longitude": 18.4671,
    },
    {  # outside the configured bounding box (KwaZulu-Natal)
        "ID": "90--3", "Name": "N2-CCTV-030A", "DirectionOfTravel": "Unknown",
        "RoadwayName": "N2", "Url": "https://www.i-traffic.co.za/Content/Images/cctv/90--3.jpg",
        "Disabled": False, "Blocked": False, "Latitude": -29.7768, "Longitude": 30.9989,
    },
    {  # disabled cameras must not be offered to a driver
        "ID": "7--4", "Name": "M5 Broken", "DirectionOfTravel": "None",
        "RoadwayName": "M5", "Url": "https://www.i-traffic.co.za/Content/Images/cctv/7--4.jpg",
        "Disabled": True, "Blocked": False, "Latitude": -33.95, "Longitude": 18.48,
    },
    {  # blocked likewise
        "ID": "8--4", "Name": "M5 Blocked", "DirectionOfTravel": "None",
        "RoadwayName": "M5", "Url": "https://www.i-traffic.co.za/Content/Images/cctv/8--4.jpg",
        "Disabled": False, "Blocked": True, "Latitude": -33.95, "Longitude": 18.48,
    },
]


def test_an_unconfigured_provider_reports_the_missing_key_not_an_empty_city():
    provider = ITrafficCameraProvider("", CAPE_TOWN_BBOX)
    assert provider.configured is False
    assert provider.reachable is False
    assert "ITRAFFIC_API_KEY" in (provider.last_error or "")
    assert asyncio.run(provider.cameras()) == []


def test_cameras_are_filtered_to_the_bbox_and_exclude_disabled_or_blocked(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(200, json=SAMPLE))
    provider = ITrafficCameraProvider("test-key", CAPE_TOWN_BBOX)
    cameras = asyncio.run(provider.cameras())
    assert [camera["id"] for camera in cameras] == ["itraffic-1--4"]
    assert provider.reachable is True


def test_the_key_and_json_format_are_sent_as_documented(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[])

    _mock(monkeypatch, handler)
    asyncio.run(ITrafficCameraProvider("secret-key", CAPE_TOWN_BBOX).cameras())
    assert "key=secret-key" in seen["url"]
    assert "format=json" in seen["url"]
    assert "/api/getcameras" in seen["url"].lower()


def test_the_label_carries_roadway_and_direction(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(200, json=SAMPLE))
    camera = asyncio.run(ITrafficCameraProvider("k", CAPE_TOWN_BBOX).cameras())[0]
    assert camera["name"] == "N2 201B (N2 Eastbound)"
    assert camera["feed_url"].endswith("/cctv/1--4.jpg")
    assert camera["feed_type"] == "image"


def test_a_relative_image_url_is_made_absolute(monkeypatch):
    """The web client uses feed_url as an <img src>, where a bare path fails."""
    record = dict(SAMPLE[0], Url="/Content/Images/cctv/1--4.jpg")
    _mock(monkeypatch, lambda request: httpx.Response(200, json=[record]))
    camera = asyncio.run(ITrafficCameraProvider("k", CAPE_TOWN_BBOX).cameras())[0]
    assert camera["feed_url"] == "https://www.i-traffic.co.za/Content/Images/cctv/1--4.jpg"


def test_an_http_error_is_reported_not_swallowed(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(403))
    provider = ITrafficCameraProvider("bad-key", CAPE_TOWN_BBOX)
    assert asyncio.run(provider.cameras()) == []
    assert provider.reachable is False
    assert "403" in (provider.last_error or "")


class _Stub:
    def __init__(self, cameras, reachable, configured=True, error=None):
        self._cameras, self._reachable = cameras, reachable
        self.configured, self._error = configured, error
    @property
    def reachable(self): return self._reachable
    @property
    def last_error(self): return self._error
    async def cameras(self): return self._cameras


def test_the_official_api_is_preferred_when_configured():
    resilient = ResilientCameraProvider(
        _Stub([{"id": "itraffic-1"}], reachable=True),
        _Stub([{"id": "opencctv-1"}], reachable=True),
    )
    assert [c["id"] for c in asyncio.run(resilient.cameras())] == ["itraffic-1"]
    assert resilient.source == "i-traffic.co.za"


def test_it_falls_back_when_no_key_is_configured():
    resilient = ResilientCameraProvider(
        _Stub([], reachable=False, configured=False, error="no key"),
        _Stub([{"id": "opencctv-1"}], reachable=True),
    )
    assert [c["id"] for c in asyncio.run(resilient.cameras())] == ["opencctv-1"]
    assert resilient.source == "opencctv.org"
    assert resilient.reachable is True


def test_both_sources_down_reports_unreachable_with_an_actionable_reason():
    """The real current state: no key, and the aggregator returning 403."""
    resilient = ResilientCameraProvider(
        _Stub([], reachable=False, configured=False, error="no i-TRAFFIC developer key configured"),
        _Stub([], reachable=False, error="source returned HTTP 403"),
    )
    assert asyncio.run(resilient.cameras()) == []
    assert resilient.reachable is False
    reason = resilient.last_error or ""
    assert "developer key" in reason, "the actionable problem must lead"
    assert "403" in reason, "the fallback's failure is still worth reporting"


def test_reachability_is_not_claimed_before_anything_is_attempted():
    resilient = ResilientCameraProvider(
        _Stub([], reachable=True, configured=False), _Stub([], reachable=True),
    )
    assert resilient.reachable is False, "optimistic defaults must not imply health"
