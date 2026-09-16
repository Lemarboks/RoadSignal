"""Optional Valhalla automobile routing; RoadSignal risk ranking stays separate.

This adapter uses the upstream auto costing model. Custom incident-aware edge
costing requires a separately built routing graph and is not enabled here.
"""

import math

import httpx

from .routes import OpenRouteProvider

_VALHALLA_MANEUVER = {
    1: "depart", 2: "depart", 3: "depart",
    4: "arrive", 5: "arrive", 6: "arrive",
    7: "straight", 8: "straight", 17: "straight", 22: "straight", 25: "straight",
    9: "slight-right", 16: "slight-left",
    10: "turn-right", 15: "turn-left",
    11: "sharp-right", 14: "sharp-left",
    12: "uturn", 13: "uturn", 37: "uturn",
    18: "slight-right", 19: "slight-left", 20: "slight-right", 21: "slight-left",
    23: "turn-right", 24: "turn-left",
    26: "roundabout", 27: "roundabout",
}


def _valhalla_step(maneuver: dict, points: list[list[float]]) -> dict | None:
    index = maneuver.get("begin_shape_index")
    if not isinstance(index, int) or index < 0 or index >= len(points):
        return None
    latitude, longitude = points[index]
    street_names = [name for name in maneuver.get("street_names", []) if isinstance(name, str) and name]
    return {
        "instruction": maneuver.get("instruction") or "Continue",
        "maneuver": _VALHALLA_MANEUVER.get(maneuver.get("type"), "straight"),
        "street_name": ", ".join(street_names[:2]),
        "distance_meters": round(float(maneuver.get("length", 0)) * 1000, 1),
        "duration_seconds": round(float(maneuver.get("time", 0)), 1),
        "location": {"latitude": latitude, "longitude": longitude},
    }


def decode_polyline6(encoded: str) -> list[list[float]]:
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Valhalla returned an empty route shape")
    position = 0
    coordinates = [0, 0]
    points = []
    while position < len(encoded):
        for axis in (0, 1):
            result = shift = 0
            while True:
                if position >= len(encoded) or shift > 30:
                    raise ValueError("Malformed Valhalla polyline6")
                byte = ord(encoded[position]) - 63
                position += 1
                if not 0 <= byte <= 63:
                    raise ValueError("Invalid Valhalla polyline character")
                result |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            coordinates[axis] += ~(result >> 1) if result & 1 else result >> 1
        latitude, longitude = (value / 1_000_000 for value in coordinates)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Valhalla route coordinates outside WGS84 bounds")
        points.append([latitude, longitude])
    if len(points) < 2:
        raise ValueError("Valhalla returned fewer than two route points")
    return points


class ValhallaRouteProvider(OpenRouteProvider):
    last_source = "valhalla"

    def __init__(self, nominatim_url: str, valhalla_url: str, timeout: float, user_agent: str):
        super().__init__(nominatim_url, valhalla_url, timeout, user_agent)
        self.valhalla_url = valhalla_url.rstrip("/")

    async def alternatives(
        self,
        origin: str,
        destination: str,
        exclude_polygons: list[list[list[float]]] | None = None,
    ) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                origin_point = await self._geocode(client, origin)
                destination_point = await self._geocode(client, destination)
                payload = {
                    "locations": [
                        {"lat": latitude, "lon": longitude, "type": "break"}
                        for latitude, longitude in (origin_point, destination_point)
                    ],
                    "costing": "auto",
                    "units": "kilometers",
                    "alternates": 2,
                    "shape_format": "polyline6",
                }
                if exclude_polygons:
                    # Top-level parameter, exterior rings in [lon, lat] order.
                    # Roads intersecting these rings are avoided in pathfinding.
                    payload["exclude_polygons"] = exclude_polygons
                response = await client.post(
                    f"{self.valhalla_url}/route",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                body = response.json()
            trips = [body["trip"], *[item["trip"] for item in body.get("alternates", [])[:2]]]
            routes = []
            for index, trip in enumerate(trips, start=1):
                if trip.get("status", 0) != 0:
                    raise ValueError("Valhalla could not build a driveable route")
                summary = trip["summary"]
                seconds, distance = float(summary["time"]), float(summary["length"])
                if not all(math.isfinite(value) and value > 0 for value in (seconds, distance)):
                    raise ValueError("Invalid Valhalla route duration or distance")
                if trip.get("units", "kilometers") not in {"kilometers", "miles"}:
                    raise ValueError("Unexpected Valhalla distance units")
                if trip.get("units") == "miles":
                    distance *= 1.609344
                geometry = []
                names = []
                steps = []
                for leg in trip["legs"]:
                    points = decode_polyline6(leg["shape"])
                    for maneuver in leg.get("maneuvers", []):
                        for name in maneuver.get("street_names", []):
                            if isinstance(name, str) and name and name not in names:
                                names.append(name)
                        parsed = _valhalla_step(maneuver, points)
                        if parsed:
                            steps.append(parsed)
                    geometry.extend(points[1:] if geometry and geometry[-1] == points[0] else points)
                if len(geometry) < 2:
                    raise ValueError("Valhalla returned no route geometry")
                routes.append({
                    "id": f"valhalla-route-{index}",
                    "name": " / ".join(names[:2]) or f"Road Alternative {index}",
                    "duration_minutes": max(1, round(seconds / 60)),
                    "distance_km": round(distance, 1),
                    "geometry": geometry,
                    "steps": steps,
                })
            return routes
        except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as exc:
            raise ValueError("Malformed Valhalla routing response") from exc
