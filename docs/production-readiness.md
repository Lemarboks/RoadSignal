# Production-readiness programme

SafeRoute AI is being upgraded in evidence-driven milestones. A feature is marked production-ready only when its runtime path, failure behavior, tests, security boundary, and operating instructions exist. Demonstration fallbacks remain available in development, but production configuration refuses to start with in-memory security or persistence.

## Milestone 1: identity and runtime boundaries

Implemented:

- Argon2 password hashing through `pwdlib`.
- Fifteen-minute JWT access tokens with issuer, audience, expiry, not-before time, unique token ID, and strict claim validation.
- Opaque 384-bit refresh tokens stored only as SHA-256 hashes, rotated after every use, and revocable on logout.
- Public registration restricted to the driver role; elevated roles must be provisioned administratively.
- Role checks on incident resolution, fleet operations, analytics, emergency resolution, and audit logs.
- Authentication throttling backed by Redis in production and an isolated memory limiter in tests.
- Strict production validation for PostgreSQL, Redis, authentication, CORS, and JWT secret strength.
- Security headers, request correlation IDs, and no-store responses for authentication routes.
- Liveness and dependency-aware readiness endpoints.

### Challenge

The original repository described authentication and role checks but did not connect them to the running API. Adding tokens alone would preserve that security gap. Refresh tokens also create replay risk if stored in plaintext or accepted repeatedly.

### Decision

Access tokens are short lived and independently verifiable. Refresh tokens are random opaque credentials, hashed at rest, rotated on use, and invalidated on logout. Local demonstrations may explicitly disable authorization, while production configuration cannot.

### Benefit

The API now demonstrates a complete session lifecycle and enforceable least-privilege boundary rather than security documentation without runtime evidence.

## Remaining milestones

1. Replace global state with PostGIS repositories and migration-tested spatial queries.
2. Replace the process-local journal with Redis Streams/pub-sub and authenticated WebSockets.
3. Route the deployed web application through the API with secure session handling and an explicit offline mode.
4. Add OpenTelemetry, Prometheus metrics, structured privacy-filtered logs, backup/restore automation, load tests, and container security checks.
5. Establish licensed data provenance and then decide whether available evidence supports a trained model or requires retaining the transparent deterministic baseline.

## User-owned decisions

No user action is required for local implementation. A production deployment will require a hosting target, DNS/domain choice, a secret-management mechanism, and explicit approval of any ongoing cost. A trained risk model will require approved datasets with licences that permit this use.
