from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.risk.data_pipeline import DataReadinessError
from app.risk.training import evaluate_predictions, probability_metrics, train_candidate, training_partitions


MANIFEST = Path(__file__).resolve().parents[3] / "data/risk/demo-risk-events-v1.manifest.json"


def rows_for_partition_testing():
    # Split invariants use toy rows, never train a model or pass the data gate.
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "event_id": f"{area}-{index}",
            "observed_at": (start + timedelta(hours=4 * index)).isoformat(),
            "area": area,
            "outcome_hazard": index % 2,
            "hour": index % 24,
        }
        for area in ("development", "held-out")
        for index in range(200)
    ]


def test_demo_training_fails_closed_without_emitting_artifact(tmp_path):
    destination = tmp_path / "candidate"
    with pytest.raises(DataReadinessError, match="synthetic demonstration data"):
        train_candidate(MANIFEST, destination, "Cape Town")
    assert not destination.exists()


def test_training_partitions_exclude_geography_and_purge_future_outcome_windows():
    splits = training_partitions(rows_for_partition_testing(), "held-out", 8)
    for name in ("train", "calibration", "test"):
        assert {row["area"] for row in splits[name]} == {"development"}
    assert {row["area"] for row in splits["geographic_test"]} == {"held-out"}
    for before, after in (("train", "calibration"), ("calibration", "test")):
        last = datetime.fromisoformat(splits[before][-1]["observed_at"])
        first = datetime.fromisoformat(splits[after][0]["observed_at"])
        assert last + timedelta(hours=8) < first
    assert splits["geographic_test"][0]["observed_at"] >= splits["test"][0]["observed_at"]


def test_training_partitions_reject_absent_area_and_single_class_holdouts():
    rows = rows_for_partition_testing()
    with pytest.raises(DataReadinessError, match="existing area"):
        training_partitions(rows, "missing-area", 8)
    for row in rows:
        if row["area"] == "held-out":
            row["outcome_hazard"] = 0
    with pytest.raises(DataReadinessError, match="geographic_test requires both"):
        training_partitions(rows, "held-out", 8)


def test_probability_metrics_include_calibration_and_subgroups():
    rows = [
        {"outcome_hazard": 0, "area": "A", "hour": 12},
        {"outcome_hazard": 1, "area": "B", "hour": 22},
    ]
    result = evaluate_predictions(rows, [0.2, 0.8])
    assert result["metrics"]["brier"] == 0.04
    assert result["metrics"]["auc"] == 1.0
    assert result["metrics"]["expected_calibration_error"] == 0.2
    assert set(result["subgroups"]) == {"area:A", "area:B", "period:day", "period:night"}
    assert result["subgroups"]["area:A"]["auc"] is None
    with pytest.raises(ValueError, match="finite"):
        probability_metrics(rows, [float("nan"), 0.5])


def test_training_rejects_naive_timestamps():
    rows = rows_for_partition_testing()
    rows[0]["observed_at"] = "2026-01-01T00:00:00"
    with pytest.raises(DataReadinessError, match="timezone"):
        training_partitions(rows, "held-out", 8)
