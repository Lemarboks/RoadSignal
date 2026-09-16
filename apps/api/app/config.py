from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://roadsignal:roadsignal@localhost:3306/roadsignal?charset=utf8mb4"
    storage_backend: Literal["memory", "mysql"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    event_backend: Literal["memory", "redis"] = "memory"
    jwt_secret: str = "development-only-secret-change-before-deploy"
    jwt_issuer: str = "roadsignal-api"
    jwt_audience: str = "roadsignal-clients"
    jwt_expiry_minutes: int = 15
    refresh_expiry_days: int = 30
    refresh_cookie_name: str = "roadsignal_refresh"
    max_request_bytes: int = 1_048_576
    require_auth: bool = False
    route_provider: str = "open"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    osrm_url: str = "https://routing.openstreetmap.de/routed-car"
    valhalla_url: str = "http://valhalla:8002"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    eonet_url: str = "https://eonet.gsfc.nasa.gov/api/v3/events"
    hazard_bbox_south: float = -35.0
    hazard_bbox_north: float = -32.5
    hazard_bbox_west: float = 17.5
    hazard_bbox_east: float = 20.0
    provider_timeout_seconds: float = 8.0
    cctv_timeout_seconds: float = 25.0
    hazard_avoidance_enabled: bool = True
    hazard_avoid_wildfire_radius_km: float = 0.6
    hazard_avoid_severe_event_radius_km: float = 0.8
    hazard_avoid_crime_percentile: float = 0.9
    # Valhalla rejects the request (error 167) above 10km of combined
    # exclusion perimeter, so stay clear of that ceiling.
    hazard_avoid_circumference_budget_m: float = 9000.0
    # Optional local neural speech. Point at the MIT-licensed rhasspy/piper
    # binary and a voice model; left empty the API reports it unavailable and
    # clients keep using the browser voice.
    piper_binary: str = ""
    piper_voice_model: str = ""
    piper_timeout_seconds: float = 30.0
    provider_user_agent: str = "RoadSignal/1.0 (self-hostable routing client)"
    cors_origins: str = "http://localhost:3000,http://localhost:8081"
    environment: Literal["development", "test", "production"] = "development"
    service_name: str = "roadsignal-api"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    otel_exporter_otlp_endpoint: str = ""
    metrics_bearer_token: str = ""
    ai_enabled: bool = False
    ai_base_url: str = ""
    ai_model: str = "gpt-oss-20b"
    ai_timeout_seconds: float = 20.0
    embedding_base_url: str = ""
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    reranker_base_url: str = ""
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"
    whisper_base_url: str = ""
    whisper_model: str = "small"
    ai_max_audio_bytes: int = 10_485_760
    monitoring_token_file: str = ""
    monitoring_stale_seconds: int = Field(default=120, ge=30, le=86400)
    verification_base_url: str = ""
    vision_base_url: str = ""
    model_worker_token_file: str = ""
    monitoring_model_timeout_seconds: float = Field(default=90, ge=1, le=120)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production":
            if self.storage_backend != "mysql":
                raise ValueError("Production requires STORAGE_BACKEND=mysql")
            if self.event_backend != "redis":
                raise ValueError("Production requires EVENT_BACKEND=redis")
            if not self.require_auth:
                raise ValueError("Production requires REQUIRE_AUTH=true")
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development-"):
                raise ValueError("Production requires a random JWT_SECRET of at least 32 characters")
            if len(self.metrics_bearer_token) < 32:
                raise ValueError("Production requires a random METRICS_BEARER_TOKEN of at least 32 characters")
            if any(origin == "*" for origin in self.allowed_origins):
                raise ValueError("Wildcard CORS is forbidden in production")
            if any(not origin.startswith("https://") for origin in self.allowed_origins):
                raise ValueError("Production CORS origins must use HTTPS")
        return self


settings = Settings()
