from abc import ABC, abstractmethod

import httpx


class RouteProvider(ABC):
    @abstractmethod
    async def alternatives(self, origin: str, destination: str) -> list[dict]: ...


class MockCapeTownRouteProvider(RouteProvider):
    """Network-independent resilience provider used when open services are unavailable."""

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        return [
            {"id": "route-balanced", "name": "Balanced Route", "duration_minutes": 29, "distance_km": 18.7, "geometry": [[-33.9249, 18.4241], [-33.936, 18.443], [-33.951, 18.473], [-33.970, 18.505], [-33.981, 18.531]]},
            {"id": "route-safest", "name": "Safest Route", "duration_minutes": 33, "distance_km": 20.4, "geometry": [[-33.9249, 18.4241], [-33.918, 18.455], [-33.931, 18.489], [-33.955, 18.520], [-33.981, 18.531]]},
            {"id": "route-fastest", "name": "Fastest Route", "duration_minutes": 24, "distance_km": 17.1, "geometry": [[-33.9249, 18.4241], [-33.941, 18.452], [-33.963, 18.478], [-33.976, 18.505], [-33.981, 18.531]]},
        ]


class OpenRouteProvider(RouteProvider):
    """Nominatim geocoding plus OSRM routing, both configurable for self-hosting."""

    def __init__(self, nominatim_url: str, osrm_url: str, timeout: float, user_agent: str):
        self.nominatim_url = nominatim_url.rstrip("/")
        self.osrm_url = osrm_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}

    async def _geocode(self, client: httpx.AsyncClient, query: str) -> tuple[float, float]:
        response = await client.get(
            f"{self.nominatim_url}/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "za"},
            headers=self.headers,
        )
        response.raise_for_status()
        matches = response.json()
        if not matches:
            raise ValueError(f"No location matched {query!r}")
        return float(matches[0]["lat"]), float(matches[0]["lon"])

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            origin_point = await self._geocode(client, origin)
            destination_point = await self._geocode(client, destination)
            coordinates = ";".join(
                f"{longitude},{latitude}" for latitude, longitude in (origin_point, destination_point)
            )
            response = await client.get(
                f"{self.osrm_url}/route/v1/driving/{coordinates}",
                params={"alternatives": 3, "steps": "true", "overview": "full", "geometries": "geojson"},
                headers=self.headers,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") != "Ok" or not body.get("routes"):
                raise ValueError(body.get("message", "No driveable route was found"))

        routes = []
        for index, route in enumerate(body["routes"][:3], start=1):
            names = []
            for leg in route.get("legs", []):
                for step in leg.get("steps", []):
                    name = step.get("ref") or step.get("name")
                    if name and name not in names:
                        names.append(name)
            routes.append({
                "id": f"open-route-{index}",
                "name": " / ".join(names[:2]) or f"Road Alternative {index}",
                "duration_minutes": max(1, round(route["duration"] / 60)),
                "distance_km": round(route["distance"] / 1000, 1),
                "geometry": [[latitude, longitude] for longitude, latitude in route["geometry"]["coordinates"]],
            })
        if not routes:
            raise ValueError("OSRM returned no routes")
        return routes


class ResilientRouteProvider(RouteProvider):
    def __init__(self, primary: RouteProvider, fallback: RouteProvider):
        self.primary = primary
        self.fallback = fallback
        self.last_source = "open"

    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        try:
            routes = await self.primary.alternatives(origin, destination)
            self.last_source = "open"
            return routes
        except (httpx.HTTPError, ValueError):
            self.last_source = "fallback"
            return await self.fallback.alternatives(origin, destination)
