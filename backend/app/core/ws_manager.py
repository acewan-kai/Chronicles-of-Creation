"""
WebSocket 连接管理器 — 按世界ID分组广播实时事件
"""
from fastapi import WebSocket
from typing import Any
import json
import asyncio


class ConnectionManager:
    """管理 WebSocket 连接，按 world_id 分组"""

    def __init__(self):
        # world_id → set of WebSocket
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, world_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(world_id, set()).add(ws)

    async def disconnect(self, world_id: str, ws: WebSocket):
        async with self._lock:
            group = self._connections.get(world_id)
            if group:
                group.discard(ws)
                if not group:
                    del self._connections[world_id]

    async def broadcast(self, world_id: str, msg_type: str, payload: Any):
        """向某世界的所有客户端广播"""
        async with self._lock:
            group = list(self._connections.get(world_id, set()))
        if not group:
            return
        data = json.dumps({"type": msg_type, "data": payload}, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in group:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                alive = self._connections.get(world_id, set())
                for ws in dead:
                    alive.discard(ws)

    @property
    def active_worlds(self) -> list[str]:
        return list(self._connections.keys())


ws_manager = ConnectionManager()
