import json
import logging
import re
import secrets
import sys
from contextlib import nullcontext
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

REQUESTS = Counter(
    "roadsignal_http_requests_total",
    "HTTP requests processed by the RoadSignal API.",
    ("method", "route", "status"),
)
DURATION = Histogram(
    "roadsignal_http_request_duration_seconds",
    "RoadSignal API request duration in seconds.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": settings.service_name,
            "environment": settings.environment,
            "message": record.getMessage(),
        }
        for field in ("request_id", "trace_id", "method", "route", "status", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("roadsignal")
    logger.setLevel(settings.log_level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configure_logging()


def current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        return f"{context.trace_id:032x}" if context.is_valid else None
    except ImportError:
        return None


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()
        status = 500
        span_context = nullcontext(None)
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry import trace

            span_context = trace.get_tracer("roadsignal.http").start_as_current_span("http.request")
        with span_context as span:
            try:
                response = await call_next(request)
                status = response.status_code
                response.headers["X-Request-ID"] = request_id
                return response
            finally:
                duration = perf_counter() - started
                route = getattr(request.scope.get("route"), "path", None) or "unmatched"
                REQUESTS.labels(request.method, route, str(status)).inc()
                DURATION.labels(request.method, route).observe(duration)
                if span:
                    span.set_attribute("http.request.method", request.method)
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.response.status_code", status)
                    span.set_attribute("roadsignal.request_id", request_id)
                logger.info(
                    "http_request",
                    extra={
                        "request_id": request_id,
                        "trace_id": current_trace_id(),
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration * 1000, 2),
                    },
                )


class ProtectedMetricsApp:
    def __init__(self):
        self.metrics = make_asgi_app()

    async def __call__(self, scope, receive, send):
        token = settings.metrics_bearer_token
        if token:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"").decode("ascii", errors="ignore")
            if not secrets.compare_digest(supplied, f"Bearer {token}"):
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await self.metrics(scope, receive, send)

def configure_observability(app: FastAPI) -> None:
    app.add_middleware(ObservabilityMiddleware)
    app.mount("/metrics", ProtectedMetricsApp())
    if not settings.otel_exporter_otlp_endpoint:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
