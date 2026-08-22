"""Unit tests for event bus."""

from typing import Any

import pytest

from atlas.core.bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe() -> None:
    bus = EventBus()
    received_events: list[dict[str, Any]] = []

    async def sample_handler(payload: dict[str, Any]) -> None:
        received_events.append(payload)

    bus.subscribe("order.filled", sample_handler)
    await bus.publish("order.filled", {"order_id": "123", "qty": 10})

    assert len(received_events) == 1
    assert received_events[0]["order_id"] == "123"
