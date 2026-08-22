"""Unit tests for WebSocket hub."""

from typing import Any

import pytest

from atlas.api.ws import ConnectionManager


class MockWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent_messages.append(message)


@pytest.mark.asyncio
async def test_websocket_connection_and_broadcast() -> None:
    manager = ConnectionManager()
    ws = MockWebSocket()

    await manager.connect(ws)  # type: ignore[arg-type]
    assert ws.accepted
    assert ws in manager.active_connections

    await manager.broadcast({"type": "ping"})
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0] == {"type": "ping"}

    manager.disconnect(ws)  # type: ignore[arg-type]
    assert ws not in manager.active_connections
