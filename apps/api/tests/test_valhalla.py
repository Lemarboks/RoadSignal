import asyncio
import json

import httpx
import pytest

from app.providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider
from app.providers.valhalla import ValhallaRouteProvider, decode_polyline6


REAL_ASYNC_CLIENT = httpx.AsyncClient


def encode_polyline6(points):
    encoded = []
    previous = [0, 0]
    for point in points:
        for axis, coordinate in enumerate(point):
            integer = round(coordinate * 1_000_000)
            delta = integer - previous[axis]
            previous[axis] = integer
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 32:
                encoded.append(chr((32 | (value & 31)) + 63))
                value >>= 5
            encoded.append(chr(value + 63))
    return "".join(encoded)


def mock_client(monkeypatch, handler):
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: REAL_ASYNC_CLIENT(
        transport=httpx.MockTransport(handler), follow_redirects=True,
    ))


def trip(points, **overrides):
    return {
        "status": 0,
        "units": "kilometers",
        "summary": {"time": 600, "length": 12.4},
        "legs": [{"shape": encode_polyline6(points), "maneuvers": [{"street_names": ["N2"]}]}],
        **overrides,
    }


def test_valhalla_requests_auto_alternatives_and_decodes_southern_hemisphere_geometry(monkeypatch):
    points = [[-33.941, 18.452], [-33.95, 18.47], [-33.963, 18.478]]

    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json=[{"lat": "-33.941", "lon": "18.452"}])
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["costing"] == "auto"
        assert body["units"] == "kilometers"
        assert body["alternates"] == 2
        assert body["shape_format"] == "polyline6"
        assert "costing_options" not in body
        return httpx.Response(200, json={
            "trip": trip(points), "alternates": [{"trip": trip(list(reversed(points)))}],
        })

    mock_client(monkeypatch, handler)
    provider = ValhallaRouteProvider("https://geo.test", "https://valhalla.test", 5, "test")
    routes = asyncio.run(provider.alternatives("Cape Town", "Airport"))
    assert len(routes) == 2
    assert routes[0]["geometry"] == points
    assert routes[0]["distance_km"] == 12.4
    assert routes[0]["duration_minutes"] == 10
    assert routes[0]["name"] == "N2"


@pytest.mark.parametrize("encoded", ["", "_", "~" * 20, "a", "\n", "??"])
def test_polyline_rejects_truncated_or_invalid_shapes(encoded):
    with pytest.raises(ValueError):
        decode_polyline6(encoded)


@pytest.mark.parametrize("body", [{}, {"trip": None}, {"trip": {"summary": {"time": 1}}}])
def test_malformed_valhalla_responses_allow_resilient_fallback(monkeypatch, body):
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json=[{"lat": "-33.9", "lon": "18.4"}])
        return httpx.Response(200, json=body)

    mock_client(monkeypatch, handler)
    provider = ResilientRouteProvider(
        ValhallaRouteProvider("https://geo.test", "https://valhalla.test", 5, "test"),
        MockCapeTownRouteProvider(),
    )
    assert len(asyncio.run(provider.alternatives("A", "B"))) == 3
    assert provider.last_source == "fallback"


def test_valhalla_failure_uses_osrm_and_preserves_actual_provider_provenance(monkeypatch):
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json=[{"lat": "-33.9", "lon": "18.4"}])
        if request.url.host == "valhalla.test":
            return httpx.Response(503)
        return httpx.Response(200, json={"code": "Ok", "routes": [{
            "duration": 1200, "distance": 15000, "legs": [],
            "geometry": {"coordinates": [[18.4, -33.9], [18.5, -33.95]]},
        }]})

    mock_client(monkeypatch, handler)
    provider = ResilientRouteProvider(
        ValhallaRouteProvider("https://geo.test", "https://valhalla.test", 5, "test"),
        ResilientRouteProvider(
            OpenRouteProvider("https://geo.test", "https://osrm.test", 5, "test"),
            MockCapeTownRouteProvider(),
        ),
    )
    routes = asyncio.run(provider.alternatives("A", "B"))
    assert routes[0]["id"] == "open-route-1"
    assert provider.last_source == "open"


def test_successful_valhalla_route_preserves_valhalla_provenance(monkeypatch):
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json=[{"lat": "-33.9", "lon": "18.4"}])
        return httpx.Response(200, json={"trip": trip([[-33.9, 18.4], [-33.95, 18.5]])})

    mock_client(monkeypatch, handler)
    provider = ResilientRouteProvider(
        ValhallaRouteProvider("https://geo.test", "https://valhalla.test", 5, "test"),
        MockCapeTownRouteProvider(),
    )
    asyncio.run(provider.alternatives("A", "B"))
    assert provider.last_source == "valhalla"
