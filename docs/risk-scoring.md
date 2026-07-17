# Risk scoring

Risk is deterministic. Each geographic route segment starts at 100. Penalties use crime 35%, accident 25%, traffic 15%, weather 10%, road condition 10%, and community 5%. Incident impact is `severity × confidence × recency decay × distance decay × route relevance`. Values are clamped to 0–100.

Route score is `0.50 × average segments + 0.30 × worst segment + 0.20 × confidence-adjusted average`. Recommendation utility combines safety and time efficiency: safest 90/10, balanced 75/25, fastest 35/65. Explanations are templates populated from the structured factor breakdown; no language model invents scores.

Confidence separately considers reporter trust, proximity, account age, history, confirmations/disputes, evidence, independent matches, age, and duplicates. Abuse flags cover likely duplicates, distant reporters, and excessive reporting. See `apps/api/app/risk/engine.py` and its unit tests.
