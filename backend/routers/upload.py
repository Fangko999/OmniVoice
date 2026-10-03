import asyncio
import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from core.epub_parser import EPUBParser
from models.schemas import BookResponse

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _save_and_inspect(src, file_path: str, book_id: str) -> BookResponse:
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(src, buffer)

    parser = EPUBParser(file_path)
    chapters = parser.get_chapters()

    sample_chars = 2000
    if len(chapters) > 0:
        idx = min(1, len(chapters) - 1)
        paras = parser.get_chapter_paragraphs(chapters[idx])
        chars = sum(len(p) for p in paras)
        if chars > 100:
            sample_chars = chars

    return BookResponse(
        book_id=book_id,
        book_name=parser.get_book_title(),
        total_chapters=len(chapters),
        avg_chars_per_chapter=sample_chars
    )


@router.post("/upload", response_model=BookResponse)
async def upload_epub(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith('.epub'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ định dạng EPUB")
        
    book_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{book_id}.epub")
    
    try:
        return await asyncio.to_thread(_save_and_inspect, file.file, file_path, book_id)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file EPUB: {str(e)}")
