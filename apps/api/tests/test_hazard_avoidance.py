import asyncio
import json

import httpx

from app.providers.hazard_avoidance import HazardAvoidanceBuilder, circle_ring, ring_circumference_m
from app.providers.valhalla import ValhallaRouteProvider

_REAL_ASYNC_CLIENT = httpx.AsyncClient


class _StubWildfire:
    def __init__(self, hotspots): self._hotspots = hotspots
    async def hotspots(self): return self._hotspots


class _StubEvents:
    def __init__(self, events): self._events = events
    async def events(self): return self._events


class _StubCrime:
    def __init__(self, precincts, available=True):
        self._precincts = precincts
        self.available = available
    def layer(self): return self._precincts


class _BrokenWildfire:
    async def hotspots(self): raise RuntimeError("upstream down")


def test_circle_ring_is_closed_and_sized_correctly():
    ring = circle_ring(-33.9249, 18.4241, radius_km=1.5, segments=12)
    assert len(ring) == 13  # 12 segments + closing point
    assert ring[0] == ring[-1], "ring must be closed"
    # Every vertex should sit roughly the requested distance from the centre.
    from app.risk.engine import haversine_km
    for longitude, latitude in ring:
        distance = haversine_km((-33.9249, 18.4241), (latitude, longitude))
        assert 1.2 < distance < 1.8, f"vertex {distance:.2f}km from centre"


def test_rings_use_lon_lat_order_as_valhalla_requires():
    ring = circle_ring(-33.9249, 18.4241, radius_km=1.0)
    for longitude, latitude in ring:
        # Cape Town: longitude ~18, latitude ~-34. Swapped order would be obvious.
        assert 17 < longitude < 20, "first element must be longitude"
        assert -35 < latitude < -32, "second element must be latitude"


def test_point_hazards_become_exclusion_zones():
    builder = HazardAvoidanceBuilder(
        _StubWildfire([{"latitude": -33.95, "longitude": 18.47, "frp": 12.0}]),
        _StubEvents([{"latitude": -33.98, "longitude": 18.52, "category": "floods", "id": "E1", "title": "Flood"}]),
        _StubCrime([]),
    )
    polygons, reasons = asyncio.run(builder.build())
    assert len(polygons) == 2
    assert any("wildfire" in reason for reason in reasons)
    assert any("severe weather" in reason for reason in reasons)


def _small_precinct(name: str, percentile: float) -> dict:
    """~2km perimeter: small enough to fit inside the exclusion budget."""
    return {"name": name, "percentile": percentile, "rings": [circle_ring(-33.95, 18.47, 0.3)]}


def test_crime_precinct_exclusion_is_opt_in():
    precincts = [_small_precinct("Worst", 0.95), _small_precinct("Middling", 0.50)]
    builder = HazardAvoidanceBuilder(_StubWildfire([]), _StubEvents([]), _StubCrime(precincts), crime_percentile=0.9)

    without, _ = asyncio.run(builder.build(include_crime=False))
    assert without == [], "excluding residential precincts must never be a silent default"

    with_crime, reasons = asyncio.run(builder.build(include_crime=True))
    assert len(with_crime) == 1, "only precincts above the percentile qualify"
    assert any("percentile" in reason for reason in reasons)


def test_real_precinct_outlines_are_too_large_for_valhallas_ceiling():
    """Measured against the committed dataset: the smallest precinct above the
    90th percentile has an 8.4km perimeter and the largest 21.7km, against a
    10km total ceiling. Crime exclusion therefore only ever fits one small
    precinct -- which is why crime is primarily a scoring input, not a hard
    avoid. The builder must report the omission rather than silently dropping
    it or sending a request Valhalla will reject outright."""
    realistic = {
        "name": "Nyanga-sized",
        "percentile": 0.98,
        "rings": [circle_ring(-33.98, 18.58, 3.5)],  # ~22km perimeter
    }
    builder = HazardAvoidanceBuilder(
        _StubWildfire([]), _StubEvents([]), _StubCrime([realistic]), crime_percentile=0.9,
    )
    polygons, reasons = asyncio.run(builder.build(include_crime=True))
    assert polygons == [], "an oversized precinct must not be sent"
    assert any("omitted" in reason for reason in reasons), "the omission must be surfaced"


