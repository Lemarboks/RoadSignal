# Threat model

Primary risks are false incident campaigns, account takeover, location stalking, tenant-data leakage, unsafe route overconfidence, malicious evidence, and denial of service. Controls include expiring JWTs, Argon2 password hashes, tenant/role checks, input schemas and sanitisation, proximity/velocity/frequency abuse signals, confidence rather than binary truth, audit events, CORS allowlists, request throttles, encrypted connections, spatial minimisation, and prominent non-guarantee messaging.

Evidence uploads must use short-lived signed URLs, MIME/signature checks, size limits, malware quarantine, metadata removal, and moderator-only access. Never put driver coordinates in Application Insights events. Before production, complete penetration testing, tenant-isolation integration tests, secrets rotation, dependency scanning, backup restoration tests, and POPIA legal review.
