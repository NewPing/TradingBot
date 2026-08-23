"""Internal pub/sub event bus interface."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None]


@dataclass(frozen=True, slots=True)
class Event:
    """Structured bus event message."""

    topic: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """In-memory event bus with async and sync event dispatch."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            res = handler(payload)
            if inspect.isawaitable(res):
                await res

    def publish_sync(self, topic: str, payload: dict[str, Any]) -> None:
        """Synchronously notify handlers (ignoring coroutines if no event loop)."""
        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            try:
                res = handler(payload)
                if inspect.isawaitable(res):
                    import asyncio

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
            except Exception:
                pass

    def emit(self, event: Event) -> None:
        """Emit a structured Event object synchronously."""
        self.publish_sync(event.topic, event.data)
