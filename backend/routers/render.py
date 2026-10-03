import json
import os
from typing import Dict

from fastapi import APIRouter, HTTPException, Query, WebSocket
from pydantic import BaseModel

from models.schemas import RenderConfigRequest, RenderState
from core import script_store
from core.job_base import STATE_DIR
from core.render_job import RenderJob, render_job_id
from core.ws_hub import hub, spawn

router = APIRouter()
active_jobs: Dict[str, RenderJob] = {}


def _channel(job_id: str) -> str:
    return f"render:{job_id}"


def _load_state(job_id: str) -> RenderState | None:
    job = active_jobs.get(job_id)
    if job:
        return job.state
    path = os.path.join(STATE_DIR, f"{job_id}.render.json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return RenderState(**json.load(f))
    return None


class StartResponse(BaseModel):
    job_id: str
    skipped: list[int]


@router.post("/start", response_model=StartResponse)
async def start_render(config: RenderConfigRequest):
    if not script_store.is_valid_script_dir(config.script_dir):
        raise HTTPException(status_code=400, detail="Thư mục không phải kịch bản OmniVoice (thiếu manifest.json)")
    job_id = render_job_id(config.script_dir)
    existing = active_jobs.get(job_id)
    if existing and existing.state.status in ("running", "waiting"):
        raise HTTPException(status_code=409, detail="Kịch bản này đang được thu âm")
    try:
        job = RenderJob(config.script_dir)
        job.state.config = config
        job.prepare()
        active_jobs[job_id] = job
        spawn(job.run(callback=hub.callback_for(_channel(job_id))))
        return StartResponse(job_id=job_id, skipped=job.state.completed_chapters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/stop")
async def stop_render(job_id: str):
    if job_id in active_jobs:
        active_jobs[job_id].stop()
        return {"message": "Đã gửi lệnh dừng"}
    return {"message": "Không tìm thấy tiến trình đang chạy"}


@router.get("/{job_id}/state", response_model=RenderState)
async def render_state(job_id: str):
    state = _load_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Không có tiến trình")
    return state


@router.get("/job_id")
async def get_job_id(script_dir: str = Query(...)):
    return {"job_id": render_job_id(script_dir)}


@router.websocket("/{job_id}/ws")
async def render_ws(websocket: WebSocket, job_id: str):
    state = _load_state(job_id)
    await hub.serve(websocket, _channel(job_id), state.model_dump_json() if state else None)
