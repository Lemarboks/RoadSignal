# SafeRoute AI

SafeRoute AI is a functional demonstration MVP for comparing driving routes by travel time and confidence-weighted risk. It includes a Next.js fleet/driver console, Expo mobile app, FastAPI service, deterministic Cape Town mock providers, PostGIS schema, Redis-ready realtime architecture, and a credential-free simulation flow. The web map uses open-source MapLibre GL and no-key OpenFreeMap/OpenStreetMap-based tiles, with an offline schematic fallback.

> All included people, trips, incidents, risk zones, and scores are demonstration data. A score is decision support based on available data; it is not a guarantee of safety.

## Quick start

Prerequisites: Node 20+, pnpm 10+, Python 3.12+, and optionally Docker Desktop.

```bash
git clone <repository>
cd SafeRouteAI
cp .env.example .env
docker compose up -d db redis
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

Open <http://localhost:3000>; API documentation is at <http://localhost:8000/docs>. The web UI has deterministic route and incident fallbacks, so its complete interaction can still be demonstrated on free static hosting when the API is unavailable. The static production artifact is written to `dist/` by `pnpm build`.

Run mobile separately with `pnpm dev:mobile`. Run the API plus data services with `docker compose up --build`. For migrations: `cd apps/api && alembic upgrade head`. The current API automatically provides demonstration data; a production repository-backed seed command is a documented follow-up.

## Verification

```bash
pnpm typecheck
pnpm build
pnpm build:all
pnpm test
python -m pytest apps/api/tests
```

## Environment

Copy `.env.example`. Required in production: `DATABASE_URL`, `REDIS_URL`, a strong `JWT_SECRET`, `ROUTE_PROVIDER`, and permitted `CORS_ORIGINS`. Browser/mobile URLs are `NEXT_PUBLIC_API_URL` and `EXPO_PUBLIC_API_URL`. The default web map and mock routes require no API key or billing account.

## Repository

- `apps/web` — operational web console and simulator
- `apps/mobile` — Expo driver experience and simulated SOS
- `apps/api` — FastAPI domains, scoring engines, providers, schema, and tests
- `packages/types` and `packages/api-client` — shared TypeScript contract
- `docs` — implementation, architecture, risk, privacy, security, deployment, and demo notes
- `infrastructure/azure` — Azure deployment guidance/template entry point

See [demo instructions](docs/demo.md) and [known limitations](docs/architecture.md#known-limitations).
