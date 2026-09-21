"""Crash history as the accident baseline.

The risk engine weights "accident" at 0.25 but nothing fed it a baseline, so
six years of recorded crashes had no effect on a score until someone filed a
report. These tests cover the dataset being real, the time-of-day dimension
actually reaching the score, and the honesty boundaries: no invented baseline
outside the covered area, and no score movement on an untrustworthy sample.
"""
from datetime import datetime, timezone

import pytest

from app.providers.crash_history import CrashHistoryProvider, band_for, slot_for

CBD = (-33.9249, 18.4241)
MID_ATLANTIC = (-40.0, 0.0)  # far outside the municipality


@pytest.fixture
def provider():
    from app import services

    return services.crash_history_provider


def test_the_shipped_dataset_is_real_and_joined():
    from app import services

    meta = services.crash_history_provider.metadata
    assert meta["available"] is True
    # The builder refuses to write below an 85% join rate; assert we are well
    # clear of it rather than merely non-zero.
    assert meta["crashes"] > 300_000, "expected the full published crash record"
    assert meta["precinct_count"] >= 55
    assert "City of Cape Town" in meta["source"]


@pytest.mark.parametrize(
    "hour,expected",
    [(0, "late_night"), (5, "late_night"), (6, "morning_peak"), (8, "morning_peak"),
     (9, "midmorning"), (12, "afternoon"), (16, "evening_peak"), (18, "evening_peak"),
     (19, "evening"), (23, "evening")],
)
def test_every_hour_lands_in_the_documented_band(hour, expected):
    assert band_for(datetime(2026, 9, 25, hour, tzinfo=timezone.utc)) == expected


def test_the_slot_names_the_weekday_and_band():
    assert slot_for(datetime(2026, 9, 25, 17, tzinfo=timezone.utc)) == "Friday|evening_peak"


def test_a_known_precinct_has_a_baseline_backed_by_crashes(provider):
    detail = provider.detail_at(*CBD)
    assert detail["precinct"] == "Cape Town Central"
    assert detail["crashes"] > 10_000
    assert detail["accident_baseline"] > 0


def test_the_commute_scores_worse_than_the_small_hours(provider):
    """The whole point of the time dimension: crash rates peak on the commute."""
    quiet = provider.baseline_at(*CBD, datetime(2026, 9, 27, 2, tzinfo=timezone.utc))
    peak = provider.baseline_at(*CBD, datetime(2026, 9, 25, 17, tzinfo=timezone.utc))
    assert peak > quiet, "evening peak must not score safer than 02:00"


def test_outside_the_municipality_no_baseline_is_invented(provider):
    assert provider.baseline_at(*MID_ATLANTIC) == 0.0
    assert provider.detail_at(*MID_ATLANTIC) is None


def test_the_baseline_never_exceeds_the_documented_ceiling(provider):
    """A slot multiplier must not push a precinct off the published scale."""
    ceiling = provider.metadata["baseline_range"][1]
    for hour in range(24):
        when = datetime(2026, 9, 25, hour, tzinfo=timezone.utc)
        assert provider.baseline_at(*CBD, when) <= ceiling


def test_an_absent_dataset_reports_unavailable_rather_than_guessing():
    class NoPrecincts:
        def precinct_at(self, latitude, longitude):
            return None

        def layer(self):
            return []

    provider = CrashHistoryProvider(NoPrecincts())
    assert provider.baseline_at(*CBD) == 0.0
    assert provider.layer() == []


def test_outcome_is_weighted_not_just_frequency():
    """A precinct with fewer crashes but more deaths must rank above one with
    many minor collisions -- otherwise fender-benders drown out fatalities."""
    from app.providers.crash_history import _dataset

    precincts = _dataset()["precincts"]
    deadly = precincts.get("Philippi East")
    assert deadly, "expected Philippi East in the dataset"
    busier_but_safer = [
        name
        for name, record in precincts.items()
        if record["crashes"] > deadly["crashes"] * 1.5
        and record["fatal"] < deadly["fatal"] / 2
        and record["accident_baseline"] < deadly["accident_baseline"]
    ]
    assert busier_but_safer, (
        "no precinct with more crashes but far fewer deaths ranked below "
        "Philippi East, so severity is not influencing the ranking"
    )


def test_the_endpoint_returns_the_precinct_array_not_a_count():
    """Regression: metadata was spread over the response and a colliding
    "precincts" key replaced the array with an integer."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        body = client.get("/api/v1/hazards/crash-history").json()
    assert isinstance(body["precincts"], list), "precincts must stay an array"
    assert body["precincts"], "expected precincts in the response"
    assert isinstance(body["count"], int)
    first = body["precincts"][0]
    assert first["rings"], "the map layer needs boundary geometry"
    assert first["code"] and first["name"]


def test_the_route_cache_key_separates_departure_slots():
    """Guards the bug this feature originally shipped with: the cache keyed on
    origin/destination only, so a 02:00 score was served to a 17:00 request."""
    from app.routers.routes import slot_for as routes_slot

    quiet = routes_slot(datetime(2026, 9, 27, 2, tzinfo=timezone.utc))
    peak = routes_slot(datetime(2026, 9, 25, 17, tzinfo=timezone.utc))
    assert quiet != peak
