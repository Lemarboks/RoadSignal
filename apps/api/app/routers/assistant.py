from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile

from ..ai import service
from ..ai.schemas import IncidentAnalysisRequest, IncidentAnalysisResponse, RouteExplanation
from ..auth import current_principal
from ..config import settings
from ..rate_limit import limiter
from ..repositories import repository

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/webm", "video/webm", "audio/ogg", "audio/flac", "audio/x-flac"}


@router.get("/status")
async def assistant_status():
    return await service.status()


@router.post("/incidents/analyse", response_model=IncidentAnalysisResponse)
@limiter.limit("12/minute")
async def analyse_incident(request: Request, response: Response, body: IncidentAnalysisRequest, principal=Depends(current_principal)):
    try:
        with service.inference_slot():
            return await service.analyse_incident(body, repository.list_incidents())
    except service.AssistantBusy as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "5"}) from None


@router.post("/routes/{route_id}/explain", response_model=RouteExplanation)
@limiter.limit("12/minute")
async def explain_route(request: Request, response: Response, route_id: str, principal=Depends(current_principal)):
    route = repository.get_route(route_id)
    if not route:
        raise HTTPException(404, "Route not found; analyse routes first")
    try:
        with service.inference_slot():
            return await service.explain_route(route)
    except service.AssistantBusy as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "5"}) from None


@router.post("/transcribe")
@limiter.limit("6/minute")
async def transcribe(request: Request, response: Response, file: UploadFile = File(...), principal=Depends(current_principal)):
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in AUDIO_TYPES:
        await file.close()
        raise HTTPException(415, "Upload a WAV, MP3, M4A, WebM, OGG or FLAC audio recording")
    maximum = getattr(settings, "ai_max_audio_bytes", 10_485_760)
    try:
        content = await file.read(maximum + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(422, "Audio recording is empty")
    if len(content) > maximum:
        raise HTTPException(413, "Audio recording is too large; use a shorter recording")
    try:
        with service.inference_slot():
            return await service.transcribe_audio(content, content_type)
    except service.AssistantBusy as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "5"}) from None
    except service.ModelUnavailable as error:
        raise HTTPException(503, str(error)) from None
