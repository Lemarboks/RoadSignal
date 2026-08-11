import asyncio
import uuid

import pytest

from app.config import settings
from app.events import RedisStreamEventBus

pytestmark = pytest.mark.skipif(settings.event_backend != "redis", reason="requires Redis")


def test_redis_stream_publishes_and_replays_from_cursor():
    asyncio.run(_exercise_redis_stream())


async def _exercise_redis_stream():
    bus = RedisStreamEventBus()
    bus.stream = f"saferoute:test:{uuid.uuid4().hex}"
    try:
        assert bus.ready()
        first = bus.publish({"type": "trip.started", "payload": {"trip_id": "one"}})
        second = bus.publish({"type": "route.risk_changed", "payload": {"trip_id": "one"}})
        cursor, events = await bus.read_after("0-0", block_ms=100)
        assert cursor == second
        assert first != second
        assert [event["type"] for event in events] == ["trip.started", "route.risk_changed"]
    finally:
        bus.sync_client.delete(bus.stream)
        await bus.async_client.aclose()
