from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def risk_evidence() -> dict[str, Any]:
    artifact = files("app.risk.artifacts").joinpath("demo-risk-evaluation-v1.json")
    report = json.loads(artifact.read_text(encoding="utf-8"))
    return {
        "method": {
            "id": report["baseline"]["name"],
            "kind": "deterministic_baseline",
            "trained_model": False,
            "explainable": True,
            "version": "1.0.0",
        },
        "evaluation": {
            "dataset_id": report["dataset"]["id"],
            "dataset_version": report["dataset"]["version"],
            "synthetic": report["dataset"]["synthetic"],
            "rows": report["quality"]["rows"],
            "test_rows": report["baseline"]["test_metrics"]["rows"],
            "brier": report["baseline"]["test_metrics"]["brier"],
            "auc": report["baseline"]["test_metrics"]["auc"],
            "expected_calibration_error": report["baseline"]["calibration"][
                "expected_calibration_error"
            ],
            "license": report["dataset"]["license"],
            "sha256_verified": report["quality"]["sha256_verified"],
        },
        "training_gate": report["training_gate"],
        "claims": {
            "status": "evaluation_only",
            "summary": (
                "The transparent baseline is reproducibly evaluated on synthetic scenarios. "
                "These metrics do not establish real-world safety effectiveness."
            ),
            "disclaimer": (
                "Risk scores are decision-support estimates and do not guarantee safety."
            ),
        },
    }
