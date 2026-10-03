from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal

class VoiceInfo(BaseModel):
    id: str
    name: str

class ChapterInfo(BaseModel):
    id: int
    title: str

class BookResponse(BaseModel):
    book_id: str
    book_name: str
    total_chapters: int
    avg_chars_per_chapter: int = 2000

class PreviewRequest(BaseModel):
    voice_id: str
    text: str
    speed: float

class BatchConfigRequest(BaseModel):
    start_chapter: int
    end_chapter: int
    narrator_voice: str
    dialogue_voice: Optional[str] = None
    reading_mode: str = "dual" # "single" or "dual"
    speed: float
    gap_seconds: float
    format: str # mp3 or wav
    output_dir: str

class BatchState(BaseModel):
    book_id: str
    book_name: str
    status: str # "idle", "waiting", "running", "paused", "completed", "error"
    total_chapters: int
    completed_chapters: List[int]
    current_chapter: Optional[int]
    config: Optional[BatchConfigRequest]
    current_log: str
    error_msg: Optional[str]
    avg_chars_per_chapter: int = 2000


# ============================================================
# Kịch bản (contract giữa Tab AI Đạo diễn và Tab Thu âm)
# ============================================================
ROLES = ("narrator", "male", "female")


class ScriptSegment(BaseModel):
    voice: Literal["narrator", "male", "female"] = "narrator"
    text: str
    speed: float = 1.0
    pause_after: Optional[float] = None
    fallback: bool = False


class ChapterScript(BaseModel):
    chapter: int
    title: str = ""
    model: str = ""
    created_at: str = ""
    edited: bool = False
    segments: List[ScriptSegment] = Field(default_factory=list)


class ManifestChapter(BaseModel):
    title: str = ""
    status: str = "pending"  # pending | done
    fallback_chunks: int = 0
    edited: bool = False


class ScriptManifest(BaseModel):
    format: str = "omnivoice-script"
    version: int = 1
    book_name: str
    source_epub: str = ""
    total_chapters: int
    chapters: Dict[str, ManifestChapter] = Field(default_factory=dict)


# ============================================================
# AI Đạo diễn
# ============================================================
class DirectorConfigRequest(BaseModel):
    book_id: str
    script_dir: str
    start_chapter: int
    end_chapter: int
    model: str = "gemini-flash"
    overwrite: bool = False  # chạy lại chương đã xong (chương đã sửa tay vẫn KHÔNG bị ghi đè)


class DirectorState(BaseModel):
    job_id: str
    book_id: str
    book_name: str
    status: str
    total_chapters: int
    completed_chapters: List[int]
    current_chapter: Optional[int]
    config: Optional[DirectorConfigRequest]
    current_log: str
    error_msg: Optional[str]
    avg_chars_per_chapter: int = 2000


# ============================================================
# Thu âm từ kịch bản
# ============================================================
class RenderConfigRequest(BaseModel):
    script_dir: str
    voice_map: Dict[str, str]  # {"narrator": "my_yen", "male": "tuan_ngoc", "female": "ngoc_huyen"}
    start_chapter: int
    end_chapter: int
    global_speed: float = 1.0
    gap_seconds: float = 0.4
    format: str = "mp3"
    output_dir: str


class RenderState(BaseModel):
    job_id: str
    book_name: str
    status: str
    total_chapters: int
    completed_chapters: List[int]
    current_chapter: Optional[int]
    config: Optional[RenderConfigRequest]
    current_log: str
    error_msg: Optional[str]
    avg_chars_per_chapter: int = 2000


# ============================================================
# Pool tài khoản Gemini
# ============================================================
class AccountStatus(BaseModel):
    name: str
    status: str  # active | cooldown | exhausted | auth_failed | disabled
    requests_today: int = 0
    daily_limit: Optional[int] = None
    until: Optional[str] = None
    last_error: Optional[str] = None
