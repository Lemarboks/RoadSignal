"""Open municipal faults, and the projection and darkness maths behind them.

Three things must hold: Lo coordinates must land where the record says it is
(a projection error puts street lights in the sea and looks plausible in a
count), a street-light outage must only count after dark, and an unreachable
source must say so rather than presenting an empty layer as a clear road.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.providers.lo_projection import field_pair_to_wgs84, lo_to_wgs84
from app.providers.service_requests import CATEGORIES, ServiceRequestProvider
from app.providers.solar import darkness_factor, is_dark, solar_elevation, sunrise, sunset

CAPE_TOWN_BBOX = (-35.0, -32.5, 17.5, 20.0)
SAST = timezone(timedelta(hours=2))
CBD = (-33.9249, 18.4241)
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock(monkeypatch, handler):
    def factory(*args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def _record(coordinate_1, coordinate_2, complaint="Street Lights - Single Light Out", **extra):
    return {
        "attributes": {
            "Notification": extra.get("id", "1"),
            "C3_Complaint_Type": complaint,
            "Suburb": extra.get("suburb", "TABLE VIEW"),
            "X_Y_Co_ordinate_1": coordinate_1,
            "X_Y_Co_ordinate_2": coordinate_2,
            "Created_On_Date": extra.get("created", 1_756_000_000_000),
        }
    }


# --- projection -----------------------------------------------------------

@pytest.mark.parametrize(
    "field_1,field_2,expected_lat,expected_lon",
    [
        (-3743793.17, -47667.49, -33.820, 18.485),  # Table View
        (-3768933.45, -33097.81, -34.047, 18.642),  # Khayelitsha
        (-3739929.47, -47261.72, -33.785, 18.490),  # Sunningdale
    ],
)
def test_lo_coordinates_land_where_the_record_says(field_1, field_2, expected_lat, expected_lon):
    latitude, longitude = field_pair_to_wgs84(field_1, field_2)
    assert abs(latitude - expected_lat) < 0.01, "latitude off by more than ~1km"
    assert abs(longitude - expected_lon) < 0.01, "longitude off by more than ~1km"


def test_the_placeholder_position_is_dropped_not_mapped_to_africas_coast():
    """A quarter of the table stores 0,0 for "no location"."""
    assert field_pair_to_wgs84(0, 0) is None
    assert field_pair_to_wgs84(-3743793.17, 0) is None
    assert field_pair_to_wgs84(None, None) is None
    assert field_pair_to_wgs84("nonsense", "nonsense") is None


def test_the_central_meridian_is_on_the_central_meridian():
    """Zero westing must come back as exactly the belt's meridian."""
    _, longitude = lo_to_wgs84(3_750_000, 0.0)
    assert abs(longitude - 19.0) < 1e-6


# --- solar ----------------------------------------------------------------

def test_sunrise_and_sunset_match_published_cape_town_times():
    # Published for Cape Town: 21 June 07:51 / 17:45 SAST.
    solstice = datetime(2026, 6, 21, 12, tzinfo=timezone.utc)
    rise = sunrise(*CBD, solstice).astimezone(SAST)
    set_ = sunset(*CBD, solstice).astimezone(SAST)
    assert (rise.hour, abs(rise.minute - 51) <= 5) == (7, True), rise
    assert (set_.hour, abs(set_.minute - 45) <= 5) == (17, True), set_


def test_midday_is_not_dark_and_midnight_is():
    assert is_dark(*CBD, datetime(2026, 9, 21, 12, tzinfo=SAST)) is False
    assert is_dark(*CBD, datetime(2026, 9, 21, 0, tzinfo=SAST)) is True


def test_darkness_ramps_rather_than_switching():
    """A hard boundary would swing a score on a minute of departure time."""
    noon = darkness_factor(*CBD, datetime(2026, 6, 21, 13, tzinfo=SAST))
    dusk = darkness_factor(*CBD, datetime(2026, 6, 21, 18, tzinfo=SAST))
    night = darkness_factor(*CBD, datetime(2026, 6, 21, 22, tzinfo=SAST))
    assert noon == 0.0
    assert 0 < dusk < 1, f"dusk should be partial, got {dusk}"
    assert night == 1.0


