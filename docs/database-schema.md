# Database schema

UUID-keyed SQLAlchemy models cover users, fleets, fleet members, vehicles, trips, trip locations, routes, route segments, incidents, confirmations, sources, risk scores, alerts, emergency events, and audit logs. Coordinates use MySQL `GEOMETRY` with SRID 4326. The initial migration creates SPATIAL indexes for incident points, trip points, and route lines. MySQL's SRID 4326 axis semantics are normalized at the repository boundary so API GeoJSON remains longitude/latitude. JSON stores factor/evidence snapshots so historical decisions remain explainable when weights change.
