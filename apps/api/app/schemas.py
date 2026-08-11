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
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return normalized

class RegisterRequest(LoginRequest):
    name: str = Field(min_length=2, max_length=100)
    role: Literal["driver"] = "driver"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.casefold() in {"password1234", "passwordpassword", "123456789012"}:
            raise ValueError("Choose a less common password")
        return value

class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=256)
