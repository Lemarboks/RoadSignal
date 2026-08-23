import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import decode_access_token
from ..config import settings
from ..events import event_bus

router = APIRouter(prefix="/api/v1", tags=["realtime"])


@router.websocket("/ws/events")
async def websocket_events(socket: WebSocket):
    await socket.accept()
    if settings.require_auth:
        try:
            message = await asyncio.wait_for(socket.receive_json(), timeout=5)
            if message.get("type") != "authenticate":
                raise ValueError("authentication message required")
            decode_access_token(message.get("access_token", ""))
        except Exception:
            await socket.close(code=4401, reason="Authentication required")
            return
    cursor = socket.query_params.get("cursor")
    try:
        while True:
            cursor, events = await event_bus.read_after(cursor)
            payload = {"cursor": cursor, "events": events}
            if not events:
                payload["type"] = "heartbeat"
            await socket.send_json(payload)
    except WebSocketDisconnect:
        pass
