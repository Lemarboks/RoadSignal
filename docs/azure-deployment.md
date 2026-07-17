# Azure deployment

Provision a resource group, Container Apps environment, PostgreSQL Flexible Server with PostGIS, Azure Cache for Redis, Maps account, Storage account, Key Vault, Log Analytics, and Application Insights. Build API/web images in ACR. Store database, Redis, JWT, and Maps secrets in Key Vault and expose them as Container Apps secret references. Run `alembic upgrade head` as a one-off Container Apps job before shifting traffic.

Use managed identities for Key Vault and Blob access, private endpoints for database/cache, TLS-only ingress, restricted CORS, minimum/maximum replicas, health probes at `/api/v1/health`, and a telemetry processor that drops precise location fields. Set `ROUTE_PROVIDER=azure` only after completing and testing the Azure adapter; retain mock mode for preview environments.
