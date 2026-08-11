# Risk scoring

The current engine is deterministic and explainable; it is not a trained safety model. Each geographic route segment starts at 100. Baseline penalty weights are crime 35%, accident 25%, traffic 15%, weather 10%, road condition 10%, and community reports 5%.

An incident contribution is proportional to:

`severity * confidence * recency_decay * distance_decay * route_relevance`

Segment values are clamped to the range 0 to 100. Route score is:

`0.50 * segment_average + 0.30 * worst_segment + 0.20 * confidence_adjusted_average`

Recommendation utility combines safety and time efficiency: safest uses 90/10, balanced 75/25, and fastest 35/65. Explanations are templates populated from the structured factor breakdown; no language model invents scores.

Incident confidence separately considers reporter trust, proximity, account age, history, confirmations and disputes, evidence, independent matches, age, and likely duplicates. Abuse flags cover duplicates, distant reporters, and excessive reporting.

## Why this remains deterministic

The repository has no licensed, representative outcome dataset proving which routes were safe or unsafe. Training on demonstration incidents would create impressive-looking but invalid metrics, target leakage, geographic bias, and false confidence. The deterministic baseline is therefore the production candidate until the data-readiness gate in the planned pipeline passes.

## Model-readiness gate

A trained candidate must have documented source licences, event/outcome definitions, spatial and temporal coverage, missingness analysis, leakage checks, subgroup/geographic evaluation, time-split validation, calibration, uncertainty, baseline comparison, model-card limitations, versioned features, and rollback criteria. It must outperform the transparent baseline on predeclared metrics without making the user-facing safety claim stronger than the evidence.

Implementation and tests are in `apps/api/app/risk/engine.py` and `apps/api/tests/test_engines.py`.