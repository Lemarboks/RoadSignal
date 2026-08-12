# Operations runbook

This runbook defines initial operating targets for a small production portfolio deployment. They are starting objectives, not claims backed by real traffic. Revisit them after 30 days of representative measurements.

## Service objectives

| Signal | Initial objective | Measurement |
|---|---:|---|
| API availability | 99.5% monthly | Successful non-health API requests divided by valid requests |
| API latency | 95% under 750 ms | Prometheus route-template request histogram, excluding provider timeouts reported as errors |
| Route analysis latency | 95% under 5 seconds | Route-analysis histogram including configured provider time |
| Server error ratio | Under 1% over 15 minutes | HTTP 5xx responses divided by requests |
| Realtime freshness | 95% delivered within 5 seconds | Event publication time to client receipt, added when production clients emit privacy-safe acknowledgements |
| Recovery point | 24 hours or better | Age of newest verified off-host MySQL spatial backup |
| Recovery time | 4 hours | Time from declared database loss to verified service restoration |

The monthly availability error budget at 99.5% is about 3 hours 39 minutes. Pause feature releases when half the monthly budget is consumed in seven days or when backup verification is stale.

## Alert triage

1. Confirm impact through `/api/v1/health`, `/api/v1/ready`, Caddy status, and recent privacy-filtered logs.
2. Use the request ID and trace ID to correlate errors; never add request bodies, precise coordinates, tokens, or raw query strings to an incident channel.
3. Check MySQL spatial and Redis health separately. A failed readiness check should remove the API from traffic while liveness remains available for diagnosis.
4. If a public provider is failing, verify the provenance/fallback behavior and rate limits before changing provider configuration.
5. Declare severity: SEV-1 for confidentiality/integrity loss or total outage, SEV-2 for major protected-flow degradation, SEV-3 for partial or portfolio-only degradation.
6. Record timeline, decision owner, affected versions, mitigations, and evidence. Preserve logs without expanding personal-data collection.

## Common responses

- MySQL spatial unavailable: stop writes, inspect storage/credentials, use the latest verified backup only after checksum and SQL-dump validation, and follow the guarded restore command in `self-hosting.md`.
- Redis unavailable: keep MySQL spatial authoritative, restore Redis service, and accept that events older than the retained stream may require a full state refresh.
- Suspected token compromise: rotate the JWT secret during a maintenance window, revoke refresh sessions, force reauthentication, and review audit records.
- Bad release: record image IDs, restore the previous reviewed images, and do not blindly downgrade a database migration.
- Provider incident: reduce call volume, switch to an approved self-hosted/configured endpoint, or retain the explicitly labelled fallback. Never relabel fallback data as live.

## Release checklist

- All seven validation jobs are green on the exact commit.
- Production Compose configuration renders without secrets in output or source control.
- Database migration and rollback implications are reviewed.
- A current backup and checksum exist; scheduled restore evidence is within policy.
- Image digests and Git commit are recorded for rollback.
- Readiness and same-origin HTTPS/API probes pass after deployment.
- Security, privacy, and user-facing risk claims have not expanded without evidence.

## Incident follow-up

Within five working days, write a blameless review with root cause, detection gap, customer/privacy impact, recovery evidence, and owned corrective actions. Add a regression test or operational control when feasible. Security incidents additionally require the owner to follow applicable notification and POPIA/legal obligations.
