from datetime import datetime, timezone
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

def plain_text(value: str) -> str:
    value = re.sub(r"<[^>]*>", "", value)
    if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
        raise ValueError("Control characters are not allowed")
    return value.strip()

class Coordinate(StrictModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class RouteAnalyseRequest(StrictModel):
    origin: str = Field(min_length=2, max_length=160)
    destination: str = Field(min_length=2, max_length=160)
    preference: Literal["safest", "balanced", "fastest"] = "balanced"
    departure_time: datetime
    vehicle_type: Literal["car", "motorcycle", "van", "truck"] = "car"

class IncidentCreate(StrictModel):
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
        return plain_text(value)

class TripLocation(StrictModel):
    location: Coordinate
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LoginRequest(StrictModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    website: str = Field(default="", max_length=0, exclude=True)

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

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return plain_text(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.casefold() in {"password1234", "passwordpassword", "123456789012"}:
            raise ValueError("Choose a less common password")
        return value

class RefreshRequest(StrictModel):
    refresh_token: str | None = Field(default=None, min_length=40, max_length=256)

class EmergencyCreate(StrictModel):
    location: Coordinate
