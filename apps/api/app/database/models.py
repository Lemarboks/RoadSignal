import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text, Numeric, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from geoalchemy2 import Geography

class Base(DeclarativeBase): pass
class Timestamped:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
class User(Timestamped, Base):
    __tablename__="users"; email: Mapped[str]=mapped_column(String(255),unique=True); password_hash: Mapped[str]=mapped_column(String(255)); role: Mapped[str]=mapped_column(String(30))
class Fleet(Timestamped, Base): __tablename__="fleets"; name: Mapped[str]=mapped_column(String(150))
class FleetMember(Timestamped, Base): __tablename__="fleet_members"; fleet_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("fleets.id")); user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"))
class Vehicle(Timestamped, Base): __tablename__="vehicles"; fleet_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("fleets.id")); registration: Mapped[str]=mapped_column(String(30))
class Trip(Timestamped, Base): __tablename__="trips"; user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id")); status: Mapped[str]=mapped_column(String(30))
class TripLocation(Timestamped, Base): __tablename__="trip_locations"; trip_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("trips.id")); location: Mapped[str]=mapped_column(Geography("POINT",srid=4326)); recorded_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
class Route(Timestamped, Base): __tablename__="routes"; trip_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("trips.id")); safety_score: Mapped[float]=mapped_column(Numeric(5,2)); geometry: Mapped[str]=mapped_column(Geography("LINESTRING",srid=4326))
class RouteSegment(Timestamped, Base): __tablename__="route_segments"; route_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("routes.id")); sequence: Mapped[int]=mapped_column(SmallInteger); geometry: Mapped[str]=mapped_column(Geography("LINESTRING",srid=4326)); factors: Mapped[dict]=mapped_column(JSONB)
class Incident(Timestamped, Base):
    __tablename__="incidents"; incident_type: Mapped[str]=mapped_column(String(50)); severity: Mapped[int]=mapped_column(SmallInteger); source_type: Mapped[str]=mapped_column(String(30)); verification_status: Mapped[str]=mapped_column(String(30)); confidence: Mapped[float]=mapped_column(Numeric(4,3)); description: Mapped[str|None]=mapped_column(Text); occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); location: Mapped[str]=mapped_column(Geography("POINT",srid=4326))
class IncidentConfirmation(Timestamped, Base): __tablename__="incident_confirmations"; incident_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("incidents.id")); user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id")); response: Mapped[str]=mapped_column(String(20))
class IncidentSource(Timestamped, Base): __tablename__="incident_sources"; incident_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("incidents.id")); provider: Mapped[str]=mapped_column(String(40)); metadata_json: Mapped[dict]=mapped_column(JSONB)
class RiskScore(Timestamped, Base): __tablename__="risk_scores"; route_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("routes.id")); score: Mapped[float]=mapped_column(Numeric(5,2)); factors: Mapped[dict]=mapped_column(JSONB)
class Alert(Timestamped, Base): __tablename__="alerts"; trip_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("trips.id")); alert_type: Mapped[str]=mapped_column(String(40)); payload: Mapped[dict]=mapped_column(JSONB)
class EmergencyEvent(Timestamped, Base): __tablename__="emergency_events"; user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id")); status: Mapped[str]=mapped_column(String(30)); location: Mapped[str]=mapped_column(Geography("POINT",srid=4326))
class AuditLog(Timestamped, Base): __tablename__="audit_logs"; actor_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True)); action: Mapped[str]=mapped_column(String(80)); details: Mapped[dict]=mapped_column(JSONB)
