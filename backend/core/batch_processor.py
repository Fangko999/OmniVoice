"""Chế độ Đọc Nhanh: EPUB -> tách vai theo ngoặc kép -> Kokoro -> MP3/WAV."""
import asyncio
import os

from models.schemas import BatchState
from core.job_base import JobBase
from core.epub_parser import EPUBParser
from core.text_processor import TextProcessor
from core.tts_engine import TTSEngine
from core.audio_encoder import AudioEncoder


def estimate_avg_chars(parser: EPUBParser, chapters) -> int:
    sample_chars = 2000
    if chapters:
        idx = min(1, len(chapters) - 1)
        chars = sum(len(p) for p in parser.get_chapter_paragraphs(chapters[idx]))
        if chars > 100:
            sample_chars = chars
    return sample_chars


def resolve_book_name(parser: EPUBParser, book_name: str = "") -> str:
    if not book_name or book_name == "Unknown":
        try:
            title_meta = parser.book.get_metadata('DC', 'title')
            if title_meta:
                book_name = title_meta[0][0]
        except Exception:
            pass
    return book_name or "Unknown"


def output_root(output_dir: str, book_name: str) -> str:
    return os.path.join(output_dir, book_name) if output_dir else os.path.join("outputs", book_name)


class FastJob(JobBase):
    kind = "fast"
    uses_gpu = True

    def __init__(self, book_id: str, book_name: str = ""):
        self.book_id = book_id
        self.epub_path = f"uploads/{book_id}.epub"
        self._init_book_name = book_name
        self.parser: EPUBParser = None
        self.tts: TTSEngine = None
        self._chapters = None
        super().__init__(book_id)
        self.book_name = self.state.book_name

    def _legacy_state_path(self):
        return os.path.join("state", f"{self.book_id}.json")

    def _state_cls(self):
        return BatchState

    def _new_state(self):
        parser = EPUBParser(self.epub_path)
        chapters = parser.get_chapters()
        return BatchState(
            book_id=self.book_id,
            book_name=resolve_book_name(parser, self._init_book_name),
            status="idle",
            total_chapters=len(chapters),
            completed_chapters=[],
            current_chapter=None,
            config=None,
            current_log="",
            error_msg=None,
            avg_chars_per_chapter=estimate_avg_chars(parser, chapters),
        )

    def log_dir(self):
        return os.path.join(output_root(self.state.config.output_dir, self.book_name), "logs")

    def _log_header(self):
        c = self.state.config
        self.log(f"Chạy từ chương {c.start_chapter} đến {c.end_chapter}")
        self.log(f"Giọng dẫn truyện: {c.narrator_voice}")
        self.log(f"Giọng lời thoại: {c.dialogue_voice or '(Cùng giọng dẫn truyện)'}")
        self.log(f"Chế độ đọc: {c.reading_mode}")
        self.log(f"Tốc độ: {c.speed}x | Khoảng nghỉ: {c.gap_seconds}s | Định dạng: {c.format}")
        self.log(f"Thư mục lưu: {output_root(c.output_dir, self.book_name)}")

    async def setup(self):
        config = self.state.config
        if not config:
            raise ValueError("No config set in state")
        if not self.parser:
            self.parser = EPUBParser(self.epub_path)
        self._chapters = self.parser.get_chapters()
        if not self.tts:
            self.tts = TTSEngine(
                narrator_voice=config.narrator_voice,
                dialogue_voice=config.dialogue_voice or config.narrator_voice,
            )
        self.log(f"TTS Engine khởi tạo thành công (Device: {self.tts.device})")
        self.log(f"EPUB đã phân tích xong: {len(self._chapters)} chương")

    def build_segments(self, paragraphs: list[str]) -> list[dict]:
        cfg = self.state.config
        segments = []
        for p in paragraphs:
            cleaned = TextProcessor.clean(p)
            if not cleaned:
                continue
            if cfg.reading_mode == "single":
                segments.append({"voice": cfg.narrator_voice, "text": cleaned, "speed": cfg.speed})
            else:
                for s in TextProcessor.split_roles(cleaned, cfg.narrator_voice, cfg.dialogue_voice or cfg.narrator_voice):
                    s['speed'] = cfg.speed
                    segments.append(s)
        return segments

    async def process_chapter(self, chapter_num: int, callback):
        cfg = self.state.config
        paragraphs = self.parser.get_chapter_paragraphs(self._chapters[chapter_num - 1])
        if not paragraphs:
            return
        segments = self.build_segments(paragraphs)

        await self._emit(callback, f"Chương {chapter_num}: Đang tổng hợp âm thanh Kokoro...")
        audio = await asyncio.to_thread(self.tts.synthesize_chapter, segments, cfg.gap_seconds)
        if len(audio) == 0:
            return

        out_dir = output_root(cfg.output_dir, self.book_name)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"chuong_{chapter_num:04d}.{cfg.format}")
        await self._emit(callback, f"Chương {chapter_num}: Đang lưu file vào {out_path}...")

        if cfg.format == "wav":
            await asyncio.to_thread(AudioEncoder.save_wav, audio, out_path)
        else:
            await asyncio.to_thread(AudioEncoder.save_mp3, audio, out_path)


# Tên cũ, giữ để tương thích
BatchProcessor = FastJob
