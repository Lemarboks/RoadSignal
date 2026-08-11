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

## Milestone 4: secure API-first web sessions

Implemented:

- The browser prefers the configured SafeRoute API for route analysis, falls back to public open routing when the API is unavailable, and labels built-in data as a demonstration fallback.
- A typed API client owns bearer authorization, one-time refresh rotation and retry, consistent error parsing, and logout revocation.
- Access and refresh credentials remain only in JavaScript memory. They are never placed in local storage, session storage, URLs, or logs.
- Login and driver registration expose loading, validation, rate-limit, service-error, and signed-in states with accessible form semantics.
- Realtime connections restart with the current access token after authentication changes.
- Starting an API-backed trip requires a session and waits for the protected server endpoint before displaying the live-trip state.
- Symbol-only navigation and corrupted display characters were replaced with readable ASCII labels; temperatures remain explicitly displayed in degrees Celsius.

### Challenge

A static portfolio build must remain useful when no API is configured, but silently treating local simulation or a third-party route response as backend state would misrepresent the system. Persisting tokens in browser storage would improve reload convenience while creating a durable credential target for injected scripts.

### Decision

Data provenance is a first-class UI state: API, public open data, and built-in demonstration are separate modes. The secure default keeps tokens in memory and accepts the usability trade-off that a page reload requires signing in again. Protected actions never fall through to a local success state when an API session is expected.

### Benefit

Reviewers can see a real end-to-end authorization boundary and graceful degradation without confusing simulated behavior for production behavior. The browser has a small, testable security boundary that can later migrate refresh rotation to an HttpOnly same-site cookie when the web and API share a production origin.
## Milestone 5: privacy-aware observability

Implemented:

- Prometheus counters and latency histograms use bounded method, route-template, and status labels to avoid high-cardinality series; production scraping requires a separate random bearer token.
- JSON request logs include request ID, trace ID, service, environment, route template, status, and duration.
- Logs deliberately exclude request bodies, authorization credentials, query strings, IP addresses, precise coordinates, and exception messages.
- Incoming request IDs are accepted only from a bounded safe character set; malformed or oversized values are replaced before logging or reflection.
- Optional OpenTelemetry FastAPI tracing exports over vendor-neutral OTLP/HTTP when an endpoint is configured.
- Liveness remains process-only, while readiness returns HTTP 503 when a required database or event bus is unavailable.
- Prometheus and OpenTelemetry behavior is covered by API tests, including route-cardinality and privacy assertions.

### Challenge

Route-risk requests can contain precise locations and authentication credentials. Generic HTTP logging and unbounded path labels can leak personal data while also making Prometheus unusable through cardinality growth.

### Decision

Observability is allow-list based. Only operational metadata is emitted, dynamic URLs are reduced to framework route templates, and OTLP export is disabled unless explicitly configured. Readiness is a traffic-management signal rather than a decorative JSON field.

### Benefit

Operators can correlate failures, measure latency and error rates, build SLOs, and drain unhealthy replicas without coupling the application to a proprietary monitoring vendor or collecting sensitive journey data.
## Milestone 6: vendor-neutral production deployment

Implemented:

- A separate production Compose topology exposes only Caddy on ports 80/443 and isolates PostGIS, Redis, the API, and observability traffic on internal networks.
- Caddy serves the static Next.js export, proxies API and WebSocket traffic, applies transport headers, and automates TLS without a cloud-specific ingress service.
- The API image runs as an unprivileged fixed UID with a read-only filesystem, a bounded temporary filesystem, and no Linux capabilities.
- PostgreSQL, Redis, API, and metrics credentials are generated locally, ignored by Git, mounted individually as read-only Docker secrets, and loaded without embedding them in images.
- Redis uses append-only persistence and authentication; PostGIS and Redis have health-gated API startup.
- Prometheus is an optional internal profile, bearer-authenticates to metrics, and binds only to host loopback.
- Backup and guarded restore scripts create custom-format Postgres archives, validate them, checksum them, enforce retention, and take a safety backup before destructive restore.
- CI validates the Compose model, builds every custom image, starts the production topology, waits for health, and probes the web and API over TLS.

### Challenge

The development Compose file published every datastore port and used known passwords. A static Pages build also had no same-origin API, while a cloud-specific deployment would undermine the project's open, portable architecture.

### Decision

Development convenience and production security are separate Compose models. The production model uses Caddy, Docker secrets, internal networks, immutable application filesystems, least privilege, and health-gated startup. PostGIS is the system of record; Redis is a persistent replay buffer but is not treated as the authoritative backup target.

### Benefit

The same reviewed artifacts can run on a laptop, VPS, bare-metal host, or any container service that supports standard OCI images. Reviewers can inspect and reproduce the security boundaries, while operators have an explicit backup, restore, update, and rollback workflow.
## Milestone 7: browser, accessibility, and security gates

Implemented:

- Playwright runs the real interface in desktop and mobile Chromium profiles rather than relying only on DOM-free unit tests.
- Browser tests cover data-provenance labels, keyboard skip navigation, Celsius weather rendering, the simulated trip flow, and horizontal overflow.
- axe-core blocks WCAG 2 A/AA and WCAG 2.1 A/AA violations in both viewport profiles.
- Failed browser runs retain traces, screenshots, video, and an HTML report for bounded diagnosis.
- API object-level authorization now prevents one driver from reading, monitoring, updating, or ending another driver's trip; fleet managers and administrators retain operational access.
- A two-account regression test covers unauthenticated, wrong-owner, and correct-owner trip access.
- CI audits production JavaScript and Python dependency graphs and scans source, secrets, dependencies, and infrastructure configuration for high/critical findings with Trivy.

### Challenge

Unit tests can prove adapters and reducers while missing keyboard traps, responsive overflow, inaccessible rendered markup, and authorization mistakes that require two independent identities. A green build is not evidence of a secure or usable browser workflow.

### Decision

Quality gates are layered: unit tests for deterministic logic, real PostGIS and Redis integration jobs, a full production deployment smoke test, two-viewport browser journeys, automated accessibility rules, and independent vulnerability/misconfiguration scanners. Object ownership is enforced in the API, never inferred from hidden frontend controls.

### Benefit

Regressions now produce actionable artifacts and fail before merge across logic, storage, events, containers, browser behavior, accessibility, dependency risk, and horizontal authorization. This is materially closer to the evidence expected from a production engineering portfolio than a single happy-path test suite.