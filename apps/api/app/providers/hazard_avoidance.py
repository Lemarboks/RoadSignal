"""Turn live hazards into routing exclusion zones.

Everything else in RoadSignal scores a route after the fact: a wildfire or a
high-crime precinct lowers a number, but the road itself is still suggested.
This builds the polygons needed to route *around* those areas instead, which
Valhalla supports natively via its top-level `exclude_polygons` parameter
(one or more exterior rings, [lon, lat] ordering; Valhalla closes open rings).

Point hazards become small circular rings. Precinct hazards reuse the polygon
already published by the crime dataset. Deliberately conservative: excluding
too much geography makes routing fail or produce absurd detours, so radii are
small and only the worst precincts qualify.

Hard constraint discovered against a real Valhalla instance: it rejects the
whole request with `error_code 167` once the *combined* circumference of all
exclusion rings exceeds 10km. That is a tight budget -- a single 1.5km-radius
circle is already ~9.4km of circumference -- so rings are kept small and are
admitted greedily, worst hazard first, until the budget is spent.
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0
# Valhalla's limit is 10,000m of total circumference; stay clear of the edge.
DEFAULT_CIRCUMFERENCE_BUDGET_M = 9_000.0


def ring_circumference_m(ring: list[list[float]]) -> float:
    """Perimeter of a [lon, lat] ring in metres."""
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring, ring[1:]):
        mean_latitude = math.radians((lat1 + lat2) / 2)
        dx = math.radians(lon2 - lon1) * math.cos(mean_latitude)
        dy = math.radians(lat2 - lat1)
        total += math.hypot(dx, dy) * EARTH_RADIUS_KM * 1000
    return total


def circle_ring(latitude: float, longitude: float, radius_km: float, segments: int = 12) -> list[list[float]]:
    """A closed ring approximating a circle, in [lon, lat] order for Valhalla."""
    ring: list[list[float]] = []
    latitude_radians = math.radians(latitude)
    # Degrees per km differ by axis, and longitude converges toward the poles.
    degrees_latitude = (radius_km / EARTH_RADIUS_KM) * (180 / math.pi)
    cosine = max(math.cos(latitude_radians), 1e-6)
    degrees_longitude = degrees_latitude / cosine
    for index in range(segments):
        angle = 2 * math.pi * index / segments
        ring.append([
            round(longitude + degrees_longitude * math.cos(angle), 6),
            round(latitude + degrees_latitude * math.sin(angle), 6),
        ])
    ring.append(ring[0])
    return ring


class HazardAvoidanceBuilder:
    """Collects exclusion rings from the hazard providers."""

    def __init__(
        self,
        wildfire_provider,
        severe_event_provider,
        crime_provider,
        wildfire_radius_km: float = 0.6,
        severe_event_radius_km: float = 0.8,
        crime_percentile: float = 0.9,
        max_polygons: int = 40,
        circumference_budget_m: float = DEFAULT_CIRCUMFERENCE_BUDGET_M,
    ):
        self.wildfire_provider = wildfire_provider
        self.severe_event_provider = severe_event_provider
        self.crime_provider = crime_provider
        self.wildfire_radius_km = wildfire_radius_km
        self.severe_event_radius_km = severe_event_radius_km
        self.crime_percentile = crime_percentile
        self.max_polygons = max_polygons
        self.circumference_budget_m = circumference_budget_m

    async def build(self, include_crime: bool = False) -> tuple[list[list[list[float]]], list[str]]:
        """Return (exclude_polygons, human-readable reasons).

        Crime precincts are opt-in and off by default. Excluding whole
        residential precincts from routing is a far heavier intervention than
        avoiding an active fire, and it should be a deliberate choice by the
        operator rather than a silent default.
        """
        # (label, ring) in priority order: an active fire outranks a storm,
        # which outranks a statistical crime rate.
        candidates: list[tuple[str, list[list[float]]]] = []

        try:
            hotspots = await self.wildfire_provider.hotspots()
        except Exception:
            hotspots = []
        for hotspot in hotspots:
            candidates.append((
                "wildfire",
                circle_ring(hotspot["latitude"], hotspot["longitude"], self.wildfire_radius_km),
            ))

        try:
            events = await self.severe_event_provider.events()
        except Exception:
            events = []
        for event in events:
            candidates.append((
                "severe weather",
                circle_ring(event["latitude"], event["longitude"], self.severe_event_radius_km),
            ))

        worst_precincts = 0
        if include_crime and getattr(self.crime_provider, "available", False):
            worst = sorted(
                (
                    precinct
                    for precinct in self.crime_provider.layer()
                    if (precinct.get("percentile") or 0) >= self.crime_percentile
                ),
                key=lambda precinct: precinct.get("percentile") or 0,
                reverse=True,
            )
            worst_precincts = len(worst)
            for precinct in worst:
                for ring in precinct.get("rings", []):
                    # The dataset already stores [lon, lat]; Valhalla wants the same.
                    candidates.append(("crime precinct", [[point[0], point[1]] for point in ring]))

        # Admit rings greedily until the circumference budget is spent.
        polygons: list[list[list[float]]] = []
        admitted: dict[str, int] = {}
        skipped: dict[str, int] = {}
        used = 0.0
        for label, ring in candidates:
            circumference = ring_circumference_m(ring)
            if len(polygons) >= self.max_polygons or used + circumference > self.circumference_budget_m:
                skipped[label] = skipped.get(label, 0) + 1
                continue
            polygons.append(ring)
            used += circumference
            admitted[label] = admitted.get(label, 0) + 1

        reasons = [f"{count} {label} zone(s) avoided" for label, count in admitted.items()]
        if worst_precincts and "crime precinct" in admitted:
            reasons.append(f"precincts above the {self.crime_percentile:.0%} vehicle-crime percentile")
        for label, count in skipped.items():
            reasons.append(
                f"{count} {label} zone(s) omitted: Valhalla allows only "
                f"{self.circumference_budget_m / 1000:.0f}km of total exclusion perimeter"
            )
        if polygons:
            reasons.append(f"{used / 1000:.1f}km of {self.circumference_budget_m / 1000:.0f}km perimeter budget used")

        return polygons, reasons
