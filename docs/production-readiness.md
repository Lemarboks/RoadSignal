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
## Milestone 2: persistent PostGIS runtime repositories

Implemented:

- A repository contract covers routes, trips, incidents, moderation state, and audit records.
- Production selects PostgreSQL/PostGIS; tests and explicit demo mode use an isolated memory implementation.
- Incident locations are stored as SRID 4326 geography points and read with spatial database functions.
- Route geometry is stored as an SRID 4326 geography line and reconstructed as GeoJSON-compatible coordinates.
- Trip state links to persisted routes and retains progress, alerts, safety score, actor, and start time across restarts.
- Alembic now has a complete runtime configuration, idempotent upgrades, and automatic container startup migrations.
- CI provisions a real PostGIS service, runs all migrations, and proves incident, route, trip, and audit round trips.

### Challenge

The original API mutated module-level dictionaries. Merely adding SQLAlchemy model files did not make the runtime persistent, and JSON-only storage would have discarded the principal technical advantage of PostGIS.

### Decision

All core runtime operations now pass through one repository boundary. The Postgres implementation uses spatial columns and database spatial functions; the memory implementation exists only for deterministic tests and deliberately configured demos. Production validation prevents selecting the memory implementation.

### Benefit

The same API flow now survives process restarts, supports indexed geographic analysis, and can be tested against the actual database engine in CI. Future risk queries can move into PostGIS without changing endpoint contracts.
## Milestone 3: replayable realtime events

Implemented:

- Production events use a capped Redis Stream rather than a process-local list or fire-and-forget pub/sub.
- Each connection carries a stream cursor, allowing reconnecting clients to recover events they missed.
- Production WebSockets require an access token in the first message, avoiding credentials in URLs and proxy logs.
- The web client uses bounded exponential reconnection, preserves the last cursor, rejects malformed envelopes, and stops retrying after an authorization failure.
- Operational connection state is visible and announced accessibly when an API is configured.
- Readiness reports Redis independently from database health.
- Dedicated CI provisions Redis and verifies ordered publication and replay behavior against the real server.

### Challenge

Plain Redis pub/sub loses messages whenever a browser disconnects, while tokens in WebSocket query strings leak into access logs and browser history. A single-process event list also cannot support multiple API replicas.

### Decision

Redis Streams provide bounded persistence and cursor-based replay. Authentication is the first WebSocket frame, and clients reconnect from the last acknowledged cursor with a capped backoff.

### Benefit

Fleet and driver views can receive the same ordered events across horizontally scaled API instances, recover after temporary network loss, and expose their connection health instead of silently becoming stale.
