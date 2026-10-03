from typing import Dict

from fastapi import APIRouter, HTTPException, WebSocket

from models.schemas import DirectorConfigRequest, DirectorState
from core.director_job import DirectorJob
from core.ws_hub import hub, spawn

router = APIRouter()
active_jobs: Dict[str, DirectorJob] = {}


def _channel(book_id: str) -> str:
    return f"director:{book_id}"


def _get_job(book_id: str) -> DirectorJob:
    return active_jobs.get(book_id) or DirectorJob(book_id)


@router.post("/start")
async def start_director(config: DirectorConfigRequest):
    existing = active_jobs.get(config.book_id)
    if existing and existing.state.status == "running":
        raise HTTPException(status_code=409, detail="Sách này đang được AI xử lý")
    if not config.script_dir.strip():
        raise HTTPException(status_code=400, detail="Chưa chọn thư mục lưu kịch bản")
    try:
        job = DirectorJob(config.book_id)
        job.state.config = config
        job.prepare()
        active_jobs[config.book_id] = job
        spawn(job.run(callback=hub.callback_for(_channel(config.book_id))))
        return {"message": "Đã bắt đầu AI đạo diễn", "skipped": job.state.completed_chapters}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{book_id}/stop")
async def stop_director(book_id: str):
    if book_id in active_jobs:
        active_jobs[book_id].stop()
        return {"message": "Đã gửi lệnh dừng"}
    return {"message": "Không tìm thấy tiến trình đang chạy"}


@router.get("/{book_id}/state", response_model=DirectorState)
async def director_state(book_id: str):
    try:
        return _get_job(book_id).state
    except Exception:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách")


@router.websocket("/{book_id}/ws")
async def director_ws(websocket: WebSocket, book_id: str):
    try:
        initial = _get_job(book_id).state.model_dump_json()
    except Exception:
        initial = None
    await hub.serve(websocket, _channel(book_id), initial)
