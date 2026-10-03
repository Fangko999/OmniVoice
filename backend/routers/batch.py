from fastapi import APIRouter, HTTPException, WebSocket
from typing import Dict
from models.schemas import BatchConfigRequest, BatchState
from core.batch_processor import FastJob
from core.ws_hub import hub, spawn

router = APIRouter()

# Các job Đọc Nhanh đang nằm trong bộ nhớ
active_batches: Dict[str, FastJob] = {}


def _channel(book_id: str) -> str:
    return f"fast:{book_id}"


@router.post("/{book_id}/start")
async def start_batch(book_id: str, config: BatchConfigRequest):
    existing = active_batches.get(book_id)
    if existing and existing.state.status in ("running", "waiting"):
        raise HTTPException(status_code=409, detail="Sách này đang được xử lý")
    try:
        processor = FastJob(book_id)
        processor.state.config = config
        processor.save_state()
        active_batches[book_id] = processor
        # Chạy nền để không block API
        spawn(processor.run(callback=hub.callback_for(_channel(book_id))))
        return {"message": "Đã bắt đầu xử lý", "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{book_id}/stop")
async def stop_batch(book_id: str):
    if book_id in active_batches:
        active_batches[book_id].stop()
        return {"message": "Đã gửi lệnh dừng"}
    return {"message": "Không tìm thấy tiến trình đang chạy"}


@router.get("/{book_id}/state", response_model=BatchState)
async def get_state(book_id: str):
    if book_id in active_batches:
        return active_batches[book_id].state
    try:
        return FastJob(book_id).state
    except Exception:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạng thái sách này")


@router.websocket("/{book_id}/ws")
async def websocket_endpoint(websocket: WebSocket, book_id: str):
    try:
        job = active_batches.get(book_id) or FastJob(book_id)
        initial = job.state.model_dump_json()
    except Exception:
        initial = None
    await hub.serve(websocket, _channel(book_id), initial)
