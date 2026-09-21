"""Historical crash risk per precinct, from City of Cape Town open data.

The risk engine weights "accident" at 0.25 but, before this, nothing supplied
an accident baseline -- the channel only moved when a user reported something.
A stretch of road with six years of fatal crashes therefore scored exactly
like a quiet suburban street until somebody filed a report.

This fills that channel with 377,996 recorded crashes (2019-2024), joined to
the SAPS precinct polygons already shipped for the crime layer. Two things it
deliberately does:

  * Weighs outcome, not just frequency. Philippi East records fewer crashes
    than Cape Town Central but far more deaths, and ranks accordingly.
  * Varies by departure time. Crash rates per hour peak during the commute and
    fall away overnight, so a 17:00 Friday trip is not scored like a 02:00 one.

Rebuild the dataset with scripts/build_crash_dataset.py.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "crash_history.json"

# Matches the band edges in scripts/build_crash_dataset.py. Kept as (start
# hour, name) so the lookup is a simple descending scan.
_BANDS = [
    (19, "evening"),
    (16, "evening_peak"),
    (12, "afternoon"),
    (9, "midmorning"),
    (6, "morning_peak"),
    (0, "late_night"),
]


@lru_cache(maxsize=1)
def _dataset() -> dict:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def band_for(when: datetime) -> str:
    for start, name in _BANDS:
        if when.hour >= start:
            return name
    return "late_night"


def slot_for(when: datetime) -> str:
    return f"{when.strftime('%A')}|{band_for(when)}"


class CrashHistoryProvider:
    """Accident baseline from recorded crash history.

    Takes the precinct locator (the crime provider) rather than carrying its
    own copy of the polygons -- same boundaries, same point-in-polygon code,
    one source of truth.
    """

    source = "City of Cape Town crash records 2019-2024"

    def __init__(self, precinct_locator, default_baseline: float = 0.0):
        self.precinct_locator = precinct_locator
        # Zero rather than a guess: outside the covered municipality there is
        # no crash history, and inventing one would move scores on no evidence.
        self.default_baseline = default_baseline

    @property
    def available(self) -> bool:
        return bool(_dataset().get("precincts"))

    @property
    def metadata(self) -> dict:
        data = _dataset()
        if not data:
            return {"available": False}
        return {
            "available": True,
            "source": data.get("source"),
            "source_terms": data.get("source_terms"),
            "window": data.get("window"),
            "crashes": data.get("joined_crashes"),
            # Named precinct_count, not precincts: the endpoint spreads this
            # metadata alongside the precincts array and a colliding key would
            # silently replace the list with an integer.
            "precinct_count": len(data.get("precincts", {})),
            "baseline_range": data.get("baseline_range"),
        }

    def _record(self, latitude: float, longitude: float) -> dict | None:
        precinct = self.precinct_locator.precinct_at(latitude, longitude)
        if not precinct:
            return None
        return _dataset().get("precincts", {}).get(precinct.get("name"))

    def baseline_at(
        self, latitude: float, longitude: float, when: datetime | None = None
    ) -> float:
        """Accident baseline for this point, optionally for a departure time."""
        record = self._record(latitude, longitude)
        if not record:
            return self.default_baseline
        baseline = float(record.get("accident_baseline", self.default_baseline))
        if when is None:
            return baseline
        # A slot with too few crashes to be trustworthy has no multiplier, and
        # the unadjusted baseline stands.
        multiplier = record.get("slot_multipliers", {}).get(slot_for(when))
        if not multiplier:
            return baseline
        maximum = float((_dataset().get("baseline_range") or [0, 26])[1])
        return round(min(maximum, baseline * float(multiplier)), 2)

    def detail_at(
        self, latitude: float, longitude: float, when: datetime | None = None
    ) -> dict | None:
        """What the score is based on, for showing a driver the evidence."""
        record = self._record(latitude, longitude)
        if not record:
            return None
        precinct = self.precinct_locator.precinct_at(latitude, longitude)
        slot = slot_for(when) if when else None
        return {
            "precinct": precinct.get("name") if precinct else None,
            "crashes": record.get("crashes"),
            "fatal": record.get("fatal"),
            "serious": record.get("serious"),
            "pedestrians": record.get("pedestrians"),
            "percentile": record.get("percentile"),
            "accident_baseline": self.baseline_at(latitude, longitude, when),
            "slot": slot,
            "slot_multiplier": record.get("slot_multipliers", {}).get(slot) if slot else None,
        }

    def summarise_route(
        self, geometry: list[tuple[float, float]], when: datetime | None = None
    ) -> dict:
        """The worst precincts a route passes through, by crash history."""
        seen: dict[str, dict] = {}
        for latitude, longitude in geometry:
            detail = self.detail_at(latitude, longitude, when)
            if detail and detail.get("precinct"):
                seen[detail["precinct"]] = detail
        ranked = sorted(
            seen.values(), key=lambda item: item.get("accident_baseline") or 0, reverse=True
        )
        data = _dataset()
        return {
            "available": self.available,
            "source": data.get("source"),
            "window": data.get("window"),
            "slot": slot_for(when) if when else None,
            "precincts": ranked[:5],
        }

    def layer(self) -> list[dict]:
        """Map layer: crash history per precinct, with its boundary."""
        entries = []
        for precinct in self.precinct_locator.layer():
            record = _dataset().get("precincts", {}).get(precinct.get("name"))
            if not record:
                continue
            entries.append(
                {
                    # Same code the crime layer uses, so the map can feed one
                    # precinct source from either dataset.
                    "code": precinct.get("code"),
                    "name": precinct.get("name"),
                    "rings": precinct.get("rings"),
                    "crashes": record.get("crashes"),
                    "fatal": record.get("fatal"),
                    "serious": record.get("serious"),
                    "pedestrians": record.get("pedestrians"),
                    "percentile": record.get("percentile"),
                    "accident_baseline": record.get("accident_baseline"),
                }
            )
        return entries
