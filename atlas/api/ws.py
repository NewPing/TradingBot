"""WebSocket streaming hub for live updates."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket client connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for connection in self.active_connections:
            with contextlib.suppress(Exception):
                await connection.send_json(message)


ws_manager = ConnectionManager()