def test_exclusion_set_respects_valhallas_circumference_ceiling():
    """A real Valhalla instance rejects the whole request with error 167 once
    the combined exclusion perimeter exceeds 10km. Found by live testing: the
    original 1.5km radius produced a ~9.4km circumference per ring, so even
    two hazards broke routing entirely."""
    many = [{"latitude": -33.9 - i / 200, "longitude": 18.4, "frp": 1.0} for i in range(40)]
    builder = HazardAvoidanceBuilder(
        _StubWildfire(many), _StubEvents([]), _StubCrime([]), circumference_budget_m=9000.0,
    )
    polygons, reasons = asyncio.run(builder.build())
    total = sum(ring_circumference_m(ring) for ring in polygons)
    assert total <= 9000.0, f"exclusion perimeter {total:.0f}m would be rejected by Valhalla"
    assert polygons, "some hazards should still be admitted within budget"
    assert any("omitted" in reason for reason in reasons), "dropped hazards must be reported"


def test_default_radii_leave_room_for_several_hazards():
    """Guards the regression that made this feature unusable: defaults must be
    small enough that more than one hazard fits inside the 10km ceiling."""
    ring = circle_ring(-33.95, 18.47, 0.6)
    assert ring_circumference_m(ring) < 4500, "a single zone must not eat the budget"


def test_a_failing_hazard_provider_does_not_break_routing():
    builder = HazardAvoidanceBuilder(_BrokenWildfire(), _StubEvents([]), _StubCrime([]))
    polygons, reasons = asyncio.run(builder.build())
    assert polygons == [] and reasons == []


VALHALLA_BODY = {
    "trip": {
        "status": 0,
        "units": "kilometers",
        "summary": {"time": 1200, "length": 18.5},
        "legs": [{
            "shape": "_ibE_seK_seK_ibE",
            "maneuvers": [
                {"type": 1, "instruction": "Depart", "begin_shape_index": 0, "length": 1.0, "time": 60, "street_names": ["N2"]},
                {"type": 4, "instruction": "Arrive", "begin_shape_index": 1, "length": 0.0, "time": 0},
            ],
        }],
    }
}


def test_exclude_polygons_is_sent_top_level_in_the_valhalla_request():
    """A misnamed or misplaced key would be ignored silently, leaving routing
    unchanged while appearing to work."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in str(request.url) or "search" in str(request.url):
            return httpx.Response(200, json=[{"lat": "-33.9249", "lon": "18.4241", "display_name": "Cape Town"}])
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=VALHALLA_BODY)

    def factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)

    original = httpx.AsyncClient
    httpx.AsyncClient = factory  # type: ignore[misc]
    try:
        provider = ValhallaRouteProvider("https://nominatim.example", "https://valhalla.example", 5.0, "test/1.0")
        rings = [circle_ring(-33.95, 18.47, 1.5)]
        asyncio.run(provider.alternatives("Cape Town", "Airport", exclude_polygons=rings))
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    payload = captured.get("payload", {})
    assert "exclude_polygons" in payload, "must be a top-level key, not nested in costing_options"
    assert payload["exclude_polygons"] == rings
    assert payload["costing"] == "auto"


def test_routing_without_exclusions_omits_the_key_entirely():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in str(request.url) or "search" in str(request.url):
            return httpx.Response(200, json=[{"lat": "-33.9249", "lon": "18.4241", "display_name": "Cape Town"}])
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=VALHALLA_BODY)

    def factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)

    original = httpx.AsyncClient
    httpx.AsyncClient = factory  # type: ignore[misc]
    try:
        provider = ValhallaRouteProvider("https://nominatim.example", "https://valhalla.example", 5.0, "test/1.0")
        asyncio.run(provider.alternatives("Cape Town", "Airport"))
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert "exclude_polygons" not in captured.get("payload", {})
