# GitHub Pages showcase

The Pages workflow publishes the web app from `main` to `https://lemarboks.github.io/RoadSignal/`. In the repository's **Settings → Pages**, the build source must be **GitHub Actions**. The deployment workflow builds and tests the actual static export under the Pages base path before uploading it.

With no `NEXT_PUBLIC_API_URL` repository variable, the site is a guest showcase: route comparison, public map/weather services when reachable, offline map fallback, simulated driver trips, four replay trackers and three street-sensor examples. The interface labels simulated observations and disables connected monitoring. No account, database, or local service is required to explore it. Sign-in and local administration-console links are not shown in this mode.

GitHub Pages cannot run Docker containers, n8n workflows, databases, GPS ingestion, server-side AI models or evidence-review storage. Those remain available in the [Docker monitoring deployment](monitoring-setup.md). Public routing/weather services may be unavailable or rate-limited; fallback data is labelled, and safety estimates are not guarantees.

## Optional separately hosted backend

Only after deploying the API and required services to a reachable server:

1. Add the repository **Actions variable** `NEXT_PUBLIC_API_URL` with the API's HTTPS base URL, without `/api/v1`, query parameters, credentials or a fragment. This is a public URL embedded in JavaScript, never a place for an API key.
2. Configure the API's CORS allowed origins to include `https://lemarboks.github.io` (the origin has no `/RoadSignal` suffix). Configure HTTPS and secure authentication cookies for the actual deployment. Cross-site cookie restrictions may require signing in again or using a same-site custom domain; GitHub Pages cannot proxy API requests.
3. Deploy authenticated monitoring and AI services privately behind that API. Do not expose worker, device-ingestion, database or n8n administration ports just to enable the showcase.
4. Run the Pages workflow again. Browser configuration is baked into the exported artifact, so changing a variable alone does not update an existing site.

An empty variable restores the guest-only showcase. Localhost, relative API URLs, plain HTTP and URLs containing credentials are rejected during a Pages build. Public map/weather access does not verify incidents or connect real trackers.

## Local Pages verification

From `apps/web`, build with `ROADSIGNAL_GITHUB_PAGES=true`, `GITHUB_REPOSITORY=Lemarboks/RoadSignal`, and an empty `NEXT_PUBLIC_API_URL`, then run:

```sh
pnpm build
pnpm exec playwright test --config playwright.pages.config.ts
```

The test starts a loopback-only static server at `http://127.0.0.1:4173/RoadSignal/`, checks desktop/mobile navigation and assets, exercises the replay and driver trip, and verifies that the backend-free artifact makes no API requests. For a custom domain, set `ROADSIGNAL_PAGES_BASE_PATH` to the deployment's actual base path during both build and test; the workflow gets this value from GitHub Pages automatically.
