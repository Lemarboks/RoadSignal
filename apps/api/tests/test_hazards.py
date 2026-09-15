import asyncio

import httpx

from app.providers.cctv import CctvCameraProvider
from app.providers.severe_events import SevereEventHazardProvider
from app.providers.wildfire import WildfireHazardProvider

CAPE_TOWN_BBOX = (-35.0, -32.5, 17.5, 20.0)
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock_client(monkeypatch, handler):
    def factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)
    monkeypatch.setattr(httpx, "AsyncClient", factory)


FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
    "-33.95,18.47,320.1,0.4,0.4,2026-09-14,1230,N,nominal,2.0NRT,290.0,12.5,D\n"  # inside Cape Town bbox, near route
    "51.5,-0.1,300.0,0.4,0.4,2026-09-14,1230,N,nominal,2.0NRT,280.0,4.0,D\n"  # London, outside bbox
)


def test_wildfire_provider_filters_to_bbox_and_computes_penalty(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FIRMS_CSV)
    _mock_client(monkeypatch, handler)

    provider = WildfireHazardProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    hotspots = asyncio.run(provider.hotspots())
    assert len(hotspots) == 1
    assert hotspots[0]["latitude"] == -33.95

    route_geometry = [[-33.9249, 18.4241], [-33.951, 18.473], [-33.981, 18.531]]
    penalty, factors = asyncio.run(provider.penalty(route_geometry))
    assert penalty > 0
    assert factors == ["Active wildfire nearby"]


def test_wildfire_provider_ignores_distant_hotspots(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FIRMS_CSV)
    _mock_client(monkeypatch, handler)

    provider = WildfireHazardProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    far_route_geometry = [[-33.0, 17.6], [-32.9, 17.7]]  # inside bbox but far from the hotspot
    penalty, factors = asyncio.run(provider.penalty(far_route_geometry))
    assert penalty == 0.0
    assert factors == []


def test_wildfire_provider_caches_between_calls(monkeypatch):
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=FIRMS_CSV)
    _mock_client(monkeypatch, handler)

    provider = WildfireHazardProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX, cache_seconds=300)
    asyncio.run(provider.hotspots())
    asyncio.run(provider.hotspots())
    assert call_count == 1


EONET_BODY = {
    "events": [
        {
            "id": "EONET_1",
            "title": "Flooding near Cape Town",
            "categories": [{"id": "floods"}],
            "geometry": [{"type": "Point", "coordinates": [18.47, -33.95], "date": "2026-09-14T00:00:00Z"}],
        },
        {
            "id": "EONET_2",
            "title": "Volcano somewhere else",
            "categories": [{"id": "volcanoes"}],
            "geometry": [{"type": "Point", "coordinates": [18.47, -33.95], "date": "2026-09-14T00:00:00Z"}],
        },
        {
            "id": "EONET_3",
            "title": "Storm far away",
            "categories": [{"id": "severeStorms"}],
            "geometry": [{"type": "Point", "coordinates": [-0.1, 51.5], "date": "2026-09-14T00:00:00Z"}],
        },
    ],
}


def test_severe_event_provider_filters_category_and_bbox(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=EONET_BODY)
    _mock_client(monkeypatch, handler)

    provider = SevereEventHazardProvider(url="https://eonet.example/events", timeout=5.0, bbox=CAPE_TOWN_BBOX)
    events = asyncio.run(provider.events())
    assert [event["id"] for event in events] == ["EONET_1"]
    assert events[0]["category"] == "floods"

    route_geometry = [[-33.9249, 18.4241], [-33.951, 18.473]]
    penalty, factors = asyncio.run(provider.penalty(route_geometry))
    assert penalty > 0
    assert factors == ["Flooding nearby"]


CCTV_MARKERS = {
    "ids": ["itraffic-1", "far-away-cam"],
    "lats": [-33.95, 51.5],
    "lngs": [18.47, -0.1],
}
CCTV_BATCH = [
    {
        "id": "itraffic-1",
        "name": "WC CCTV N2 201B",
        "lat": -33.95,
        "lng": 18.47,
        "feed_url": "https://www.i-traffic.co.za/map/Cctv/1",
        "feed_type": "image",
        "source": "itraffic",
        "category": "traffic",
        "active": 1,
    },
]


def test_cctv_provider_filters_bbox_then_resolves_traffic_cameras(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/markers"):
            return httpx.Response(200, json=CCTV_MARKERS)
        return httpx.Response(200, json=CCTV_BATCH)
    _mock_client(monkeypatch, handler)

    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    cameras = asyncio.run(provider.cameras())
    assert len(cameras) == 1
    assert cameras[0]["id"] == "itraffic-1"
    assert cameras[0]["feed_url"] == "https://www.i-traffic.co.za/map/Cctv/1"


def test_cctv_provider_fails_closed_on_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)
    _mock_client(monkeypatch, handler)

    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    assert asyncio.run(provider.cameras()) == []
