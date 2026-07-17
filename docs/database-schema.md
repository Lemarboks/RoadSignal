# Database schema

UUID-keyed SQLAlchemy models cover users, fleets, fleet members, vehicles, trips, trip locations, routes, route segments, incidents, confirmations, sources, risk scores, alerts, emergency events, and audit logs. Coordinates use PostGIS `GEOGRAPHY` with SRID 4326. The initial migration enables PostGIS and creates GiST indexes for incident points, trip points, and route lines. JSONB stores factor/evidence snapshots so historical decisions remain explainable when weights change.
