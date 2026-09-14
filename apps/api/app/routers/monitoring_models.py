"""Authenticated, read-only model proxies; never publish incidents or alter risk."""
import base64
import binascii
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..auth import Principal, current_principal, require_roles
from ..config import settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring-models"])
operator = require_roles("administrator", "incident_moderator")
MAX_FRAME_BODY = 768 * 1024
MAX_IMAGE_BYTES = 512 * 1024


class FrameBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    frame_index: int = Field(ge=0, lt=1800)
    image_base64: str = Field(min_length=4, max_length=699052)
    source: Literal["demo", "authorized"]
    authorization_confirmed: bool = Field(default=False, strict=True)
    frame_rate: int = Field(default=5, ge=1, le=30)

    @field_validator("image_base64")
    @classmethod
    def bounded_image(cls, value):
        try:
            image = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Frame must be plain base64") from None
        if len(image) > MAX_IMAGE_BYTES:
            raise ValueError("Frame exceeds 512 KiB")
        if not (image.startswith(b"\x89PNG\r\n\x1a\n") or image.startswith(b"\xff\xd8\xff")):
            raise ValueError("Only PNG/JPEG frames are supported")
        return value

    @model_validator(mode="after")
    def require_permission(self):
        if self.source == "authorized" and not self.authorization_confirmed:
            raise ValueError("Permission to process camera frames must be confirmed")
        return self


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=3000)
    source_url: AnyHttpUrl
    observed_at: datetime | None = None

    @field_validator("source_url")
    @classmethod
    def bounded_url(cls, value):
        if len(str(value)) > 2048 or urlsplit(str(value)).username is not None:
            raise ValueError("Source URL is too long or contains credentials")
        return value

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Observation timestamp requires a timezone")
        return value


class EvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    claim: str = Field(min_length=1, max_length=500)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=5)


async def parse_bounded(request, schema, byte_limit):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(415, "Send application/json")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > byte_limit:
            raise HTTPException(413, "Model request exceeds the upload limit")
        chunks.append(chunk)
    try:
        return schema.model_validate_json(b"".join(chunks))
    except ValidationError:
        # Pydantic errors may include a full base64 frame or sensitive source
        # text, so do not return their input fields to callers or logs.
        raise HTTPException(422, "Invalid or oversized model request; check the documented fields and limits") from None


def worker_headers():
    if not settings.model_worker_token_file:
        return {}
    try:
        with Path(settings.model_worker_token_file).open(encoding="utf-8") as handle:
            token = handle.read(514).strip()
        if not 32 <= len(token) <= 512 or not token.isascii():
            raise ValueError("Invalid credential")
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(503, "Model worker credential is unavailable") from None
    return {"X-Worker-Token": token}


def worker_url(base, path):
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise HTTPException(503, "Model worker is not configured")
    return base.rstrip("/") + path


async def call_worker(base, path, method="GET", payload=None, timeout=None):
    url = worker_url(base, path)
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.monitoring_model_timeout_seconds,
                                     follow_redirects=False, trust_env=False) as client:
            response = await client.request(method, url, json=payload, headers=worker_headers())
        if response.status_code == 429:
            raise HTTPException(429, "Model worker busy; retry later", headers={"Retry-After": "2"})
        if response.status_code in {409, 413, 422}:
            raise HTTPException(response.status_code, "Model worker rejected the frame sequence or input limits")
        if response.status_code != 200:
            raise HTTPException(503, "Model worker is unavailable or still loading")
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Unexpected response")
        return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Model worker is temporarily unavailable") from None


def scoped_session(principal, session_id):
    return hashlib.sha256(f"{principal.id}:{session_id}".encode()).hexdigest()


@router.get("/vision/status")
async def vision_status(principal: Principal = Depends(current_principal)):
    configured = bool(settings.vision_base_url)
    try:
        response = await call_worker(settings.vision_base_url, "/ready", timeout=3)
        available = response.get("status") == "ready" and response.get("role") == "vision"
    except HTTPException:
        available = False
    return {"configured": configured, "available": available, "requires_review": True,
            "demo_allowed": True, "authorized_frames_allowed": principal.role in {"administrator", "incident_moderator"},
            "max_image_bytes": MAX_IMAGE_BYTES, "max_request_bytes": MAX_FRAME_BODY,
            "notice": "Vehicle-box estimates only. No camera feed or real traffic accuracy is implied."}


@router.post("/vision/frames")
async def vision_frames(request: Request, principal: Principal = Depends(current_principal)):
    body = await parse_bounded(request, FrameBody, MAX_FRAME_BODY)
    if body.source == "authorized" and principal.role not in {"administrator", "incident_moderator"}:
        raise HTTPException(403, "Only an incident operator may submit authorized camera frames")
    payload = body.model_dump()
    payload["session_id"] = scoped_session(principal, body.session_id)
    response = await call_worker(settings.vision_base_url, "/frames", "POST", payload)
    result = {key: response[key] for key in ("model", "revision", "tracker", "frame_index", "frame_size", "tracks", "counts", "warnings") if key in response}
    result.update(session_id=body.session_id, source=body.source, requires_review=True, retained_images=False)
    return result


@router.delete("/vision/sessions/{session_id}")
async def delete_vision_session(session_id: str, principal: Principal = Depends(current_principal)):
    if len(session_id) > 64 or not session_id or any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in session_id):
        raise HTTPException(422, "Invalid session id")
    await call_worker(settings.vision_base_url, "/sessions/" + scoped_session(principal, session_id), "DELETE")
    return {"deleted": True}


@router.post("/evidence/compare")
async def evidence_compare(request: Request, principal: Principal = Depends(operator)):
    body = await parse_bounded(request, EvidenceBody, 96 * 1024)
    response = await call_worker(settings.verification_base_url, "/verify", "POST", body.model_dump(mode="json"))
    result = {key: response[key] for key in ("model", "revision", "sources", "warnings") if key in response}
    result.update(assessment="textual_consistency_only", requires_review=True, incident_published=False)
    return result
