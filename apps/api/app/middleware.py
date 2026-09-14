from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

AUDIO_PATH = "/api/v1/assistant/transcribe"


class BoundedAudioUploadMiddleware:
    """Bound multipart bytes even when a client omits Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != AUDIO_PATH:
            return await self.app(scope, receive, send)
        messages, size = [], 0
        limit = settings.ai_max_audio_bytes + 65536  # multipart headers
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                return await JSONResponse({"detail": "Audio upload is too large"}, status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        position = 0
        async def bounded_receive():
            nonlocal position
            if position < len(messages):
                message = messages[position]
                position += 1
                return message
            return await receive()
        await self.app(scope, bounded_receive, send)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.state.request_id
        audio_upload = request.url.path == AUDIO_PATH and request.method == "POST"
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                limit = settings.ai_max_audio_bytes + 65536 if audio_upload else settings.max_request_bytes
                too_large = int(content_length) > limit
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400, headers={"X-Request-ID": request_id})
            if too_large:
                return JSONResponse({"detail": "Request body is too large"}, status_code=413, headers={"X-Request-ID": request_id})
        if not audio_upload and request.headers.get("content-type", "").split(";", 1)[0].lower() == "multipart/form-data":
            return JSONResponse({"detail": "File uploads are not supported"}, status_code=415, headers={"X-Request-ID": request_id})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=(self)"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/v1/auth") else "no-cache"
        return response
