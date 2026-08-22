"""Internal pub/sub event bus interface."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    """In-memory event bus with async event dispatch."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            await handler(payload)
