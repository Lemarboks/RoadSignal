import json
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geometry, WKTElement
from sqlalchemy import func, select

from .config import settings
from .database.models import AuditLog, Incident, Route, Trip, TripLocation as TripLocationModel
from .database.session import session_factory
from .store import AUDIT_LOG, INCIDENTS, ROUTES, TRIP_LOCATIONS, TRIPS


def serialise(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: serialise(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialise(item) for item in value]
    return value


class Repository(ABC):
    @abstractmethod
    def list_incidents(self) -> list[dict]: ...
    @abstractmethod
    def get_incident(self, incident_id: str) -> dict | None: ...
    @abstractmethod
    def save_incident(self, incident: dict) -> dict: ...
    @abstractmethod
    def save_route(self, route: dict) -> dict: ...
    @abstractmethod
    def get_route(self, route_id: str) -> dict | None: ...
    @abstractmethod
    def create_trip(self, route: dict, user_id: UUID | None = None) -> dict: ...
    @abstractmethod
    def get_trip(self, trip_id: str) -> dict | None: ...
    @abstractmethod
    def save_trip(self, trip: dict) -> dict: ...
    @abstractmethod
    def list_trips(self) -> list[dict]: ...
    @abstractmethod
    def save_trip_location(self, trip_id: str, location: dict, recorded_at: datetime) -> dict: ...
    @abstractmethod
    def list_trip_locations(self, trip_id: str, limit: int = 200) -> list[dict]: ...
    @abstractmethod
    def append_audit(self, kind: str, payload: dict, actor_id: UUID | None = None) -> dict: ...
    @abstractmethod
    def list_audit(self, limit: int = 100) -> list[dict]: ...


class MemoryRepository(Repository):
    def list_incidents(self):
        return INCIDENTS

    def get_incident(self, incident_id):
        return next((item for item in INCIDENTS if item["id"] == incident_id), None)

    def save_incident(self, incident):
        existing = self.get_incident(incident["id"])
        if existing:
            existing.update(incident)
            return existing
        INCIDENTS.insert(0, incident)
        return incident

    def save_route(self, route):
        ROUTES[route["id"]] = route
        return route

    def get_route(self, route_id):
        return ROUTES.get(route_id)

    def create_trip(self, route, user_id=None):
        trip = {
            "id": str(uuid4()), "route_id": route["id"], "status": "active", "progress": 0,
            "safety_score": route["safety_score"], "alerts": [], "started_at": datetime.now().astimezone(),
            "user_id": str(user_id) if user_id else None,
        }
        TRIPS[trip["id"]] = trip
        return trip

    def get_trip(self, trip_id):
        return TRIPS.get(trip_id)

    def save_trip(self, trip):
        TRIPS[trip["id"]] = trip
        return trip

    def list_trips(self):
        return list(TRIPS.values())

    def save_trip_location(self, trip_id, location, recorded_at):
        entry = {"trip_id": trip_id, "latitude": location["latitude"], "longitude": location["longitude"], "recorded_at": recorded_at}
        TRIP_LOCATIONS.setdefault(trip_id, []).append(entry)
        return entry

    def list_trip_locations(self, trip_id, limit=200):
        return TRIP_LOCATIONS.get(trip_id, [])[-limit:]

    def append_audit(self, kind, payload, actor_id=None):
        event = {"id": str(uuid4()), "type": kind, "occurred_at": datetime.now().astimezone().isoformat(), "payload": serialise(payload), "actor_id": str(actor_id) if actor_id else None}
        AUDIT_LOG.append(event)
        return event

    def list_audit(self, limit=100):
        return AUDIT_LOG[-limit:]


class MySQLRepository(Repository):
    @staticmethod
    def _incident_dict(model: Incident, latitude: float, longitude: float) -> dict:
        return serialise({
            "id": model.id, "incident_type": model.incident_type, "severity": model.severity,
            "source_type": model.source_type, "verification_status": model.verification_status,
            "confidence": model.confidence, "description": model.description,
            "occurred_at": model.occurred_at, "expires_at": model.expires_at,
            "location": {"latitude": latitude, "longitude": longitude},
            "confirmations": model.confirmations, "disputes": model.disputes,
            "status": model.status, "abuse_flags": model.abuse_flags or [],
        })

    def list_incidents(self):
        with session_factory()() as db:
            statement = select(
                Incident,
                func.ST_Y(Incident.location).label("latitude"),
                func.ST_X(Incident.location).label("longitude"),
            ).order_by(Incident.occurred_at.desc())
            return [self._incident_dict(model, latitude, longitude) for model, latitude, longitude in db.execute(statement)]

    def get_incident(self, incident_id):
        try:
            identifier = UUID(incident_id)
        except ValueError:
            return None
        with session_factory()() as db:
            row = db.execute(select(
                Incident,
                func.ST_Y(Incident.location),
                func.ST_X(Incident.location),
            ).where(Incident.id == identifier)).first()
            return self._incident_dict(*row) if row else None

    def save_incident(self, incident):
        with session_factory()() as db:
            identifier = UUID(incident["id"])
            model = db.get(Incident, identifier) or Incident(id=identifier)
            for field in ("incident_type", "severity", "source_type", "verification_status", "confidence", "description", "occurred_at", "expires_at", "confirmations", "disputes", "status", "abuse_flags"):
                value = incident.get(field)
                if field in {"occurred_at", "expires_at"} and isinstance(value, str):
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                setattr(model, field, value)
            point = incident["location"]
            model.location = WKTElement(f"POINT({point['longitude']} {point['latitude']})", srid=4326)
            db.add(model); db.commit()
        return incident

    @staticmethod
    def _route_dict(model: Route, geojson: str) -> dict:
        coordinates = json.loads(geojson)["coordinates"]
        return serialise({
            "id": model.external_id, "name": model.name, "duration_minutes": model.duration_minutes,
            "distance_km": model.distance_km, "safety_score": model.safety_score,
            "confidence": model.confidence, "risk_level": model.risk_level,
            "recommended": model.recommended, "difference_from_fastest": model.difference_from_fastest,
            "breakdown": model.breakdown, "factors": model.factors, "explanation": model.explanation,
            "segment_scores": model.segment_scores,
            "geometry": [{"latitude": latitude, "longitude": longitude} for longitude, latitude in coordinates],
        })

    def save_route(self, route):
        with session_factory()() as db:
            model = db.scalar(select(Route).where(Route.external_id == route["id"])) or Route(external_id=route["id"])
            for field in ("name", "duration_minutes", "distance_km", "safety_score", "confidence", "risk_level", "recommended", "difference_from_fastest", "breakdown", "factors", "explanation", "segment_scores"):
                setattr(model, field, route.get(field))
            points = route["geometry"]
            model.geometry = WKTElement("LINESTRING(" + ",".join(f"{point['longitude']} {point['latitude']}" for point in points) + ")", srid=4326)
            db.add(model); db.commit()
        return route

    def get_route(self, route_id):
        with session_factory()() as db:
            row = db.execute(select(Route, func.ST_AsGeoJSON(func.ST_SwapXY(Route.geometry))).where(Route.external_id == route_id)).first()
            return self._route_dict(*row) if row else None

    def create_trip(self, route, user_id=None):
        with session_factory()() as db:
            stored_route = db.scalar(select(Route).where(Route.external_id == route["id"]))
            model = Trip(route_id=stored_route.id if stored_route else None, user_id=user_id, status="active", progress=0, safety_score=route["safety_score"], alerts=[], started_at=datetime.now().astimezone())
            db.add(model); db.commit(); db.refresh(model)
            return self._trip_dict(model, route["id"])

    @staticmethod
    def _trip_dict(model: Trip, external_route_id: str | None):
        return serialise({"id": model.id, "route_id": external_route_id, "status": model.status, "progress": model.progress, "safety_score": model.safety_score, "alerts": model.alerts or [], "started_at": model.started_at, "user_id": model.user_id})

    def get_trip(self, trip_id):
        try: identifier = UUID(trip_id)
        except ValueError: return None
        with session_factory()() as db:
            row = db.execute(select(Trip, Route.external_id).outerjoin(Route, Trip.route_id == Route.id).where(Trip.id == identifier)).first()
            return self._trip_dict(*row) if row else None

    def save_trip(self, trip):
        with session_factory()() as db:
            model = db.get(Trip, UUID(trip["id"]))
            if not model: raise KeyError(trip["id"])
            for field in ("status", "progress", "safety_score", "alerts"):
                setattr(model, field, trip[field])
            db.commit()
        return trip

    def list_trips(self):
        with session_factory()() as db:
            rows = db.execute(select(Trip, Route.external_id).outerjoin(Route, Trip.route_id == Route.id).order_by(Trip.started_at.desc()))
            return [self._trip_dict(*row) for row in rows]

    def save_trip_location(self, trip_id, location, recorded_at):
        with session_factory()() as db:
            point = WKTElement(f"POINT({location['longitude']} {location['latitude']})", srid=4326)
            model = TripLocationModel(trip_id=UUID(trip_id), location=point, recorded_at=recorded_at)
            db.add(model); db.commit()
        return {"trip_id": trip_id, "latitude": location["latitude"], "longitude": location["longitude"], "recorded_at": recorded_at}

    def list_trip_locations(self, trip_id, limit=200):
        try:
            identifier = UUID(trip_id)
        except ValueError:
            return []
        with session_factory()() as db:
            statement = select(
                TripLocationModel.recorded_at,
                func.ST_Y(TripLocationModel.location).label("latitude"),
                func.ST_X(TripLocationModel.location).label("longitude"),
            ).where(TripLocationModel.trip_id == identifier).order_by(TripLocationModel.recorded_at.asc()).limit(min(limit, 1000))
            return [serialise({"trip_id": trip_id, "latitude": latitude, "longitude": longitude, "recorded_at": recorded_at}) for recorded_at, latitude, longitude in db.execute(statement)]

    def append_audit(self, kind, payload, actor_id=None):
        with session_factory()() as db:
            model = AuditLog(actor_id=actor_id, action=kind, details=serialise(payload))
            db.add(model); db.commit(); db.refresh(model)
            return serialise({"id": model.id, "type": kind, "occurred_at": model.created_at, "payload": payload, "actor_id": actor_id})

    def list_audit(self, limit=100):
        with session_factory()() as db:
            rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))).all()
            return [serialise({"id": row.id, "type": row.action, "occurred_at": row.created_at, "payload": row.details, "actor_id": row.actor_id}) for row in reversed(rows)]


repository: Repository = MySQLRepository() if settings.storage_backend == "mysql" else MemoryRepository()
