import asyncio

import httpx

from app.providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider


_real_async_client = httpx.AsyncClient


def _mock_client_factory(handler):
    def factory(*args, **kwargs):
        return _real_async_client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return factory


def _handler(osrm_routes):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=[{"lat": "-33.9", "lon": "18.4"}])
        return httpx.Response(200, json={"code": "Ok", "routes": osrm_routes})
    return handle


def _osrm_route(duration=1200, distance=15000, steps=None):
    return {
        "duration": duration,
        "distance": distance,
        "legs": [{"steps": steps if steps is not None else []}],
        "geometry": {"coordinates": [[18.4, -33.9], [18.5, -33.95]]},
    }


def test_open_route_provider_accepts_a_single_alternative(monkeypatch):
    # The public OSRM demo server often returns only one or two alternatives
    # for a given origin/destination pair; requiring three made the live
    # provider discard working responses in favour of mock data.
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(_handler([_osrm_route()])))
    provider = OpenRouteProvider("https://nominatim.example", "https://osrm.example", 5.0, "test-agent")

    routes = asyncio.run(provider.alternatives("Origin", "Destination"))

    assert len(routes) == 1


def test_open_route_provider_raises_when_osrm_returns_no_routes(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(_handler([])))
    provider = OpenRouteProvider("https://nominatim.example", "https://osrm.example", 5.0, "test-agent")

    try:
        asyncio.run(provider.alternatives("Origin", "Destination"))
        raised = False
    except ValueError:
        raised = True

    assert raised


def test_resilient_provider_reports_open_source_for_a_single_live_alternative(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(_handler([_osrm_route()])))
    open_provider = OpenRouteProvider("https://nominatim.example", "https://osrm.example", 5.0, "test-agent")
    resilient = ResilientRouteProvider(open_provider, MockCapeTownRouteProvider())

    routes = asyncio.run(resilient.alternatives("Origin", "Destination"))

    assert resilient.last_source == "open"
    assert len(routes) == 1


def test_open_route_provider_extracts_turn_by_turn_steps(monkeypatch):
    steps = [
        {
            "name": "Long Street", "ref": "", "distance": 500.0, "duration": 60.0,
            "maneuver": {"type": "depart", "location": [18.4, -33.9]},
        },
        {
            "name": "N2", "ref": "N2", "distance": 4200.0, "duration": 240.0,
            "maneuver": {"type": "turn", "modifier": "left", "location": [18.45, -33.92]},
        },
        {
            "name": "", "ref": "", "distance": 0.0, "duration": 0.0,
            "maneuver": {"type": "arrive", "location": [18.5, -33.95]},
        },
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(_handler([_osrm_route(steps=steps)])))
    provider = OpenRouteProvider("https://nominatim.example", "https://osrm.example", 5.0, "test-agent")

    routes = asyncio.run(provider.alternatives("Origin", "Destination"))

    parsed = routes[0]["steps"]
    assert [step["maneuver"] for step in parsed] == ["depart", "turn-left", "arrive"]
    assert parsed[1]["instruction"] == "Turn left onto N2"
    assert parsed[1]["location"] == {"latitude": -33.92, "longitude": 18.45}
    assert parsed[2]["instruction"] == "Arrive at your destination"


def test_mock_route_provider_includes_turn_by_turn_steps():
    routes = asyncio.run(MockCapeTownRouteProvider().alternatives("Origin", "Destination"))

    for route in routes:
        assert len(route["steps"]) >= 2
        assert route["steps"][0]["maneuver"] == "depart"
        assert route["steps"][-1]["maneuver"] == "arrive"
        for step in route["steps"]:
            assert "instruction" in step and "location" in step


def test_resilient_provider_falls_back_when_osrm_returns_no_routes(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(_handler([])))
    open_provider = OpenRouteProvider("https://nominatim.example", "https://osrm.example", 5.0, "test-agent")
    fallback = MockCapeTownRouteProvider()
    resilient = ResilientRouteProvider(open_provider, fallback)

    routes = asyncio.run(resilient.alternatives("Origin", "Destination"))

    assert resilient.last_source == "fallback"
    assert routes == asyncio.run(fallback.alternatives("Origin", "Destination"))