def test_the_sun_is_higher_at_noon_than_at_breakfast():
    noon = solar_elevation(*CBD, datetime(2026, 9, 21, 12, tzinfo=SAST))
    early = solar_elevation(*CBD, datetime(2026, 9, 21, 7, tzinfo=SAST))
    assert noon > early > -20


# --- provider -------------------------------------------------------------

def test_requests_are_categorised_and_positioned(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3743793.17, -47667.49),
        _record(-3743800.0, -47600.0, complaint="Traffic Controller: No Power", id="2"),
    ]}))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    entries = asyncio.run(provider.requests())
    assert {entry["category"] for entry in entries} == {"street_light", "traffic_signal"}
    assert all(-35 < entry["latitude"] < -32.5 for entry in entries)
    assert provider.reachable is True


def test_records_outside_the_bbox_are_dropped(monkeypatch):
    # A KwaZulu-Natal position in Lo31, nowhere near the configured area.
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3_295_000.0, -33_000.0)
    ]}))
    assert asyncio.run(ServiceRequestProvider(CAPE_TOWN_BBOX).requests()) == []


def test_only_the_documented_complaint_types_are_requested(monkeypatch):
    seen = {}

    def handler(request):
        seen["where"] = request.url.params.get("where", "")
        return httpx.Response(200, json={"features": []})

    _mock(monkeypatch, handler)
    asyncio.run(ServiceRequestProvider(CAPE_TOWN_BBOX).requests())
    where = seen["where"]
    assert "Completed_Date IS NULL" in where, "must ask only for still-open faults"
    assert "X_Y_Co_ordinate_1 <> 0" in where, "must skip the unpositioned records"
    for names in CATEGORIES.values():
        for name in names:
            assert name in where
    assert "Closure of Roads" not in where, "the closure type has no open records"


def test_a_street_light_counts_only_after_dark(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3743793.17, -47667.49, id=str(index)) for index in range(6)
    ]}))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    route = [field_pair_to_wgs84(-3743793.17, -47667.49)] * 3

    day, day_factors = asyncio.run(
        provider.penalty(route, datetime(2026, 9, 21, 13, tzinfo=SAST))
    )
    night, night_factors = asyncio.run(
        provider.penalty(route, datetime(2026, 9, 21, 22, tzinfo=SAST))
    )
    assert day == 0.0 and day_factors == [], "a broken light at midday is not a hazard"
    assert night > 0 and night_factors, "a dark road with six lights out must count"


def test_a_dead_traffic_light_counts_regardless_of_daylight(monkeypatch):
    """Unlike lighting, an unsignalled junction is a hazard at any hour."""
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3743793.17, -47667.49, complaint="Traffic Controller: No Power")
    ]}))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    route = [field_pair_to_wgs84(-3743793.17, -47667.49)] * 3
    penalty, factors = asyncio.run(
        provider.penalty(route, datetime(2026, 9, 21, 13, tzinfo=SAST))
    )
    assert penalty > 0
    assert "traffic light without power" in factors[0]


def test_faults_far_from_the_route_do_not_count(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3768933.45, -33097.81, complaint="Traffic Controller: No Power")
    ]}))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    far_route = [field_pair_to_wgs84(-3743793.17, -47667.49)] * 3  # ~30km away
    penalty, factors = asyncio.run(
        provider.penalty(far_route, datetime(2026, 9, 21, 22, tzinfo=SAST))
    )
    assert penalty == 0.0 and factors == []


def test_plural_phrasing_reads_correctly(monkeypatch):
    """Naive pluralisation produced "15 street light outs reported"."""
    _mock(monkeypatch, lambda request: httpx.Response(200, json={"features": [
        _record(-3743793.17, -47667.49, id=str(index)) for index in range(4)
    ]}))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    route = [field_pair_to_wgs84(-3743793.17, -47667.49)] * 3
    _, factors = asyncio.run(provider.penalty(route, datetime(2026, 9, 21, 22, tzinfo=SAST)))
    assert factors == ["4 street lights out reported"]


def test_an_unreachable_source_says_so_rather_than_showing_a_clear_road(monkeypatch):
    _mock(monkeypatch, lambda request: httpx.Response(503))
    provider = ServiceRequestProvider(CAPE_TOWN_BBOX)
    layer = asyncio.run(provider.layer())
    assert layer["status"] == "unavailable"
    assert "503" in (layer["detail"] or "")
    assert layer["count"] == 0
