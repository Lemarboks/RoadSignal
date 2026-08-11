# Architecture

The browser and Expo client share contracts from `@saferoute/types`. Both call the versioned FastAPI boundary. Routes use Nominatim geocoding and OSRM road routing; deterministic Cape Town geometries provide an offline resilience fallback. Route points are scored against baseline risk and active incident evidence, then aggregated so a single unsafe segment cannot disappear inside a good average. Incident confidence is calculated separately. The browser renders maps with MapLibre GL and OpenFreeMap's no-key OpenStreetMap-based vector styles; an offline schematic remains available when public tiles cannot load.

The local MVP repository and event journal are in process, making the acceptance flow immediately runnable without paid services. Production models cover all requested entities with PostGIS geography columns and GiST indexes. The intended production path replaces the local repository with SQLAlchemy repositories and replaces the event journal with Redis pub/sub; WebSocket clients retain the same event contract.

The deployment stack is vendor-neutral: OCI containers, PostgreSQL/PostGIS, Redis, OSRM, Nominatim, Open-Meteo, MinIO-compatible object storage, OpenTelemetry, and Grafana.

## Known limitations

- The default runtime persists demonstration state in one API process; restarting clears newly created trips/reports.
- Authentication schemas and storage models exist, but the demonstration endpoints are intentionally open and the full JWT router/RBAC middleware is not yet connected.
- Public open-source endpoints have usage policies and no production SLA; production deployments should use self-hosted provider instances.
- OpenFreeMap is a free public basemap service without an SLA; the application falls back to its offline schematic if tiles are unavailable.
- Photon, Nominatim, and FOSSGIS OSRM are shared public demonstration services without an SLA or live traffic. Their endpoints are configurable so production can move to self-hosted or contracted providers.
- Expo background tracking, native maps, notifications, evidence uploads, and actual emergency integrations require native entitlements and security review.
- Seed volume is represented by the UI/analytics fixtures; a database seed command containing the requested 50 incident rows is still pending.
- Rate limiting is listed in the dependency set but not wired to routes in this build.
