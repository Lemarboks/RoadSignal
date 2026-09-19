"""A dead feed must not look like good news.

opencctv.org put its API behind authentication and began returning 403. The
provider caught it, returned [], and the UI rendered "0 traffic cameras" --
indistinguishable from a working feed reporting an empty region. The layer was
broken for some time without anything indicating it.

These tests pin the two properties that failure taught us: report whether the
source answered, and never cache a failure for the full TTL.
"""
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


MARKERS = {"ids": ["itraffic-1"], "lats": [-33.95], "lngs": [18.47]}
BATCH = [{
    "id": "itraffic-1", "name": "WC CCTV N2 201B", "lat": -33.95, "lng": 18.47,
    "feed_url": "https://www.i-traffic.co.za/map/Cctv/1", "feed_type": "image",
    "source": "itraffic", "category": "traffic", "active": 1,
}]
EMPTY_FIRMS = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"


def test_cameras_report_unavailable_on_the_403_that_broke_this():
    """The exact upstream behaviour: 403 {"error":"Unauthorized"}."""
    def handler(request):
        return httpx.Response(403, json={"error": "Unauthorized"})

    import pytest
    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, handler)
        assert asyncio.run(provider.cameras()) == []
    assert provider.reachable is False
    assert "403" in (provider.last_error or "")


def test_cameras_report_ok_when_the_source_answers():
    import pytest
    def handler(request):
        if request.url.path.endswith("/markers"):
            return httpx.Response(200, json=MARKERS)
        return httpx.Response(200, json=BATCH)

    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, handler)
        assert len(asyncio.run(provider.cameras())) == 1
    assert provider.reachable is True
    assert provider.last_error is None


def test_an_empty_region_is_not_reported_as_unavailable():
    """A reachable source with nothing to report is healthy, not broken."""
    import pytest
    def handler(request):
        if request.url.path.endswith("/markers"):
            return httpx.Response(200, json={"ids": [], "lats": [], "lngs": []})
        return httpx.Response(200, json=[])

    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, handler)
        assert asyncio.run(provider.cameras()) == []
    assert provider.reachable is True


def test_a_failure_does_not_discard_a_previously_good_result():
    """A brief blip should not blank the layer for the rest of the TTL."""
    import pytest
    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX, cache_seconds=3600)

    def good(request):
        if request.url.path.endswith("/markers"):
            return httpx.Response(200, json=MARKERS)
        return httpx.Response(200, json=BATCH)

    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, good)
        assert len(asyncio.run(provider.cameras())) == 1

    # Force the cache to look expired, then fail the refresh.
    provider._cache = (provider._cache[0] - 4000, provider._cache[1])
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, lambda request: httpx.Response(503))
        kept = asyncio.run(provider.cameras())

    assert len(kept) == 1, "the last good result should be kept"
    assert provider.reachable is False, "but the source is still reported as down"


def test_a_failure_is_retried_soon_rather_than_cached_for_the_whole_ttl():
    import pytest
    import time as time_module
    provider = CctvCameraProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX, cache_seconds=3600)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, lambda request: httpx.Response(503))
        asyncio.run(provider.cameras())
    # The stamp is backdated so the entry expires within the retry window,
    # not an hour later.
    age = time_module.monotonic() - provider._cache[0]
    assert age > provider.cache_seconds - 300, "a failure must expire quickly"


def test_wildfires_distinguish_no_fires_from_a_dead_feed():
    """Zero active fires is normal for Cape Town, so this distinction is the
    difference between 'all clear' and 'we cannot tell'."""
    import pytest
    provider = WildfireHazardProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, lambda request: httpx.Response(200, text=EMPTY_FIRMS))
        assert asyncio.run(provider.hotspots()) == []
    assert provider.reachable is True, "an empty fire list is a healthy answer"

    down = WildfireHazardProvider(timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, lambda request: httpx.Response(500))
        assert asyncio.run(down.hotspots()) == []
    assert down.reachable is False


def test_severe_events_report_unavailability():
    import pytest
    provider = SevereEventHazardProvider(url="https://eonet.example/events", timeout=5.0, bbox=CAPE_TOWN_BBOX)
    with pytest.MonkeyPatch.context() as monkeypatch:
        _mock_client(monkeypatch, lambda request: httpx.Response(502))
        assert asyncio.run(provider.events()) == []
    assert provider.reachable is False
