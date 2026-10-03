"""Tab Thu âm: thư mục kịch bản JSON + bảng gán 3 vai -> Kokoro -> MP3/WAV."""
import asyncio
import hashlib
import os

from models.schemas import RenderState, ROLES
from core import script_store
from core.audio_encoder import AudioEncoder
from core.job_base import JobBase
from core.tts_engine import TTSEngine


def render_job_id(script_dir: str) -> str:
    norm = os.path.normcase(os.path.abspath(script_dir))
    return "render_" + hashlib.md5(norm.encode("utf-8")).hexdigest()[:12]


class RenderJob(JobBase):
    kind = "render"
    uses_gpu = True

    def __init__(self, script_dir: str):
        self.script_dir = script_dir
        self.tts: TTSEngine = None
        super().__init__(render_job_id(script_dir))

    def _state_cls(self):
        return RenderState

    def _new_state(self):
        m = script_store.load_manifest(self.script_dir)
        avg = 2000
        first = script_store.load_chapter(self.script_dir, (script_store.done_chapters(self.script_dir) or [1])[0])
        if first:
            avg = max(100, sum(len(s.text) for s in first.segments))
        return RenderState(
            job_id=self.job_id,
            book_name=m.book_name,
            status="idle",
            total_chapters=m.total_chapters,
            completed_chapters=[],
            current_chapter=None,
            config=None,
            current_log="",
            error_msg=None,
            avg_chars_per_chapter=avg,
        )

    def out_dir(self) -> str:
        return os.path.join(self.state.config.output_dir, self.state.book_name)

    def log_dir(self):
        return os.path.join(self.out_dir(), "logs")

    def _log_header(self):
        c = self.state.config
        self.log(f"Kịch bản: {c.script_dir}")
        self.log(f"Chạy từ chương {c.start_chapter} đến {c.end_chapter}")
        self.log(f"Gán giọng: {c.voice_map}")
        self.log(f"Tốc độ tổng: {c.global_speed}x | Nghỉ mặc định: {c.gap_seconds}s | Định dạng: {c.format}")
        self.log(f"Thư mục lưu: {self.out_dir()}")

    def prepare(self):
        """Gọi trước run(). Bỏ qua chương đã có audio MỚI HƠN file kịch bản (sửa kịch bản -> render lại)."""
        cfg = self.state.config
        m = script_store.load_manifest(cfg.script_dir)
        self.state.book_name = m.book_name
        self.state.total_chapters = m.total_chapters
        done = []
        for n in script_store.done_chapters(cfg.script_dir):
            audio = os.path.join(self.out_dir(), f"chuong_{n:04d}.{cfg.format}")
            if os.path.isfile(audio) and os.path.getmtime(audio) >= os.path.getmtime(script_store.chapter_path(cfg.script_dir, n)):
                done.append(n)
        self.state.completed_chapters = done
        self.save_state()

    async def setup(self):
        vm = self.state.config.voice_map
        missing = [r for r in ROLES if not vm.get(r)]
        if missing:
            raise ValueError(f"Chưa chọn giọng cho vai: {', '.join(missing)}")
        if not self.tts:
            self.tts = TTSEngine(narrator_voice=vm["narrator"], dialogue_voice=vm["male"])
        self.log(f"TTS Engine khởi tạo thành công (Device: {self.tts.device})")

    def build_segments(self, script) -> list[dict]:
        cfg = self.state.config
        out = []
        for s in script.segments:
            text = s.text.strip()
            if not text:
                continue
            out.append({
                "voice": cfg.voice_map.get(s.voice) or cfg.voice_map["narrator"],
                "text": text,
                "speed": round(max(0.5, min(2.0, s.speed * cfg.global_speed)), 3),
                "pause_after": s.pause_after,
            })
        return out

    async def process_chapter(self, n: int, callback):
        cfg = self.state.config
        script = script_store.load_chapter(cfg.script_dir, n)
        if script is None:
            self.log(f"  Chương {n}: chưa có kịch bản, bỏ qua")
            return
        segments = self.build_segments(script)
        if not segments:
            return

        await self._emit(callback, f"Chương {n}: Đang tổng hợp âm thanh ({len(segments)} đoạn)...")
        audio = await asyncio.to_thread(self.tts.synthesize_chapter, segments, cfg.gap_seconds)
        if len(audio) == 0:
            return

        os.makedirs(self.out_dir(), exist_ok=True)
        out_path = os.path.join(self.out_dir(), f"chuong_{n:04d}.{cfg.format}")
        await self._emit(callback, f"Chương {n}: Đang lưu file vào {out_path}...")
        if cfg.format == "wav":
            await asyncio.to_thread(AudioEncoder.save_wav, audio, out_path)
        else:
            await asyncio.to_thread(AudioEncoder.save_mp3, audio, out_path)
