# API guide

Interactive OpenAPI is served at `/docs`. The implemented local flow includes health, route analysis/retrieval/start, trip retrieval/location/alerts/end, incident create/list/nearby/confirm/dispute/resolve, fleet drivers/trips/incidents/analytics, emergencies, audit logs, and `/api/v1/ws/events`.

`POST /api/v1/routes/analyse` accepts origin, destination, ISO departure time, vehicle type, and `safest|balanced|fastest`. `POST /api/v1/incidents` accepts type, severity 1–5, description, observed time, and `{latitude, longitude}`. WebSocket clients send a heartbeat message to receive events since their last poll. Route responses identify whether live open providers or the deterministic fallback supplied the geometry.
