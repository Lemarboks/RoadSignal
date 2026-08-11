import asyncio

from app.events import MemoryEventBus


def test_memory_event_stream_replays_from_cursor():
    bus = MemoryEventBus()
    first = bus.publish({"type": "trip.started"})
    bus.publish({"type": "route.risk_changed"})
    cursor, events = asyncio.run(bus.read_after(first, block_ms=1))
    assert cursor == "2-0"
    assert [event["type"] for event in events] == ["route.risk_changed"]


def test_memory_event_stream_times_out_without_failing():
    bus = MemoryEventBus()
    cursor, events = asyncio.run(bus.read_after(None, block_ms=1))
    assert cursor is None
    assert events == []
