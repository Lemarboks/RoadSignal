# SafeRoute AI

SafeRoute AI is a production-oriented route-risk decision-support portfolio system. It includes a Next.js fleet/driver console, FastAPI API, persistent MySQL spatial repositories, JWT/RBAC sessions, replayable Redis events, open-source routing and weather adapters, a hardened vendor-neutral deployment, and a separate Expo mobile prototype. The web map uses MapLibre GL and no-key OpenFreeMap/OpenStreetMap-based tiles with an offline schematic fallback.

> All included people, trips, incidents, risk zones, and scores are demonstration data. A score is decision support based on available data; it is not a guarantee of safety.

## Quick start

Prerequisites on Windows: Docker Desktop, Node 20+, pnpm 10+, and Python 3.12+. A separate Linux installation is not required.

```bash
git clone <repository>
cd SafeRouteAI
cp .env.example .env
docker compose up -d --build --wait
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

Open <http://localhost:3000>; API documentation is at <http://localhost:8000/docs>. The web UI has deterministic route and incident fallbacks, so its complete interaction can still be demonstrated on free static hosting when the API is unavailable. `pnpm build` writes a deployment bundle to `dist/`, with static assets under `dist/client` and a minimal asset worker under `dist/server`.

Run mobile separately with `pnpm dev:mobile`. MySQL, Redis, and the API persist locally in Docker volumes; stop containers with `docker compose stop` without deleting that data. For migrations: `cd apps/api && alembic upgrade head`. The API uses Nominatim, OSRM, and Open-Meteo by default and falls back to deterministic demonstration routes when a public service is unavailable. For production, point the configurable URLs at self-hosted instances.

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
- `docker-compose.yml` - local open-source MySQL spatial, Redis, and API services

See [architecture and trade-offs](docs/architecture.md), [operations runbook](docs/operations-runbook.md), [data and model governance](docs/data-and-model-governance.md), [demo instructions](docs/demo.md), and [known limitations](docs/architecture.md#known-limitations).

For assignment submission evidence, use the [assessment marking guide](docs/assessment-marking-guide.md) and replace every learner placeholder with personally verified information.

Repository-specific Codex workflows are versioned under `skills/`: release validation, risk-model auditing, assessment evidence collection, and accessibility review. The exhibition cover artwork is in `docs/presentation/saferoute-exhibition-cover.png`.

## Free GitHub Pages deployment

The repository includes `.github/workflows/pages.yml`. Pushes to `main` build the web workspace with the `/SafeRouteAI` base path and publish `apps/web/out` to GitHub Pages. The public static demonstration uses MapLibre/OpenFreeMap, Photon place suggestions, explicit Nominatim lookup, OSRM road geometry, and deterministic client-side risk scoring without API keys or a billing account. Public providers are conservatively throttled and backed by deterministic offline routes. GitHub Pages does not run the FastAPI, MySQL, Redis, or WebSocket services.

## Free backend deployment (Render)

`render.yaml` at the repository root is a Render Blueprint that deploys `apps/api` as a free Docker web service, with no database or Redis to provision: `STORAGE_BACKEND=memory` and `EVENT_BACKEND=memory` reset on every restart, and `ROUTE_PROVIDER=open` still calls live Nominatim, OSRM, and Open-Meteo. `JWT_SECRET` and `METRICS_BEARER_TOKEN` are generated automatically by Render.

1. Sign up at [render.com](https://render.com) (free, no card required for the free plan).
2. New + → Blueprint → connect the `SafeRouteAI` GitHub repository → Apply. Render reads `render.yaml` and provisions `saferoute-ai-api`. If that name is taken, Render lets you rename it; note the resulting `https://<name>.onrender.com` URL.
3. In the GitHub repo, go to Settings → Secrets and variables → Actions → Variables, and add `NEXT_PUBLIC_API_URL` set to that URL.
4. Re-run the `Deploy web app to GitHub Pages` workflow (or push to `main`) so the static build bakes in the backend URL.

The free plan spins the service down after 15 minutes of inactivity; the first request after idling takes up to a minute to wake it. If the CORS origin in `render.yaml` doesn't match your Pages URL (default assumes `https://lemarboks.github.io`), update it before applying the blueprint.

## Production deployment

See [Vendor-neutral self-hosting](docs/self-hosting.md) for the hardened Docker Compose stack, TLS, secrets, observability, backups, restore drills, and the owner decisions required for a public launch.
