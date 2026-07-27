---
name: saferoute-risk-audit
description: Audit SafeRoute AI risk scoring, incident confidence, route aggregation, evidence provenance, bias, stale data, adversarial reports, and safety wording. Use when changing scoring weights, incident moderation, explanations, route recommendations, risk tests, or claims shown to drivers and fleet users.
---

# SafeRoute risk audit

Review the model as decision support, not as a safety oracle.

## Audit sequence

1. Trace every input through incident confidence, distance decay, recency decay, segment scoring, and route aggregation.
2. Confirm monotonic behaviour: nearer, newer, more severe, and more credible evidence must not reduce the relevant penalty.
3. Test boundary cases: no incidents, duplicate incidents, stale reports, conflicting reports, extreme coordinates, one unsafe segment, and many low-confidence reports.
4. Check manipulation resistance: confirmation spam, dispute spam, anonymous flooding, duplicated sources, and strategic false locations.
5. Check geographic and reporting bias. Sparse reporting must lower confidence rather than imply safety.
6. Require factor snapshots and provenance for historical explanations.
7. Verify that recommendation copy distinguishes score, confidence, uncertainty, and travel-time trade-offs.
8. Require deterministic tests for every scoring change.

## Required output

List assumptions, invariants, tests examined, failure modes, severity, and specific remediation. Flag any wording that promises safety or conceals uncertainty as release-blocking.
