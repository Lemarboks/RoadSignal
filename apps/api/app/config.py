from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://saferoute:saferoute@localhost:5432/saferoute"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-secret-change-before-deploy"
    jwt_expiry_minutes: int = 60
    route_provider: str = "open"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    osrm_url: str = "https://routing.openstreetmap.de/routed-car"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    provider_timeout_seconds: float = 8.0
    provider_user_agent: str = "SafeRouteAI/1.0 (self-hostable routing client)"
    cors_origins: str = "http://localhost:3000,http://localhost:8081"
    environment: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
