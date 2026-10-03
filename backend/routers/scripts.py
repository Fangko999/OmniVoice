from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from models.schemas import ChapterScript
from core import script_store

router = APIRouter()


class OpenRequest(BaseModel):
    script_dir: str


@router.post("/open")
async def open_project(req: OpenRequest):
    """Mở một thư mục kịch bản bất kỳ trên ổ đĩa."""
    if not script_store.is_valid_script_dir(req.script_dir):
        raise HTTPException(status_code=400, detail="Thư mục không phải kịch bản OmniVoice (thiếu manifest.json)")
    m = script_store.load_manifest(req.script_dir)
    return {
        "script_dir": req.script_dir,
        "manifest": m,
        "available_chapters": script_store.done_chapters(req.script_dir),
    }


@router.get("/chapter", response_model=ChapterScript)
async def get_chapter(dir: str = Query(...), n: int = Query(...)):
    script = script_store.load_chapter(dir, n)
    if script is None:
        raise HTTPException(status_code=404, detail=f"Chưa có kịch bản chương {n}")
    return script


@router.put("/chapter", response_model=ChapterScript)
async def put_chapter(script: ChapterScript, dir: str = Query(...)):
    """Lưu kịch bản đã sửa tay (đánh dấu edited=true, AI sẽ không ghi đè)."""
    if not script_store.is_valid_script_dir(dir):
        raise HTTPException(status_code=400, detail="Thư mục kịch bản không hợp lệ")
    for s in script.segments:
        s.speed = round(max(0.5, min(2.0, s.speed)), 2)
        if s.pause_after is not None:
            s.pause_after = round(max(0.0, min(5.0, s.pause_after)), 2)
    script.segments = [s for s in script.segments if s.text.strip()]
    script_store.save_chapter(dir, script, user_edit=True)
    return script
