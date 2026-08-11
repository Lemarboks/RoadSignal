from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.risk.data_pipeline import (
    DataReadinessError,
    DatasetManifest,
    baseline_probability,
    evaluate,
    temporal_split,
    validate_dataset,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "data" / "risk" / "demo-risk-events-v1.manifest.json"


def test_demo_dataset_is_reproducible_but_cannot_train_production_model():
    report = evaluate(MANIFEST_PATH)

    assert report["quality"]["sha256_verified"] is True
    assert report["quality"]["rows"] == 40
    assert report["split"]["train"]["rows"] == 24
    assert report["split"]["calibration"]["rows"] == 8
    assert report["split"]["test"]["rows"] == 8
    assert report["baseline"]["test_metrics"]["auc"] is not None
    assert report["training_gate"]["eligible"] is False
    assert report["training_gate"]["artifact_emitted"] is False
    assert "dataset is synthetic demonstration data" in report["training_gate"]["blockers"]


def test_temporal_split_never_shuffles_future_records_into_training():
    records = [
        {"event_id": "later", "observed_at": "2026-01-03T00:00:00Z"},
        {"event_id": "first", "observed_at": "2026-01-01T00:00:00Z"},
        {"event_id": "middle", "observed_at": "2026-01-02T00:00:00Z"},
        {"event_id": "last", "observed_at": "2026-01-04T00:00:00Z"},
        {"event_id": "last-2", "observed_at": "2026-01-05T00:00:00Z"},
    ]
    split = temporal_split(records)

    assert split["train"][0]["event_id"] == "first"
    assert split["test"][-1]["event_id"] == "last-2"
    assert split["train"][-1]["observed_at"] < split["test"][0]["observed_at"]


def test_manifest_hash_tampering_fails_closed(tmp_path: Path):
    raw_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_data = MANIFEST_PATH.parent / raw_manifest["file"]
    copied_data = tmp_path / source_data.name
    copied_data.write_bytes(source_data.read_bytes() + b"\n")
    copied_manifest = tmp_path / MANIFEST_PATH.name
    copied_manifest.write_text(json.dumps(raw_manifest), encoding="utf-8")
    manifest = DatasetManifest.load(copied_manifest)

    with pytest.raises(DataReadinessError, match="hash"):
        validate_dataset(manifest, copied_manifest, [])


def test_higher_weighted_factors_increase_baseline_probability():
    low = {feature: "0.1" for feature in ("crime", "accident", "traffic", "weather", "road_condition", "community")}
    high = dict(low, crime="0.9", accident="0.8")

    assert baseline_probability(high) > baseline_probability(low)
