# RoadSignal

RoadSignal is a production-oriented route-risk decision-support portfolio system. It includes a Next.js fleet/driver console, FastAPI API, persistent MySQL spatial repositories, JWT/RBAC sessions, replayable Redis events, open-source routing and weather adapters, a hardened vendor-neutral deployment, and a separate Expo mobile prototype. The web map uses MapLibre GL and no-key OpenFreeMap/OpenStreetMap-based tiles with an offline schematic fallback.

> All included people, trips, incidents, risk zones, and scores are demonstration data. A score is decision support based on available data; it is not a guarantee of safety.

## Docker showcase

The complete showcase runs in Docker: the exported Next.js interface, FastAPI, MySQL, Redis, and a Caddy gateway. The only prerequisite is Docker Desktop (Windows/macOS) or Docker Engine with Compose v2 (Linux).

```bash
git clone <repository>
cd RoadSignal
docker compose up -d --build --wait
```

Open <http://localhost:3000>. Choose **Continue as guest** for the deterministic walkthrough, or register a demonstration account to exercise protected API-backed trips and realtime events. API documentation remains available at <http://localhost:8000/docs>.

Useful showcase commands:

```bash
docker compose ps
docker compose logs -f web api
docker compose down
```

MySQL data persists between starts. To deliberately reset all local showcase data, run `docker compose down --volumes`.

## Local development

Optional local intelligence adds H3 incident counts, Qwen duplicate retrieval, reviewed incident drafts, Whisper voice input, and OpenTelemetry/Jaeger tracing. See [the open-source stack guide](docs/open-source-stack.md) for Docker profiles, memory requirements, tests, and the gated XGBoost/Valhalla integrations.

The Fleet workspace includes animated demo GPS trackers and simulated street-sensor readings with playback, offline/stale states, and reduced-motion support. See [monitoring and evidence verification](docs/monitoring-and-verification.md) for the difference between these synthetic devices and real monitoring integrations.

For the connected Docker demonstration (Traccar, ThingsBoard, n8n, local text/vision models and Valhalla), use the [monitoring setup guide](docs/monitoring-setup.md). It includes the local operator login instructions and memory-saving service modes. All device inputs remain labelled synthetic; no real feed credentials are required.

Prerequisites: Node 20+, pnpm 10+, Python 3.12+, and Docker. Copy `.env.example` to `.env`, start the backing services, then run the API and web development servers:

```bash
cp .env.example .env
docker compose up -d db redis --wait
corepack enable
corepack prepare pnpm@10.13.1 --activate
pnpm install
python -m venv apps/api/.venv
# Windows: apps\api\.venv\Scripts\activate
# macOS/Linux: source apps/api/.venv/bin/activate
pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload --port 8000
pnpm dev:web
```

The web UI has deterministic route and incident fallbacks, so its complete interaction can still be demonstrated when the API or a public data provider is unavailable. `pnpm build` writes a deployment bundle to `dist/`, with static assets under `dist/client` and a minimal asset worker under `dist/server`.

Run mobile separately with `pnpm dev:mobile`. For migrations: `cd apps/api && alembic upgrade head`. The API uses Nominatim, OSRM, and Open-Meteo by default and falls back to deterministic demonstration routes when a public service is unavailable. For production, point the configurable URLs at self-hosted instances.

## Verification

```bash
pnpm typecheck
pnpm build
pnpm build:all
pnpm test
python -m pytest apps/api/tests
```

## Environment

Copy `.env.example`. Required in production: `DATABASE_URL`, `REDIS_URL`, a strong `JWT_SECRET`, `ROUTE_PROVIDER`, and permitted `CORS_ORIGINS`. Browser/mobile URLs are `NEXT_PUBLIC_API_URL` and `EXPO_PUBLIC_API_URL`. The default map, geocoder, router, and weather provider require no API key or billing account.

## Repository

- `apps/web` - operational web console and simulator
- `apps/mobile` - Expo driver prototype and simulated SOS
- `apps/api` - FastAPI domains, scoring engines, providers, persistence, and tests
- `packages/types` and `packages/api-client` - shared TypeScript contract
- `docs` - architecture, operations, risk, privacy, security, deployment, and demo notes
- `docker-compose.yml` - one-command local showcase with web, API, MySQL, and Redis

See [architecture and trade-offs](docs/architecture.md), [operations runbook](docs/operations-runbook.md), [data and model governance](docs/data-and-model-governance.md), [AI model strategy](docs/ai-model-strategy.md), [demo instructions](docs/demo.md), and [known limitations](docs/architecture.md#known-limitations).

Repository-specific Codex workflows are versioned under `skills/`: release validation, risk-model auditing, and accessibility review.

## Free GitHub Pages deployment

The repository includes `.github/workflows/pages.yml`. Pushes to `main` build the web workspace with the `/RoadSignal` base path and publish `apps/web/out` to GitHub Pages. The public static demonstration uses MapLibre/OpenFreeMap, Photon place suggestions, explicit Nominatim lookup, OSRM road geometry, and deterministic client-side risk scoring without API keys or a billing account. Public providers are conservatively throttled and backed by deterministic offline routes. GitHub Pages does not run the FastAPI, MySQL, Redis, or WebSocket services.

## Free backend deployment (Render)

`render.yaml` at the repository root is a Render Blueprint that deploys `apps/api` as a free Docker web service, with no database or Redis to provision: `STORAGE_BACKEND=memory` and `EVENT_BACKEND=memory` reset on every restart, and `ROUTE_PROVIDER=open` still calls live Nominatim, OSRM, and Open-Meteo. `JWT_SECRET` and `METRICS_BEARER_TOKEN` are generated automatically by Render.

1. Sign up at [render.com](https://render.com) (free, no card required for the free plan).
2. New + → Blueprint → connect the `RoadSignal` GitHub repository → Apply. Render reads `render.yaml` and provisions `roadsignal-ai-api`. If that name is taken, Render lets you rename it; note the resulting `https://<name>.onrender.com` URL.
3. In the GitHub repo, go to Settings → Secrets and variables → Actions → Variables, and add `NEXT_PUBLIC_API_URL` set to that URL.
4. Re-run the `Deploy web app to GitHub Pages` workflow (or push to `main`) so the static build bakes in the backend URL.

The free plan spins the service down after 15 minutes of inactivity; the first request after idling takes up to a minute to wake it. If the CORS origin in `render.yaml` doesn't match your Pages URL (default assumes `https://lemarboks.github.io`), update it before applying the blueprint.

## Production deployment

See [Vendor-neutral self-hosting](docs/self-hosting.md) for the hardened Docker Compose stack, TLS, secrets, observability, backups, restore drills, and the owner decisions required for a public launch.

## Licence

Copyright (C) 2026 Lemar Boks.

RoadSignal is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0). See [LICENSE](LICENSE) and [NOTICE](NOTICE).

In short: you may use, study, modify and share this software, but if you
distribute it *or run a modified version as a network service*, you must make
the corresponding source code available under the same licence. That network
clause (section 13) is the reason AGPL was chosen over GPL — RoadSignal is a
web application, and GPL alone would let a modified copy be run as a hosted
service without publishing anything.

Third-party components keep their own licences; see
[docs/open-source-stack.md](docs/open-source-stack.md). Reported crime figures
derive from South African Police Service statistics via
[afrith/crime-stats](https://github.com/afrith/crime-stats), released under the
Open Data Commons PDDL v1.0.
