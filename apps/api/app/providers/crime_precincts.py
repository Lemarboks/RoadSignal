"""Per-precinct vehicle-crime exposure from published SAPS statistics.

The dataset is built offline by scripts/build_crime_dataset.py and committed as
a compact JSON file, so this provider needs no network call, no API key and no
geo dependencies -- it just answers "which police precinct is this point in,
and how much vehicle-directed crime is reported there".

Scope and limits, deliberately explicit because this feeds the heaviest weight
in the risk engine:
  * Counts are reported crime over a fixed 12-month window, not live data and
    not a prediction. They describe an area, never an individual.
  * Only vehicle-directed categories are used (carjacking, truck hijacking,
    vehicle theft, theft from a vehicle, robbery), so the figure reflects
    driving exposure rather than a general judgement about a neighbourhood.
  * Normalised by area rather than resident population: a driver passing
    through is exposed to what happens on those roads, and per-resident rates
    badly distort commercial districts with large commuter populations.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "crime_precincts.json"
DEFAULT_BASELINE = 8.0


@lru_cache(maxsize=1)
def _dataset() -> dict:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"precincts": [], "window": "", "source": "", "municipality": ""}


def _bbox(rings: list[list[list[float]]]) -> tuple[float, float, float, float]:
    xs = [point[0] for ring in rings for point in ring]
    ys = [point[1] for ring in rings for point in ring]
    return (min(xs), max(xs), min(ys), max(ys))


@lru_cache(maxsize=1)
def _indexed() -> list[tuple[tuple[float, float, float, float], dict]]:
    """Precincts paired with their bounding box, so most candidates are
    rejected by four comparisons before any ray casting happens."""
    return [(_bbox(p["rings"]), p) for p in _dataset().get("precincts", []) if p.get("rings")]


def _point_in_rings(longitude: float, latitude: float, rings: list[list[list[float]]]) -> bool:
    inside = False
    for ring in rings:
        count = len(ring)
        j = count - 1
        for i in range(count):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > latitude) != (yj > latitude):
                crossing = (xj - xi) * (latitude - yi) / (yj - yi) + xi
                if longitude < crossing:
                    inside = not inside
            j = i
    return inside


class CrimePrecinctProvider:
    """Static lookup of reported vehicle crime by police precinct."""

    def __init__(self, default_baseline: float = DEFAULT_BASELINE):
        self.default_baseline = default_baseline

    @property
    def available(self) -> bool:
        return bool(_indexed())

    @property
    def metadata(self) -> dict:
        data = _dataset()
        return {
            "source": data.get("source", ""),
            "municipality": data.get("municipality", ""),
            "window": data.get("window", ""),
            "months": data.get("months"),
            "categories": sorted(data.get("category_weights", {})),
            "precinct_count": len(data.get("precincts", [])),
        }

    def precinct_at(self, latitude: float, longitude: float) -> dict | None:
        for (min_x, max_x, min_y, max_y), precinct in _indexed():
            if min_x <= longitude <= max_x and min_y <= latitude <= max_y:
                if _point_in_rings(longitude, latitude, precinct["rings"]):
                    return precinct
        return None

    def baseline_at(self, latitude: float, longitude: float) -> float:
        """Crime baseline for the risk engine. Outside the covered
        municipality this returns the previous hand-tuned default, so routes
        beyond the dataset score exactly as they did before."""
        precinct = self.precinct_at(latitude, longitude)
        if not precinct:
            return self.default_baseline
        return float(precinct.get("crime_baseline", self.default_baseline))

    def summarise_route(self, geometry: list[tuple[float, float]]) -> dict:
        """Which precincts a route passes through, worst first."""
        seen: dict[str, dict] = {}
        for latitude, longitude in geometry:
            precinct = self.precinct_at(latitude, longitude)
            if precinct:
                seen[precinct["code"]] = precinct
        ranked = sorted(seen.values(), key=lambda p: p.get("crime_baseline", 0), reverse=True)
        return {
            "precincts": [
                {
                    "code": p["code"],
                    "name": p["name"],
                    "per_km2": p.get("per_km2"),
                    "crime_baseline": p.get("crime_baseline"),
                }
                for p in ranked
            ],
            "worst": ranked[0]["name"] if ranked else None,
        }

    def layer(self) -> list[dict]:
        """Precinct outlines plus figures, for the map layer."""
        return [
            {
                "code": p["code"],
                "name": p["name"],
                "rings": p["rings"],
                "per_km2": p.get("per_km2"),
                "rate_per_100k": p.get("rate_per_100k"),
                "percentile": p.get("percentile"),
                "crime_baseline": p.get("crime_baseline"),
                "weighted_incidents": p.get("weighted_incidents"),
                "breakdown": p.get("breakdown", {}),
                "population": p.get("population"),
                "area_km2": p.get("area_km2"),
            }
            for p in _dataset().get("precincts", [])
        ]
