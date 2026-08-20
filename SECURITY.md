# Security

Report vulnerabilities privately to the repository owner. Do not include credentials, personal data, or exploit details in a public issue.

## Implemented controls

- Production refuses in-memory persistence, disabled authentication, weak JWT/metrics secrets, wildcard CORS, and non-HTTPS origins.
- MySQL and Redis credentials are server-side Docker secrets. This application has no public database key.
- MySQL does not provide PostgreSQL row-level security. RoadSignal enforces the equivalent boundary in the API through authenticated owner checks for trips and role checks for fleet, moderation, audit, and emergency resolution operations. Database ports are not exposed publicly.
- Passwords use Argon2. Refresh tokens are random, stored only as SHA-256 hashes, rotated on use, and delivered to browsers in HttpOnly, SameSite=Strict cookies. Access tokens remain in memory.
- Login and registration are rate limited. Unknown accounts follow a dummy password verification path, and a honeypot field rejects basic automated form filling.
- Pydantic rejects unknown request fields and bounds strings, coordinates, enums, and body sizes. SQLAlchemy binds query parameters. User text is stored as plain text and React escapes it on output.
- Multipart requests are rejected because RoadSignal currently has no upload feature. A future upload feature requires isolated object storage, MIME/signature checks, size limits, malware scanning, and authorization.
- API responses use no-store/no-cache policy and omit password hashes, refresh tokens, and internal database credentials.
- Caddy terminates HTTPS and sends HSTS. The API sends CSP, frame, MIME, referrer, permissions, opener, and resource-policy headers.
- MySQL backups are encrypted and checksummed. CI scans full Git history for secrets and audits Python, deployed JavaScript, container configuration, and dependencies.

## Operator responsibilities

Application code cannot enable storage encryption for the host disk. Production operators must enable provider or volume encryption, protect the backup key separately, rotate any credential suspected of exposure, and perform restore and access-control drills. A managed bot challenge requires provider-issued site keys and should be added before exposing registration to sustained hostile traffic.
