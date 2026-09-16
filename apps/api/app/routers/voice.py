from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import services

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=400)


@router.get("/status")
def status():
    """Whether server-side speech is usable, so the client can offer the
    option only when it will actually work."""
    return {"piper": services.piper_voice_provider.status}


@router.post("/speak")
async def speak(request: SpeakRequest):
    """Synthesise a spoken alert as WAV.

    Served from our own API rather than a separate service, so the browser
    needs no extra host configured and no cross-origin setup. Falls back to
    the browser's built-in speech when unavailable.
    """
    if not services.piper_voice_provider.available:
        raise HTTPException(503, "Server-side speech is not configured; use the browser voice")
    try:
        audio = await services.piper_voice_provider.synthesize(request.text)
    except RuntimeError as error:
        raise HTTPException(502, str(error))
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline; filename=alert.wav"},
    )
