from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://saferoute:saferoute@localhost:5432/saferoute"
    storage_backend: Literal["memory", "postgres"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    event_backend: Literal["memory", "redis"] = "memory"
    jwt_secret: str = "development-only-secret-change-before-deploy"
    jwt_issuer: str = "saferoute-api"
    jwt_audience: str = "saferoute-clients"
    jwt_expiry_minutes: int = 15
    refresh_expiry_days: int = 30
    require_auth: bool = False
    route_provider: str = "open"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    osrm_url: str = "https://routing.openstreetmap.de/routed-car"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    provider_timeout_seconds: float = 8.0
    provider_user_agent: str = "SafeRouteAI/1.0 (self-hostable routing client)"
    cors_origins: str = "http://localhost:3000,http://localhost:8081"
    environment: Literal["development", "test", "production"] = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production":
            if self.storage_backend != "postgres":
                raise ValueError("Production requires STORAGE_BACKEND=postgres")
            if self.event_backend != "redis":
                raise ValueError("Production requires EVENT_BACKEND=redis")
            if not self.require_auth:
                raise ValueError("Production requires REQUIRE_AUTH=true")
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development-"):
                raise ValueError("Production requires a random JWT_SECRET of at least 32 characters")
            if any(origin == "*" for origin in self.allowed_origins):
                raise ValueError("Wildcard CORS is forbidden in production")
        return self


settings = Settings()
