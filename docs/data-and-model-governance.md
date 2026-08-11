# Data and model governance

## Current decision

SafeRoute AI does not ship a trained safety model. The repository has no licensed, representative real-world dataset linking prediction-time route conditions to a well-defined future safety outcome. Training on demonstration incidents would create invalid accuracy claims and geographic bias. The checked-in pipeline therefore evaluates the transparent deterministic baseline and fails closed at the training gate.

## Reproducible pipeline

Run:

```bash
python scripts/evaluate-risk-data.py --check
```

The pipeline verifies the dataset SHA-256 digest, source and licence metadata, allowed uses, schema, required values, unique event IDs, feature ranges, time coverage, both outcome classes, and suspicious leakage terms. It creates chronological 60/20/20 train, calibration, and test partitions; no random split can place future observations into training.

Evaluation reports Brier score, log loss, ROC AUC when both classes exist, calibration bins, expected calibration error, geographic subgroup metrics, and day/night subgroup metrics. The report is canonical JSON committed beside the dataset, so CI can detect unexplained data or evaluation drift.

## Demo dataset

`demo-risk-events-v1.csv` contains only manually authored synthetic scenarios and is released as CC0-1.0. It is suitable for testing, evaluation, and demonstration, but its manifest does not permit training and the sample size is below the predeclared minimum. The pipeline consequently records blockers and emits no model artifact.

## Gate for a future trained candidate

Before any model is trained or deployed, a reviewed manifest must establish:

- a licence that explicitly permits training and the intended deployment;
- a prediction-time feature contract and a future outcome definition;
- collection methodology, spatial/temporal coverage, retention, and privacy basis;
- at least 1,000 validated rows as a software gate, plus a domain-justified power/sample analysis;
- missingness, duplication, class balance, coordinate quality, and leakage analysis;
- chronological and geographic holdouts rather than a random-only split;
- calibration, uncertainty, subgroup performance, and comparison with the deterministic baseline;
- model card, signed/versioned artifact, feature version, monitoring thresholds, and rollback criteria;
- human/domain review of whether the user-facing claim is supported.

The 1,000-row threshold is intentionally only a minimum automation guard, not evidence that the dataset is sufficient. The owner must approve any third-party dataset licence or cost before it enters the repository or pipeline.
