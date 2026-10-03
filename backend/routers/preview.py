import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import PreviewRequest
from pydantic import BaseModel
from core.tts_engine import TTSEngine
from core.audio_encoder import AudioEncoder
from core.epub_parser import EPUBParser
from core.text_processor import TextProcessor
import os
from typing import Optional

router = APIRouter()

# Global engine for preview to save load time
preview_engine = TTSEngine()

class ChapterPreviewRequest(BaseModel):
    book_id: str
    narrator_voice: str
    dialogue_voice: Optional[str] = None
    reading_mode: str = "dual"
    speed: float = 1.0

@router.post("/preview")
async def preview_audio(req: PreviewRequest):
    try:
        # Generate audio using the requested voice
        segment = {
            "voice": req.voice_id,
            "text": req.text,
            "speed": req.speed
        }
        
        audio_array = preview_engine.synthesize_segment(segment)
        if len(audio_array) == 0:
            raise HTTPException(status_code=500, detail="Không thể tạo âm thanh")
            
        # Write to in-memory bytes
        import soundfile as sf
        import numpy as np
        
        buffer = io.BytesIO()
        sf.write(buffer, audio_array, 24000, format='WAV')
        buffer.seek(0)
        
        return StreamingResponse(buffer, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preview_chapter")
async def preview_chapter(req: ChapterPreviewRequest):
    try:
        epub_path = f"uploads/{req.book_id}.epub"
        if not os.path.exists(epub_path):
            raise HTTPException(status_code=404, detail="File sách không tồn tại")
            
        parser = EPUBParser(epub_path)
        chapters = parser.get_chapters()
        if not chapters:
            raise HTTPException(status_code=400, detail="Sách không có chương nào")
            
        # Lấy 5 đoạn văn đầu của chương 1
        paragraphs = parser.get_chapter_paragraphs(chapters[0])[:5]
        full_text = "\n\n".join(paragraphs)
        
        # Xử lý đoạn
        final_segments = []
        for p in paragraphs:
            cleaned = TextProcessor.clean(p)
            if cleaned:
                if req.reading_mode == "single":
                    final_segments.append({
                        "voice": req.narrator_voice,
                        "text": cleaned,
                        "speed": req.speed
                    })
                else:
                    segments = TextProcessor.split_roles(
                        cleaned,
                        req.narrator_voice,
                        req.dialogue_voice if req.dialogue_voice else req.narrator_voice
                    )
                    for s in segments:
                        s['speed'] = req.speed
                    final_segments.extend(segments)
                
        # Tổng hợp âm thanh
        preview_engine.narrator_voice = req.narrator_voice
        preview_engine.dialogue_voice = req.dialogue_voice if req.dialogue_voice else req.narrator_voice
        
        audio_array = preview_engine.synthesize_chapter(final_segments, gap_seconds=0.4)
        if len(audio_array) == 0:
            raise HTTPException(status_code=500, detail="Không thể tạo âm thanh")
            
        # Trả về WAV
        import soundfile as sf
        import numpy as np
        buffer = io.BytesIO()
        sf.write(buffer, audio_array, 24000, format='WAV')
        buffer.seek(0)
        
        return StreamingResponse(buffer, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
