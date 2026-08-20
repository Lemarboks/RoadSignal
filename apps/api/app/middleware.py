from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.state.request_id
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > settings.max_request_bytes
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400, headers={"X-Request-ID": request_id})
            if too_large:
                return JSONResponse({"detail": "Request body is too large"}, status_code=413, headers={"X-Request-ID": request_id})
        if request.headers.get("content-type", "").split(";", 1)[0].lower() == "multipart/form-data":
            return JSONResponse({"detail": "File uploads are not supported"}, status_code=415, headers={"X-Request-ID": request_id})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/v1/auth") else "no-cache"
        return response
