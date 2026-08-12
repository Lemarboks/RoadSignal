# SafeRoute AI assessment evidence guide

This document maps the repository to the **App Development 2 Summative Assignment**. Rewrite reflective sections in your own voice and add your own screenshots, contact details, dates, repository URL, and presentation evidence before submission. Do not claim a test or contact attempt that you did not personally complete.

## Submission checklist

- [ ] Fill in the assignment cover page and student details.
- [ ] Add the public GitHub repository URL and deployed GitHub Pages URL.
- [ ] Confirm the repository has at least five meaningful commits after the initial commit.
- [ ] Add contact people, phone numbers and email addresses that you verified yourself.
- [ ] Insert 2–3 debugging screenshots and final application screenshots.
- [ ] Capture unit-test and acceptance-test results from GitHub Actions.
- [ ] Attach the presentation graphics and rehearse a 3–10 minute presentation.
- [ ] Submit the source, final release, assignment document and evidence files.

## Task A — Market the exhibition (10)

### Suitable organisations

These are relevant examples because the project demonstrates TypeScript, Python, cloud deployment, geospatial data, API design and user-focused safety software. Verify a real contact through each organisation's official website or LinkedIn before submission.

| Organisation | Why SafeRoute AI is relevant | Contact person | Phone | Email |
| --- | --- | --- | --- | --- |
| Amazon Development Centre South Africa | Cloud and software engineering | **Learner to verify** | **Learner to verify** | **Learner to verify** |
| Takealot Group | Logistics, routing and large-scale software | **Learner to verify** | **Learner to verify** | **Learner to verify** |
| Entersekt | South African safety-focused technology | **Learner to verify** | **Learner to verify** | **Learner to verify** |
| OfferZen | South African software engineering network | **Learner to verify** | **Learner to verify** | **Learner to verify** |
| City of Cape Town technology/transport team | Local mobility and community impact | **Learner to verify** | **Learner to verify** | **Learner to verify** |

### Exhibition invitation draft

**Subject: Invitation to SafeRoute AI software exhibition**

Dear **[name]**,

I am completing my Software Engineering qualification and would like to invite you to our student software exhibition on **[date, time and venue]**. I will demonstrate SafeRoute AI, a web and mobile prototype that compares driving routes using travel time and confidence-weighted risk information. The project combines a Next.js interface, FastAPI service, geospatial data design, automated testing and cloud-ready deployment.

The demonstration will explain the problem, the system design, how route-risk estimates are calculated, the limitations of the current prototype and the next steps required for responsible production use. I believe it may be relevant to your work in **[company-specific reason]**.

Please let me know if you would be able to attend. Thank you for considering the invitation.

Kind regards,  
**[full name, student number, phone and email]**

## Task B — Presentation plan (10)

### Suggested visual sequence

1. Problem and motivation: road users often compare time, but not confidence-weighted route risk.
2. Architecture diagram: Next.js/Expo → FastAPI → routing/risk providers → MySQL spatial/Redis production design.
3. Live demonstration: Dashboard → Route Planner → compare alternatives → start simulated trip → inject an incident → observe rerouting.
4. Engineering evidence: tests, GitHub Actions and Pages deployment.
5. Limitations, future improvements and lessons learned.

Presentation cover artwork: `docs/presentation/saferoute-exhibition-cover.png`. This is generated supporting artwork, not evidence of application functionality.

### 3–5 minute monologue draft

> SafeRoute AI was motivated by a simple problem: the fastest route is not always the most appropriate route. Drivers and fleet managers may also want to understand recent incidents, road conditions and the confidence of available reports. I designed SafeRoute AI as decision-support software rather than as a guarantee of safety.
>
> The solution includes a responsive Next.js fleet console, an Expo mobile prototype and a Python FastAPI service. The system compares route duration with a confidence-weighted risk score. Route segments are assessed separately so that one high-risk section is not hidden by a good route average. Reports also gain or lose confidence through confirmations and disputes.
>
> In this demonstration I can plan a route in Cape Town, compare balanced, safest and fastest options, and inspect the factors behind each estimate. I can start a simulated trip and introduce an incident to show how the score and rerouting recommendation change. The public GitHub Pages release remains usable if external services fail because it includes deterministic demo routes and clearly labels the active data source.
>
> The project could be improved by connecting validated live data providers, implementing production authentication and role-based access, storing data through MySQL spatial repositories, using Redis for realtime events, adding secure emergency integrations and validating the risk model with domain experts. Native background location and notification features would also require consent, privacy and security review.
>
> Building the project taught me how to organise a multi-application repository, share TypeScript contracts, design and test APIs, work with geospatial routing, handle unreliable networks, create graceful offline fallbacks and deploy a static production build with GitHub Actions. **[Add one specific challenge and what you personally learned from resolving it.]**

## Task C — Plan, develop and debug (90)

### Software description, motivation and beneficiaries

