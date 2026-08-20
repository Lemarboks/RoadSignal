import asyncio
import json
from abc import ABC, abstractmethod

import redis
import redis.asyncio as async_redis

from .config import settings


class EventBus(ABC):
    @abstractmethod
    def publish(self, event: dict) -> str: ...
    @abstractmethod
    async def read_after(self, cursor: str | None, block_ms: int = 15_000) -> tuple[str | None, list[dict]]: ...
    @abstractmethod
    def ready(self) -> bool: ...


class MemoryEventBus(EventBus):
    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self.changed = asyncio.Event()

    def publish(self, event):
        identifier = f"{len(self.events) + 1}-0"
        self.events.append((identifier, event))
        self.changed.set()
        return identifier

    async def read_after(self, cursor, block_ms=15_000):
        position = int((cursor or "0-0").split("-", 1)[0])
        available = self.events[position:]
        if not available:
            self.changed.clear()
            try:
                await asyncio.wait_for(self.changed.wait(), block_ms / 1000)
            except TimeoutError:
                return cursor, []
            available = self.events[position:]
        return (available[-1][0], [event for _, event in available]) if available else (cursor, [])

    def ready(self):
        return True


class RedisStreamEventBus(EventBus):
    stream = "roadsignal:events"

    def __init__(self):
        self.sync_client = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=3)
        self.async_client = async_redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=20)

    def publish(self, event):
        return self.sync_client.xadd(self.stream, {"event": json.dumps(event)}, maxlen=10_000, approximate=True)

    async def read_after(self, cursor, block_ms=15_000):
        result = await self.async_client.xread({self.stream: cursor or "$"}, count=100, block=block_ms)
        if not result:
            return cursor, []
        entries = result[0][1]
        return entries[-1][0], [json.loads(fields["event"]) for _, fields in entries]

    def ready(self):
        try:
            return bool(self.sync_client.ping())
        except redis.RedisError:
            return False


event_bus: EventBus = RedisStreamEventBus() if settings.event_backend == "redis" else MemoryEventBus()
