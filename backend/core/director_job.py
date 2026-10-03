"""Tab AI Đạo diễn: EPUB -> AI phân vai/nhịp -> thư mục kịch bản JSON trên ổ đĩa."""
import os
from datetime import datetime

from models.schemas import ChapterScript, DirectorState, ScriptSegment
from core import script_store
from core.account_pool import AllAccountsExhausted, PoolStopped, get_pool
from core.ai_director import AIDirector
from core.batch_processor import estimate_avg_chars, resolve_book_name
from core.epub_parser import EPUBParser
from core.job_base import JobBase, JobStopped


class DirectorJob(JobBase):
    kind = "director"
    uses_gpu = False

    def __init__(self, book_id: str):
        self.book_id = book_id
        self.epub_path = f"uploads/{book_id}.epub"
        self.parser: EPUBParser = None
        self._chapters = None
        self.director: AIDirector = None
        super().__init__(book_id)

    def _state_cls(self):
        return DirectorState

    def _new_state(self):
        parser = EPUBParser(self.epub_path)
        chapters = parser.get_chapters()
        return DirectorState(
            job_id=self.book_id,
            book_id=self.book_id,
            book_name=resolve_book_name(parser),
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
        return os.path.join(self.state.config.script_dir, "logs")

    def _log_header(self):
        c = self.state.config
        self.log(f"Chạy từ chương {c.start_chapter} đến {c.end_chapter} | Model: {c.model}")
        self.log(f"Thư mục kịch bản: {c.script_dir}")

    def prepare(self):
        """Gọi trước run(): tạo/mở thư mục kịch bản và tính các chương đã xong để bỏ qua."""
        cfg = self.state.config
        if not self.parser:
            self.parser = EPUBParser(self.epub_path)
        self._chapters = self.parser.get_chapters()
        script_store.create_or_open_project(
            cfg.script_dir, self.state.book_name, len(self._chapters),
            source_epub=os.path.abspath(self.epub_path),
            titles=[c.title for c in self._chapters],
        )
        manifest = script_store.load_manifest(cfg.script_dir)
        on_disk = set(script_store.done_chapters(cfg.script_dir))
        edited = {int(k) for k, v in manifest.chapters.items() if v.edited}
        # Chương còn khúc fallback (chưa sửa tay) -> cho AI làm lại khi chạy lại
        has_fallback = {int(k) for k, v in manifest.chapters.items() if v.fallback_chunks and not v.edited}
        skip = (edited & on_disk) if cfg.overwrite else (on_disk - has_fallback)
        self.state.completed_chapters = sorted(skip)
        self.save_state()

    async def setup(self):
        if self._chapters is None:
            self.prepare()
        pool = get_pool()
        pool.load()  # đọc lại accounts.json mỗi lần chạy (cập nhật cookie mới)
        pool.on_event = lambda msg: (self.log(msg), setattr(self.state, "current_log", msg))
        self.director = AIDirector(pool=pool, model=self.state.config.model, log=self.log)
        active = [a for a in pool.status()["accounts"] if a["status"] == "active"]
        self.log(f"Pool tài khoản: {len(pool.accounts)} tài khoản, {len(active)} đang sẵn sàng")

    async def teardown(self):
        get_pool().on_event = None

    async def process_chapter(self, n: int, callback):
        cfg = self.state.config
        if script_store.is_edited(cfg.script_dir, n):
            self.log(f"  Chương {n}: đã sửa tay -> giữ nguyên, bỏ qua AI")
            return
        chapter = self._chapters[n - 1]
        paragraphs = self.parser.get_chapter_paragraphs(chapter)

        async def progress(i, total):
            await self._emit(callback, f"Chương {n}: AI đang phân tích khúc {i}/{total}...")

        try:
            segments, fallbacks = await self.director.direct_chapter(
                paragraphs, should_stop=lambda: self._stop_flag, on_progress=progress)
        except AllAccountsExhausted as e:
            raise JobStopped(str(e))
        except PoolStopped:
            raise JobStopped("Người dùng đã dừng")

        script = ChapterScript(
            chapter=n,
            title=chapter.title or f"Chương {n}",
            model=cfg.model,
            created_at=datetime.now().isoformat(timespec="seconds"),
            segments=[ScriptSegment(**s) for s in segments],
        )
        if script_store.is_edited(cfg.script_dir, n):  # người dùng sửa tay trong lúc AI đang chạy
            self.log(f"  Chương {n}: đã được sửa tay trong lúc AI chạy -> không ghi đè")
            return
        script_store.save_chapter(cfg.script_dir, script, fallback_chunks=fallbacks)
        if fallbacks:
            self.log(f"  Chương {n}: {fallbacks} khúc dùng fallback (nên kiểm tra lại)")