SafeRoute AI is a route-risk decision-support prototype. It compares driving alternatives by travel time and an explainable risk estimate derived from baseline risk factors and confidence-weighted incidents. Potential beneficiaries include individual drivers, delivery or service fleets, incident moderators and transport operations teams. All included identities, trips and incidents are demonstration data.

### Design specification and interaction flow

#### Main features

- Fleet dashboard with driver, incident, trip and safety indicators.
- Cape Town place search, current-location permission handling and route planning.
- Balanced, safest and fastest route alternatives.
- Segment-level risk display, overall score, confidence and factor breakdown.
- Simulated trip progress, incident injection, alerting and rerouting.
- Incident reporting, confirmation, dispute and resolution flows.
- Analytics and audit-style activity evidence.
- Responsive layouts for desktop and mobile browsers.
- Static GitHub Pages mode with public routing and deterministic offline fallbacks.
- FastAPI endpoints, MySQL spatial production models and Redis-ready event contracts.

#### User flow

1. The user opens the dashboard and reviews current demonstration operations.
2. The user opens Route Planner and enters an origin, destination and preference.
3. The browser tries public place/routing services with bounded request times.
4. If services succeed, three alternatives are scored and displayed. If they fail, the user can immediately use built-in demo routes.
5. The user selects a route and reviews time, distance, score, confidence and contributing factors.
6. The user starts a simulated trip.
7. A new incident can reduce the route score and trigger a safer-route recommendation.
8. Incident confirmations or disputes update confidence and are reflected in the activity history.

#### Non-functional requirements

- Clear disclaimers: estimates are not guarantees of safety.
- Graceful degradation when APIs, tiles, storage or location permissions fail.
- Keyboard-visible focus, semantic controls and announced status updates.
- No API credentials required for the static demonstration.
- Reproducible builds and automated validation in GitHub Actions.
- Maintainable separation between web, mobile, API and shared contracts.

### Libraries and tools

