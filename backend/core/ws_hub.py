"""Quản lý WebSocket theo kênh (mỗi job một kênh) và tác vụ đang chạy."""
import asyncio
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect


class WSHub:
    def __init__(self):
        self.channels: Dict[str, list[WebSocket]] = {}

    async def broadcast(self, key: str, text: str):
        for ws in list(self.channels.get(key, [])):
            try:
                await ws.send_text(text)
            except Exception:
                pass

    def callback_for(self, key: str):
        async def _cb(state):
            await self.broadcast(key, state.model_dump_json())
        return _cb

    async def serve(self, websocket: WebSocket, key: str, initial_json: str | None):
        await websocket.accept()
        self.channels.setdefault(key, []).append(websocket)
        if initial_json:
            try:
                await websocket.send_text(initial_json)
            except Exception:
                pass
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            conns = self.channels.get(key, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                self.channels.pop(key, None)


hub = WSHub()

# Giữ tham chiếu tới task nền để không bị garbage-collect
_background_tasks: set[asyncio.Task] = set()


def spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
