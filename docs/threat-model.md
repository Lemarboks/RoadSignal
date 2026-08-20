# Threat model

## Scope and assets

The protected production scope is Caddy, the browser session, FastAPI, MySQL spatial, Redis, Docker secrets, backups, and outbound provider adapters. High-value assets are account credentials, refresh sessions, precise trip locations, tenant membership, incident moderation state, audit history, and route-risk explanations. The static GitHub Pages demonstration contains no real identities or production secrets.

## Trust boundaries and threats

| Boundary / threat | Abuse case | Implemented controls | Residual risk / next control |
|---|---|---|---|
| Browser to API | Token theft, request forgery, credential leakage | TLS, exact CORS allowlist, in-memory access tokens, HttpOnly SameSite refresh cookie, no credentials in URLs/storage/logs, CSP and security headers, short JWT lifetime, rotated hashed refresh tokens | XSS can act as the user while the page is open; maintain CSP review and dependency scanning |
| Authorization | Driver reads or mutates another driver's trip | Role checks plus owner-or-operator authorization and two-user regression tests | Fleet membership is still a policy-sensitive boundary; add tenant-isolation matrix tests before multi-tenant onboarding |
| WebSocket | Token leaks through proxy logs or missed events | Authentication in first frame, Redis cursor replay, bounded reconnect, authorization-failure stop | A stolen live access token remains valid until expiry |
| Incident reports | Coordinated false reports or moderator abuse | Confidence rather than binary truth, confirmations/disputes, rate limits, abuse signals, expiry, moderation roles, audit events | Sybil campaigns require verified reporter reputation and operational moderation |
| Precise location | Stalking, secondary use, telemetry leakage | No bodies, query strings, IPs, coordinates, or exception text in operational logs; role and object checks; encrypted transport | Database operators can access records; define retention/deletion schedules and audited privileged access |
| Provider adapters | SSRF, availability failure, data leakage | Fixed configurable base URLs, request timeouts, provenance labels, deterministic fallback, no user-controlled destination hosts | Public providers receive network metadata and selected coordinates; proxy or self-host for real deployments |
| Containers/secrets | Secret committed to Git, root escape, lateral movement | Docker secrets, ignored secret directory, non-root images, read-only application filesystems, dropped capabilities, private networks, CI secret/misconfiguration scans | Host compromise defeats container isolation; patch and harden the host |
| Backups | Data loss, malicious restore, backup disclosure | AES-256 encrypted, checksummed transaction-consistent SQL dumps, validation, retention, off-host guidance, explicit restore confirmation, safety backup | Key custody and off-host access policy depend on the owner-selected backup target |
| Risk score | User over-trusts an incomplete estimate | Explainable factors, confidence, provider provenance, prominent disclaimer, worst-segment weighting | No score can guarantee safety; real-world deployment needs domain review and outcome monitoring |
| Availability | Request floods or dependency outage | Authentication throttles, route limits, readiness 503, health-gated startup, replay bounds, provider timeouts | Load limits require target-specific capacity tests and autoscaling policy |

## Security verification

Every pull request runs API and web tests, real MySQL spatial and Redis integration tests, a production Compose/TLS smoke test, desktop/mobile Playwright journeys, axe accessibility rules, production JavaScript reachability auditing, Python dependency auditing, and Trivy secret/misconfiguration scanning. Backup restoration is exercised by the deployment workflow. Logs and metrics are tested for bounded labels and location/credential exclusion.

## Required before handling real journey data

Complete a POPIA/privacy legal review, retention and deletion policy, tenant-isolation penetration test, incident-response exercise, secret rotation drill, capacity test against the selected host, encrypted off-host restore drill, and contracts or self-hosting for providers. Evidence uploads must additionally use short-lived signed URLs, signature/MIME checks, size limits, malware quarantine, metadata removal, and moderator-only access.
