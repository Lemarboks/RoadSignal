from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


FEATURES = (
    "crime",
    "accident",
    "traffic",
    "weather",
    "road_condition",
    "community",
)
FORBIDDEN_FEATURE_TERMS = (
    "outcome",
    "target",
    "label",
    "future",
    "resolved_after",
    "post_event",
)
WEIGHTS = {
    "crime": 0.35,
    "accident": 0.25,
    "traffic": 0.15,
    "weather": 0.10,
    "road_condition": 0.10,
    "community": 0.05,
}


class DataReadinessError(ValueError):
    """Raised when a dataset cannot be evaluated safely."""


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    file: str
    sha256: str
    source: str
    license: str
    license_url: str
    allowed_use: tuple[str, ...]
    synthetic: bool
    geography: tuple[str, ...]
    observation_start: str
    observation_end: str
    outcome_definition: str
    prediction_horizon_hours: int
    features_available_at_prediction: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "DatasetManifest":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            dataset_id=raw["dataset_id"],
            version=raw["version"],
            file=raw["file"],
            sha256=raw["sha256"],
            source=raw["source"],
            license=raw["license"],
            license_url=raw["license_url"],
            allowed_use=tuple(raw["allowed_use"]),
            synthetic=bool(raw["synthetic"]),
            geography=tuple(raw["geography"]),
            observation_start=raw["observation_start"],
            observation_end=raw["observation_end"],
            outcome_definition=raw["outcome_definition"],
            prediction_horizon_hours=int(raw["prediction_horizon_hours"]),
            features_available_at_prediction=tuple(raw["features_available_at_prediction"]),
        )


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_dataset(
    manifest: DatasetManifest, manifest_path: Path, records: list[dict[str, Any]]
) -> dict[str, Any]:
    data_path = (manifest_path.parent / manifest.file).resolve()
    actual_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    errors: list[str] = []

    if actual_hash != manifest.sha256:
        errors.append("dataset hash does not match the manifest")
    if not manifest.license or not manifest.license_url:
        errors.append("license and license_url are required")
    if "evaluation" not in manifest.allowed_use:
        errors.append("manifest does not permit evaluation")
    if set(manifest.features_available_at_prediction) != set(FEATURES):
        errors.append("manifest prediction-time features do not match the evaluator")
    for feature in manifest.features_available_at_prediction:
        lowered = feature.lower()
        if any(term in lowered for term in FORBIDDEN_FEATURE_TERMS):
            errors.append(f"potential target leakage in feature: {feature}")

    ids: set[str] = set()
    parsed_times: list[datetime] = []
    class_counts: Counter[int] = Counter()
    area_counts: Counter[str] = Counter()
    latitudes: list[float] = []
    longitudes: list[float] = []
    missing = 0
    for row_number, row in enumerate(records, start=2):
        required = {"event_id", "observed_at", "area", "latitude", "longitude", "hour", "outcome_hazard", *FEATURES}
        absent = [field for field in required if row.get(field, "") == ""]
        if absent:
            missing += len(absent)
            errors.append(f"row {row_number} has missing fields: {', '.join(sorted(absent))}")
            continue
        if row["event_id"] in ids:
            errors.append(f"duplicate event_id: {row['event_id']}")
        ids.add(row["event_id"])
        try:
            observed_at = _parse_time(row["observed_at"])
            parsed_times.append(observed_at)
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            hour = int(row["hour"])
            outcome = int(row["outcome_hazard"])
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("coordinates outside WGS84 bounds")
            if not 0 <= hour <= 23:
                raise ValueError("hour outside 0..23")
            if outcome not in (0, 1):
                raise ValueError("outcome_hazard must be 0 or 1")
            for feature in FEATURES:
                value = float(row[feature])
                if not 0 <= value <= 1:
                    raise ValueError(f"{feature} outside 0..1")
        except (TypeError, ValueError) as exc:
            errors.append(f"row {row_number} is invalid: {exc}")
            continue
        class_counts[outcome] += 1
        area_counts[row["area"]] += 1
        latitudes.append(latitude)
        longitudes.append(longitude)

    if not records:
        errors.append("dataset is empty")
    if parsed_times:
        start = _parse_time(manifest.observation_start)
        end = _parse_time(manifest.observation_end)
        if min(parsed_times) < start or max(parsed_times) > end:
            errors.append("record timestamp falls outside manifest coverage")
    if len(class_counts) < 2:
        errors.append("both outcome classes are required")
    if errors:
        raise DataReadinessError("; ".join(errors))

    return {
        "rows": len(records),
        "unique_ids": len(ids),
        "missing_required_values": missing,
        "class_counts": {str(key): class_counts[key] for key in sorted(class_counts)},
        "area_counts": dict(sorted(area_counts.items())),
        "coordinate_bounds": {
            "min_latitude": min(latitudes),
            "max_latitude": max(latitudes),
            "min_longitude": min(longitudes),
            "max_longitude": max(longitudes),
        },
        "sha256_verified": True,
        "license_present": True,
        "leakage_name_check_passed": True,
    }


