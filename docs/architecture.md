# Architecture

The browser and Expo client share contracts from `@saferoute/types`. Both call the versioned FastAPI boundary. Routes pass through a provider abstraction; local development uses three deterministic Cape Town geometries. Route points are scored against baseline risk and active incident evidence, then aggregated so a single unsafe segment cannot disappear inside a good average. Incident confidence is calculated separately.

The local MVP repository and event journal are in process, making the acceptance flow immediately runnable without paid services. Production models cover all requested entities with PostGIS geography columns and GiST indexes. The intended production path replaces the local repository with SQLAlchemy repositories and replaces the event journal with Redis pub/sub; WebSocket clients retain the same event contract.

Azure deployment targets Container Apps for API/web, Azure Database for PostgreSQL, Azure Cache for Redis, Azure Maps, Blob Storage for quarantined evidence, and Application Insights with precise locations removed from telemetry.

## Known limitations

- The default runtime persists demonstration state in one API process; restarting clears newly created trips/reports.
- Authentication schemas and storage models exist, but the demonstration endpoints are intentionally open and the full JWT router/RBAC middleware is not yet connected.
- Azure Maps and live incident provider adapters need deployment credentials and provider-specific implementation.
- The web uses a deliberately schematic credential-free map, not turn-by-turn navigation.
- Expo background tracking, native maps, notifications, evidence uploads, and actual emergency integrations require native entitlements and security review.
- Seed volume is represented by the UI/analytics fixtures; a database seed command containing the requested 50 incident rows is still pending.
- Rate limiting is listed in the dependency set but not wired to routes in this build.
