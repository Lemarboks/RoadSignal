from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class RouteAnalyseRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=160)
    destination: str = Field(min_length=2, max_length=160)
    preference: Literal["safest", "balanced", "fastest"] = "balanced"
    departure_time: datetime
    vehicle_type: Literal["car", "motorcycle", "van", "truck"] = "car"

class IncidentCreate(BaseModel):
    incident_type: str = Field(min_length=2, max_length=50)
    severity: int = Field(ge=1, le=5)
    description: str = Field(default="", max_length=1000)
    location: Coordinate
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    anonymous: bool = False
    reporter_location: Coordinate | None = None

    @field_validator("description")
    @classmethod
    def strip_markup(cls, value: str) -> str:
        return value.replace("<", "").replace(">", "").strip()

class TripLocation(BaseModel):
    location: Coordinate
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)

class RegisterRequest(LoginRequest):
    name: str = Field(min_length=2, max_length=100)
    role: Literal["driver", "fleet_manager", "administrator", "incident_moderator"] = "driver"
