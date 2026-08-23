# RoadSignal implementation plan

This checklist is the delivery contract for the production-quality MVP. Items marked complete are implemented in this repository; deferred items remain explicit rather than hidden behind placeholder UI.

## 1. Foundation

- [x] Create pnpm/Turborepo monorepo layout
- [x] Add shared TypeScript types and API client
- [x] Add environment template and validation guidance
- [x] Add Docker Compose for MySQL spatial, Redis, and FastAPI
- [x] Add health checks and development commands
- [x] Add seven-gate CI workflow

## 2. Backend and data

- [x] Organise FastAPI by route, incident, trip, fleet, emergency, and realtime domains
- [x] Add deterministic Cape Town demonstration dataset
- [x] Add Nominatim/OSRM route-provider abstraction with deterministic fallback
- [x] Implement deterministic segment and route risk scoring
- [x] Implement incident-confidence calculation and abuse flags
- [x] Implement route analysis, incident moderation, trip lifecycle, fleet analytics, emergency, and health endpoints
- [x] Add in-process event bus and WebSocket event stream for the local MVP
- [x] Add SQLAlchemy/MySQL spatial production models and initial Alembic migration
- [x] Add JWT/password service and role checks
- [x] Use MySQL repositories for every persistent runtime path
- [x] Use Redis Streams for replayable multi-process events

## 3. Web product

- [x] Add responsive operational shell and all required navigation destinations
- [x] Build dashboard and fleet operational views
- [x] Build route planner with three comparable routes and selectable risk-aware paths
- [x] Build risk explanation and decision-support disclaimer
- [x] Build live-trip simulation with pause, resume, incident injection, reroute, audit history, and end-trip review
- [x] Build incident report and incident management flows with confirm/dispute/resolve
- [x] Build risk map, analytics, and settings screens with meaningful seeded content
- [x] Add loading, empty, failure, and action feedback states
- [x] Add a no-key MapLibre/OpenFreeMap map with visible attribution and an offline SVG fallback
- [x] Integrate configurable MapLibre, OpenFreeMap, Photon, Nominatim, OSRM, and Open-Meteo services without API keys

## 4. Mobile

- [x] Scaffold Expo Router application sharing API types
- [x] Implement home, route comparison, active-trip simulation, reporting, alerts, history, profile, and SOS screens
- [x] Add simulated-location abstraction and MVP-labelled SOS countdown
- [x] Persist mobile refresh sessions in encrypted device storage and restore them safely on launch
- [x] Complete native push-notification registration and background-location production entitlements

## 5. Quality, security, and delivery

- [x] Add risk and confidence unit tests
- [x] Add API integration tests
- [x] Add frontend component tests and critical-flow Playwright specification
- [x] Add request validation, CORS, rate limiting, audit events, password hashing, and expiring JWTs
- [x] Add architecture, API, risk, schema, threat-model, privacy, deployment, and demo documentation
- [x] Run locally available lint/type/test checks and record limitations
- [ ] Perform a staging deployment and load/security test against self-hosted provider instances

## Acceptance flow

- [x] Search between Cape Town locations and receive three alternatives
- [x] Recommend the balanced route using deterministic safety/time utility
- [x] Start and advance a simulated trip
- [x] Inject an accident or crime report on the route
- [x] Recalculate score, warn the driver, and recommend a safer route
- [x] Publish the event to the fleet view and audit log
- [x] Confirm/dispute the incident and update confidence
- [x] End the trip and review its risk-event history
