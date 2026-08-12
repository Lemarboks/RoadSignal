import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, SmallInteger, String, Text, Uuid, func
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    """Persist UTC in MySQL DATETIME and always return aware values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class Timestamped:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class User(Timestamped, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshSession(Timestamped, Base):
    __tablename__ = "refresh_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Fleet(Timestamped, Base):
    __tablename__ = "fleets"
    name: Mapped[str] = mapped_column(String(150))


class FleetMember(Timestamped, Base):
    __tablename__ = "fleet_members"
    fleet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fleets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Vehicle(Timestamped, Base):
    __tablename__ = "vehicles"
    fleet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fleets.id", ondelete="CASCADE"), index=True)
    registration: Mapped[str] = mapped_column(String(30))


class Trip(Timestamped, Base):
    __tablename__ = "trips"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    safety_score: Mapped[float] = mapped_column(Numeric(5, 2))
    alerts: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), index=True)


class TripLocation(Timestamped, Base):
    __tablename__ = "trip_locations"
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class Route(Timestamped, Base):
    __tablename__ = "routes"
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    duration_minutes: Mapped[int] = mapped_column(SmallInteger)
    distance_km: Mapped[float] = mapped_column(Numeric(8, 2))
    safety_score: Mapped[float] = mapped_column(Numeric(5, 2))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    risk_level: Mapped[str] = mapped_column(String(20))
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    difference_from_fastest: Mapped[int] = mapped_column(SmallInteger, default=0)
    breakdown: Mapped[dict] = mapped_column(JSON)
    factors: Mapped[list] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    segment_scores: Mapped[list] = mapped_column(JSON)
    geometry: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326))


class RouteSegment(Timestamped, Base):
    __tablename__ = "route_segments"
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(SmallInteger)
    geometry: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326))
    factors: Mapped[dict] = mapped_column(JSON)


class Incident(Timestamped, Base):
    __tablename__ = "incidents"
    incident_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[int] = mapped_column(SmallInteger)
    source_type: Mapped[str] = mapped_column(String(30))
    verification_status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    description: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    confirmations: Mapped[int] = mapped_column(SmallInteger, default=0)
    disputes: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    abuse_flags: Mapped[list] = mapped_column(JSON, default=list)


class IncidentConfirmation(Timestamped, Base):
    __tablename__ = "incident_confirmations"
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    response: Mapped[str] = mapped_column(String(20))


class IncidentSource(Timestamped, Base):
    __tablename__ = "incident_sources"
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    metadata_json: Mapped[dict] = mapped_column(JSON)


class RiskScore(Timestamped, Base):
    __tablename__ = "risk_scores"
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2))
    factors: Mapped[dict] = mapped_column(JSON)


class Alert(Timestamped, Base):
    __tablename__ = "alerts"
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class EmergencyEvent(Timestamped, Base):
    __tablename__ = "emergency_events"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))


class AuditLog(Timestamped, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON)