| Tool | Purpose and reason |
| --- | --- |
| [Next.js](https://nextjs.org/) and React | Component-based web interface with static export support. |
| [TypeScript](https://www.typescriptlang.org/) | Shared typed contracts and safer frontend refactoring. |
| [Expo](https://expo.dev/) / React Native | Cross-platform driver mobile prototype. |
| [FastAPI](https://fastapi.tiangolo.com/) | Typed Python API with automatic OpenAPI documentation. |
| [Pydantic](https://docs.pydantic.dev/) | Request validation and API schemas. |
| [SQLAlchemy](https://www.sqlalchemy.org/) and Alembic | Production data models and migrations. |
| [MySQL 8 spatial](https://mysql.net/) | Spatial storage and indexes for routes, trips and incidents. |
| [Redis](https://redis.io/) | Intended production event and realtime architecture. |
| [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/) | Open-source interactive vector maps. |
| [OpenStreetMap](https://www.openstreetmap.org/copyright), Photon and OSRM | Credential-free demonstration search, map and road routing data. |
| [Vitest](https://vitest.dev/) and Pytest | Automated web logic and API/engine unit tests. |
| [pnpm](https://pnpm.io/) and Turborepo | Reproducible monorepo dependency and task management. |
| GitHub Actions and GitHub Pages | Automated validation and public static deployment. |
| Docker Compose | Repeatable local MySQL and Redis services. |

Public services were selected for a credential-free demonstration. They have no production SLA, so the final design adds request timeouts and deterministic fallback routes. Production deployments should point the same adapters at self-hosted instances.

### Implementation plan

| Stage | Expected time | Languages/tools | Main challenge |
| --- | ---: | --- | --- |
| Requirements and responsible-risk scope | 4 hours | Markdown, diagrams | Avoiding misleading safety claims |
| Shared contracts and monorepo | 5 hours | TypeScript, pnpm, Turbo | Keeping applications consistent |
| Risk and incident engines | 10 hours | Python, Pytest | Explainability and deterministic scoring |
| API and production schema | 12 hours | FastAPI, SQLAlchemy, MySQL spatial | Spatial models and validation |
| Web dashboard and route planner | 18 hours | Next.js, MapLibre | Responsive maps and interaction states |
| Mobile prototype | 8 hours | Expo, React Native | Permissions and small-screen workflow |
| Public routing and offline fallback | 10 hours | Photon, Nominatim, OSRM | Rate limits and network failure |
| Automated tests and debugging | 10 hours | Vitest, Pytest, Actions | Edge cases across applications |
| Static release and documentation | 7 hours | GitHub Pages, Markdown | Repository base paths and honest demo labelling |

Replace expected values with your original plan if you recorded different estimates, and add actual time where available.

### GitHub evidence

- Repository: **[insert public repository URL]**
- Release: **[insert GitHub Pages URL]**
- Licence: [LICENSE](../LICENSE)
- Deployment workflow: [pages.yml](../.github/workflows/pages.yml)
- Pull-request validation: [validate.yml](../.github/workflows/validate.yml)
- Verify at least five descriptive commits exist after the initial commit. Do not manufacture or squash evidence solely to satisfy the count.

### Debugging log examples

Use these only if they match work you actually performed, and attach your own before/after or console screenshots.

| Issue | Cause | Technique and resolution | Screenshot |
| --- | --- | --- | --- |
| Static site assets could fail under `/SafeRouteAI/` | GitHub project Pages uses a repository subpath | Derived `basePath` and `assetPrefix` from `GITHUB_REPOSITORY`, enabled static export and added `.nojekyll` | **[insert]** |
| Public route search occasionally fails | Public Photon/Nominatim/OSRM services have rate limits and no SLA | Added bounded requests, cached places, deterministic route fallback and a manual demo option | **[insert]** |
| Map tiles may not load | Network, CSP or shared tile-service failure | MapLibre reports an error and the component displays an offline schematic | **[insert]** |
| Pages tried a nonexistent local API route | Production API URL can be empty | Skip the API call when it is not configured and use built-in demo data | **[insert]** |

### Error-handling code examples

1. **Public geocoding/routing failure:** `open-routing.ts` limits public requests to eight seconds and surfaces a controlled failure. `page.tsx` catches that failure, preserves the interface and activates built-in demo routes. This handles offline use, throttling and unavailable providers without leaving the route planner stuck.
2. **Map loading failure:** `route-map.tsx` listens for MapLibre loading errors and replaces the interactive map with an accessible schematic. Route comparison remains visible even when tile delivery fails.
3. **Location permission failure:** `page.tsx` checks browser support, permission state, denial and timeout conditions. It explains how to recover and retains manual place search.

## Task D — Test and deploy (60)

### Unit tests

The repository contains more than the required two unit tests:

- `apps/web/lib/open-routing.test.ts`: verifies route scoring, preference ordering, fallback calculations and public-routing transformations. Explain two selected cases and insert the GitHub Actions output screenshot.
- `apps/api/tests/test_engines.py`: verifies deterministic decay, nearby high-severity penalties, worst-segment aggregation, and confidence changes from confirmations/disputes.
- `apps/api/tests/test_api.py`: exercises the critical API flow for route analysis, incident creation/moderation and related endpoints.

Run and capture:

```bash
pnpm --filter @saferoute/web test
python -m pytest apps/api/tests
```

### System and acceptance test record

Record the actual date, browser/device, result and screenshot. Do not mark a case Passed until you personally run it or GitHub Actions provides evidence.

| Test | Expected result | Actual result | Status/evidence |
| --- | --- | --- | --- |
| Open deployed Pages URL | Dashboard loads beneath repository base path | **[record]** | **[Pass/Fail + screenshot]** |
| Plan default Cape Town route | Three alternatives or clear fallback appears | **[record]** | **[Pass/Fail]** |
| Disconnect network and use demo | Built-in routes remain usable | **[record]** | **[Pass/Fail]** |
| Block location permission | Manual origin entry remains available with guidance | **[record]** | **[Pass/Fail]** |
| Select a route and start trip | Live Trip shows selected route and progress | **[record]** | **[Pass/Fail]** |
| Inject an incident | Score falls and reroute alert appears | **[record]** | **[Pass/Fail]** |
| Keyboard-only navigation | Navigation, planner, cards and notification dismissal work | **[record]** | **[Pass/Fail]** |
| Mobile viewport | No page-level horizontal overflow; controls remain usable | **[record]** | **[Pass/Fail]** |
| GitHub validation workflow | Type-check, web tests, API tests and build succeed | **[record]** | **[workflow link]** |

Suggested conclusion after testing: **[State whether all critical flows passed, identify remaining limitations, and explain whether the release is suitable as a demonstration rather than a live safety service.]**

### Deployment evidence

- Production-mode static export is configured in `apps/web/next.config.ts`.
- GitHub Actions installs locked dependencies, type-checks, tests and builds before deployment.
- `.nojekyll` preserves Next.js `_next` assets.
- Repository-aware `basePath` and `assetPrefix` support project Pages URLs.
- The deployed app clearly labels simulated/public/API data and remains usable without the backend.
- Source code and the exported release are available through the repository and Pages artifact.

### Changes from the original design

The initial design expected the web client to communicate with FastAPI, MySQL, Redis and live providers. GitHub Pages only hosts static files, so the release design was adapted to preserve the demonstration without pretending those backend services are running. The final static version adds deterministic routes, public provider fallbacks, an offline schematic, request timeouts, explicit data-source badges, a manual demo-route action, repository-aware asset paths and automated pre-deployment checks. The full API and production database architecture remain in the source for local or cloud deployment.

### Final screenshots to include

1. Dashboard with the GitHub Pages demonstration/data-source banner.
2. Route Planner showing three alternatives and the risk explanation.
3. Live Trip after an incident and rerouting alert.
4. Mobile-width interface.
5. Successful GitHub Actions validation and Pages deployment.
