"""Offline candidate training, gated by provenance and a reviewed data manifest.

Run from apps/api with ``python -m app.risk.training --help``. No route handler
loads these artifacts; an offline evaluation is never a deployment approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from .data_pipeline import (
    FEATURES,
    DataReadinessError,
    DatasetManifest,
    _auc,
    _parse_time,
    baseline_probability,
    canonical_json,
    evaluate,
    load_records,
    temporal_split,
)


REVIEW_FIELDS = (
    "reviewer",
    "reviewed_at",
    "collection_methodology",
    "privacy_basis",
    "sample_size_rationale",
    "feature_leakage_review",
)


def training_partitions(
    records: list[dict[str, Any]], geographic_holdout: str, prediction_horizon_hours: int
) -> dict[str, list[dict[str, Any]]]:
    """Reserve a geography and purge overlapping outcome windows at time splits."""
    if prediction_horizon_hours < 1:
        raise DataReadinessError("A positive future prediction horizon is required")
    spatial = [row for row in records if row["area"] == geographic_holdout]
    development = [row for row in records if row["area"] != geographic_holdout]
    if not spatial or not development:
        raise DataReadinessError("Geographic holdout must reserve an existing area and leave development data")
    try:
        if any(_parse_time(row["observed_at"]).tzinfo is None for row in records):
            raise DataReadinessError("Training timestamps must include a timezone")
        splits = temporal_split(development)
        if not all(splits.values()):
            raise DataReadinessError("Temporal partitions must be nonempty")
        calibration_start = _parse_time(splits["calibration"][0]["observed_at"])
        test_start = _parse_time(splits["test"][0]["observed_at"])
        horizon = timedelta(hours=prediction_horizon_hours)
        splits["train"] = [
            row for row in splits["train"]
            if _parse_time(row["observed_at"]) + horizon < calibration_start
        ]
        splits["calibration"] = [
            row for row in splits["calibration"]
            if _parse_time(row["observed_at"]) + horizon < test_start
        ]
        # Report the unseen area's performance in the same future test period.
        splits["geographic_test"] = sorted(
            [row for row in spatial if _parse_time(row["observed_at"]) >= test_start],
            key=lambda row: (_parse_time(row["observed_at"]), row["event_id"]),
        )
    except (TypeError, ValueError) as exc:
        raise DataReadinessError(f"Invalid temporal holdout: {exc}") from exc
    for name, rows in splits.items():
        if len(rows) < 20:
            raise DataReadinessError(f"{name} requires at least 20 rows after holdout and outcome-window purging")
        if {int(row["outcome_hazard"]) for row in rows} != {0, 1}:
            raise DataReadinessError(f"{name} requires both outcome classes")
    return splits


def probability_metrics(rows: list[dict[str, Any]], probabilities: list[float]) -> dict[str, Any]:
    if len(rows) != len(probabilities) or not rows:
        raise ValueError("Predictions must align with a nonempty evaluation partition")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("Evaluation probabilities must be finite and in 0..1")
    labels = [int(row["outcome_hazard"]) for row in rows]
    clipped = [min(1 - 1e-12, max(1e-12, value)) for value in probabilities]
    grouped: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for probability, label in zip(probabilities, labels):
        grouped[min(9, int(probability * 10))].append((probability, label))
    bins = []
    error = 0.0
    for index, values in sorted(grouped.items()):
        mean_prediction = sum(value[0] for value in values) / len(values)
        observed_rate = sum(value[1] for value in values) / len(values)
        error += len(values) / len(rows) * abs(mean_prediction - observed_rate)
        bins.append({
            "lower": index / 10,
            "upper": (index + 1) / 10,
            "rows": len(values),
            "mean_prediction": round(mean_prediction, 6),
            "observed_rate": round(observed_rate, 6),
        })
    auc = _auc(labels, probabilities)
    return {
        "rows": len(rows),
        "positive_rate": round(sum(labels) / len(rows), 6),
        "brier": round(sum((value - label) ** 2 for value, label in zip(probabilities, labels)) / len(rows), 6),
        "log_loss": round(-sum(
            label * math.log(value) + (1 - label) * math.log(1 - value)
            for value, label in zip(clipped, labels)
        ) / len(rows), 6),
        "auc": None if auc is None else round(auc, 6),
        "expected_calibration_error": round(error, 6),
        "calibration_bins": bins,
    }


def evaluate_predictions(rows: list[dict[str, Any]], probabilities: list[float]) -> dict[str, Any]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[f"area:{row['area']}"].append(index)
        hour = int(row["hour"])
        groups["period:night" if hour < 6 or hour >= 20 else "period:day"].append(index)
    return {
        "metrics": probability_metrics(rows, probabilities),
        "subgroups": {
            name: probability_metrics([rows[index] for index in indices], [probabilities[index] for index in indices])
            for name, indices in sorted(groups.items())
        },
    }


def train_candidate(manifest_path: Path, output_dir: Path, geographic_holdout: str) -> dict[str, Any]:
    report = evaluate(manifest_path)
    if not report["training_gate"]["eligible"]:
        raise DataReadinessError("Training blocked: " + "; ".join(report["training_gate"]["blockers"]))
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = raw_manifest.get("training_review", {})
    if not isinstance(review, dict) or review.get("approved") is not True:
        raise DataReadinessError("Manifest requires training_review.approved=true from a domain/data reviewer")
    if any(not isinstance(review.get(field), str) or not review[field].strip() for field in REVIEW_FIELDS):
        raise DataReadinessError("training_review requires: " + ", ".join(REVIEW_FIELDS))
    try:
        reviewed_at = _parse_time(review["reviewed_at"])
        if reviewed_at.tzinfo is None or reviewed_at > datetime.now(timezone.utc):
            raise ValueError("review timestamp must include a timezone and cannot be in the future")
    except ValueError as exc:
        raise DataReadinessError(f"Invalid training review: {exc}") from exc
    manifest = DatasetManifest.load(manifest_path)
    if not manifest.source.strip() or not manifest.outcome_definition.strip():
        raise DataReadinessError("Source and future outcome definition are required for training")
    records = load_records((manifest_path.parent / manifest.file).resolve())
    splits = training_partitions(records, geographic_holdout, manifest.prediction_horizon_hours)
    if output_dir.exists():
        raise DataReadinessError("Output directory already exists; use a new versioned candidate directory")

    # Import heavyweight packages only after every data gate passes.
    try:
        import numpy as np
        from sklearn.isotonic import IsotonicRegression
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise DataReadinessError("Install apps/api/requirements-training.txt to train an offline candidate") from exc

    def features(rows):
        return np.asarray([[float(row[feature]) for feature in FEATURES] for row in rows], dtype=np.float32)

    model = XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        min_child_weight=5,
        subsample=1.0,
        colsample_bytree=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        monotone_constraints=tuple(1 for _ in FEATURES),
        tree_method="hist",
        random_state=42,
        n_jobs=1,
    )
    model.fit(features(splits["train"]), [int(row["outcome_hazard"]) for row in splits["train"]])
    calibrator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip", increasing=True)
    calibration_predictions = model.predict_proba(features(splits["calibration"]))[:, 1]
    calibrator.fit(calibration_predictions, [int(row["outcome_hazard"]) for row in splits["calibration"]])
    evaluations = {}
    for name in ("test", "geographic_test"):
        rows = splits[name]
        raw = model.predict_proba(features(rows))[:, 1]
        calibrated = calibrator.predict(raw).tolist()
        evaluations[name] = {
            "baseline": evaluate_predictions(rows, [baseline_probability(row) for row in rows]),
            "candidate_uncalibrated": evaluate_predictions(rows, raw.tolist()),
            "candidate_calibrated": evaluate_predictions(rows, calibrated),
        }
    candidate_report = {
        "schema_version": 1,
        "status": "offline_candidate_only",
        "production_approved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": report["dataset"],
        "dataset_sha256": manifest.sha256,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "training_review": review,
        "feature_version": "risk_prediction_time_v1",
        "features": list(FEATURES),
        "monotonic_constraints": {feature: 1 for feature in FEATURES},
        "geographic_holdout": geographic_holdout,
        "prediction_horizon_hours": manifest.prediction_horizon_hours,
        "outcome_window_purging": True,
        "partitions": {
            name: {"rows": len(rows), "start": rows[0]["observed_at"], "end": rows[-1]["observed_at"]}
            for name, rows in splits.items()
        },
        "evaluation": evaluations,
        "packages": {name: version(name) for name in ("xgboost", "scikit-learn", "numpy")},
        "limitations": [
            "Held-out evaluation does not establish safety or justify deployment.",
            "Sparse subgroup estimates require domain review and uncertainty analysis.",
            "Artifact hashes establish integrity, not reviewer signatures or deployment approval.",
            "Serving, signed promotion, monitoring thresholds and rollback approval are separate gates.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    model_path = output_dir / "model.json"
    model.save_model(model_path)
    calibration_path = output_dir / "calibration.json"
    calibration_path.write_text(canonical_json({
        "method": "isotonic_linear_interpolation",
        "out_of_bounds": "clip",
        "x_thresholds": calibrator.X_thresholds_.tolist(),
        "y_thresholds": calibrator.y_thresholds_.tolist(),
    }), encoding="utf-8")
    candidate_report["artifact_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (model_path, calibration_path)
    }
    (output_dir / "evaluation.json").write_text(canonical_json(candidate_report), encoding="utf-8")
    (output_dir / "model-card.md").write_text(
        "# Offline RoadSignal risk candidate\n\n"
        f"Dataset: {manifest.dataset_id} / {manifest.version}.\n\n"
        f"Future outcome: {manifest.outcome_definition}.\n\n"
        f"Unseen geographic test area: {geographic_holdout}.\n\n"
        "This candidate is not approved for route scoring or safety claims. "
        "See evaluation.json for temporal and geographic holdouts, baseline comparisons, "
        "calibration, subgroup metrics, provenance, constraints and limitations. "
        "No live application code loads this model.\n",
        encoding="utf-8",
    )
    return candidate_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--geographic-holdout", required=True, help="Entire area reserved from model and calibration fitting")
    arguments = parser.parse_args()
    try:
        result = train_candidate(arguments.manifest, arguments.output_dir, arguments.geographic_holdout)
    except (DataReadinessError, OSError, KeyError, ValueError) as exc:
        print(canonical_json({"status": "blocked", "reason": str(exc), "production_approved": False}))
        return 2
    print(canonical_json({
        "status": result["status"],
        "output_dir": str(arguments.output_dir.resolve()),
        "production_approved": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