def temporal_split(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(records, key=lambda row: (_parse_time(row["observed_at"]), row["event_id"]))
    count = len(ordered)
    train_end = max(1, int(count * 0.60))
    calibration_end = max(train_end + 1, int(count * 0.80))
    return {
        "train": ordered[:train_end],
        "calibration": ordered[train_end:calibration_end],
        "test": ordered[calibration_end:],
    }


def baseline_probability(row: dict[str, Any]) -> float:
    weighted_risk = sum(float(row[feature]) * WEIGHTS[feature] for feature in FEATURES)
    return min(0.99, max(0.01, weighted_risk))


def _auc(labels: list[int], probabilities: list[float]) -> float | None:
    positive = [score for label, score in zip(labels, probabilities) if label == 1]
    negative = [score for label, score in zip(labels, probabilities) if label == 0]
    if not positive or not negative:
        return None
    wins = sum(1 if pos > neg else 0.5 if pos == neg else 0 for pos in positive for neg in negative)
    return wins / (len(positive) * len(negative))


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [int(row["outcome_hazard"]) for row in rows]
    probabilities = [baseline_probability(row) for row in rows]
    if not rows:
        return {"rows": 0, "positive_rate": None, "brier": None, "log_loss": None, "auc": None}
    brier = sum((probability - label) ** 2 for label, probability in zip(labels, probabilities)) / len(rows)
    log_loss = -sum(
        label * math.log(probability) + (1 - label) * math.log(1 - probability)
        for label, probability in zip(labels, probabilities)
    ) / len(rows)
    return {
        "rows": len(rows),
        "positive_rate": round(sum(labels) / len(labels), 6),
        "brier": round(brier, 6),
        "log_loss": round(log_loss, 6),
        "auc": None if (auc := _auc(labels, probabilities)) is None else round(auc, 6),
    }


def _calibration(rows: list[dict[str, Any]], bins: int = 5) -> dict[str, Any]:
    grouped: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for row in rows:
        probability = baseline_probability(row)
        grouped[min(bins - 1, int(probability * bins))].append(
            (probability, int(row["outcome_hazard"]))
        )
    output = []
    expected_error = 0.0
    for index in range(bins):
        values = grouped.get(index, [])
        if not values:
            continue
        mean_prediction = sum(item[0] for item in values) / len(values)
        observed_rate = sum(item[1] for item in values) / len(values)
        expected_error += len(values) / len(rows) * abs(mean_prediction - observed_rate)
        output.append(
            {
                "lower": round(index / bins, 2),
                "upper": round((index + 1) / bins, 2),
                "rows": len(values),
                "mean_prediction": round(mean_prediction, 6),
                "observed_rate": round(observed_rate, 6),
            }
        )
    return {"expected_calibration_error": round(expected_error, 6), "bins": output}


def _subgroups(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[f"area:{row['area']}"].append(row)
        hour = int(row["hour"])
        groups["period:night" if hour < 6 or hour >= 20 else "period:day"].append(row)
    return {name: _metrics(group) for name, group in sorted(groups.items())}


def evaluate(manifest_path: Path) -> dict[str, Any]:
    manifest = DatasetManifest.load(manifest_path)
    data_path = (manifest_path.parent / manifest.file).resolve()
    records = load_records(data_path)
    quality = validate_dataset(manifest, manifest_path, records)
    splits = temporal_split(records)
    test = splits["test"]
    minimum_rows_for_training = 1000
    eligible = (
        not manifest.synthetic
        and "training" in manifest.allowed_use
        and len(records) >= minimum_rows_for_training
    )
    blockers = []
    if manifest.synthetic:
        blockers.append("dataset is synthetic demonstration data")
    if "training" not in manifest.allowed_use:
        blockers.append("license manifest does not permit training")
    if len(records) < minimum_rows_for_training:
        blockers.append(f"fewer than {minimum_rows_for_training} validated rows")

    return {
        "schema_version": 1,
        "dataset": {
            "id": manifest.dataset_id,
            "version": manifest.version,
            "source": manifest.source,
            "license": manifest.license,
            "license_url": manifest.license_url,
            "synthetic": manifest.synthetic,
            "geography": list(manifest.geography),
            "observation_start": manifest.observation_start,
            "observation_end": manifest.observation_end,
            "outcome_definition": manifest.outcome_definition,
            "prediction_horizon_hours": manifest.prediction_horizon_hours,
        },
        "quality": quality,
        "split": {
            name: {
                "rows": len(rows),
                "start": rows[0]["observed_at"] if rows else None,
                "end": rows[-1]["observed_at"] if rows else None,
            }
            for name, rows in splits.items()
        },
        "baseline": {
            "name": "transparent_weighted_risk_v1",
            "test_metrics": _metrics(test),
            "calibration": _calibration(test),
            "subgroups": _subgroups(test),
        },
        "training_gate": {
            "eligible": eligible,
            "minimum_rows": minimum_rows_for_training,
            "blockers": blockers,
            "artifact_emitted": False,
        },
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
