from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .middleware import BoundedAudioUploadMiddleware, SecurityHeadersMiddleware
from .observability import configure_observability
from .rate_limit import limiter
from .routers import assistant, authentication, emergencies, fleet, hazards, incidents, map, monitoring, realtime, routes, system, trips, voice
from .routers import monitoring_models


def create_app() -> FastAPI:
    application = FastAPI(
        title="RoadSignal API",
        version="0.1.0",
        description="Route-risk decision support. Scores are estimates, not guarantees of safety.",
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(BoundedAudioUploadMiddleware)
    configure_observability(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-RoadSignal-Client"],
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    for router in (
        authentication.router,
        system.router,
        routes.router,
        trips.router,
        incidents.router,
        assistant.router,
        map.router,
        hazards.router,
        monitoring.router,
        monitoring_models.router,
        fleet.router,
        emergencies.router,
        realtime.router,
        voice.router,
    ):
        application.include_router(router)
    return application


app = create_app()
