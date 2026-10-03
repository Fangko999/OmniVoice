"""Khung chung cho mọi tác vụ chạy theo chương (Đọc nhanh, AI Đạo diễn, Thu âm kịch bản).

Lớp con chỉ cần cài:
    kind            : "fast" | "director" | "render"
    uses_gpu        : True nếu chạy Kokoro (chỉ 1 job GPU tại một thời điểm)
    _new_state()    : tạo state ban đầu (pydantic model có các trường của JobStateBase)
    _log_header()   : ghi thông tin cấu hình vào log
    setup()         : khởi tạo tài nguyên trước vòng lặp
    process_chapter(n, callback)
    log_dir()       : thư mục chứa file log
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Awaitable, Callable, Optional

STATE_DIR = "state"

# Chỉ cho phép một job dùng Kokoro tại một thời điểm (tránh tràn VRAM)
TTS_LOCK = asyncio.Lock()


class JobStopped(Exception):
    """Lớp con ném ra khi cần dừng job giữa chừng ở trạng thái 'paused' (ví dụ: hết hạn mức AI)."""


class JobBase:
    kind = "base"
    uses_gpu = False

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state_path = os.path.join(STATE_DIR, f"{job_id}.{self.kind}.json")
        self._stop_flag = False
        self._logger: Optional[logging.Logger] = None
        self.state = self._load_or_init_state()

    # ------------------------------------------------------------------ state
    def _legacy_state_path(self) -> Optional[str]:
        return None

    def _state_cls(self):
        raise NotImplementedError

    def _new_state(self):
        raise NotImplementedError

    def _load_or_init_state(self):
        for path in (self.state_path, self._legacy_state_path()):
            if path and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return self._state_cls()(**json.load(f))
        state = self._new_state()
        self.save_state(state)
        return state

    def save_state(self, state=None):
        if state is not None:
            self.state = state
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(self.state.model_dump_json(indent=2))
        os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- logging
    def log_dir(self) -> str:
        return os.path.join("outputs", "logs")

    def _log_header(self):
        pass

    def _setup_logger(self):
        log_dir = self.log_dir()
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"{self.kind}_{timestamp}.log")

        logger = logging.getLogger(f"omnivoice.{self.kind}.{self.job_id}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
        self._logger = logger

        logger.info("===== BẮT ĐẦU PHIÊN LÀM VIỆC =====")
        logger.info(f"Loại tác vụ: {self.kind}")
        logger.info(f"Tên truyện: {self.state.book_name}")
        logger.info(f"Tổng số chương: {self.state.total_chapters}")
        self._log_header()
        logger.info(f"File log: {log_file}")
        logger.info("")

    def log(self, msg: str, level: int = logging.INFO):
        if self._logger:
            self._logger.log(level, msg)

    # ---------------------------------------------------------------- control
    def stop(self):
        self._stop_flag = True

    def chapter_range(self) -> tuple[int, int]:
        cfg = self.state.config
        start = max(1, cfg.start_chapter)
        end = min(self.state.total_chapters, cfg.end_chapter)
        return start, end

    async def setup(self):
        pass

    async def teardown(self):
        pass

    async def process_chapter(self, chapter_num: int, callback):
        raise NotImplementedError

    async def _emit(self, callback, log: Optional[str] = None):
        if log is not None:
            self.state.current_log = log
        self.save_state()
        if callback:
            await callback(self.state)

    async def run(self, callback: Callable[[object], Awaitable[None]] = None):
        self._stop_flag = False
        if self.uses_gpu:
            if TTS_LOCK.locked():
                self.state.status = "waiting"
                await self._emit(callback, "Đang chờ tác vụ tạo audio khác hoàn thành...")
            async with TTS_LOCK:
                await self._run(callback)
        else:
            await self._run(callback)

    async def _run(self, callback):
        if self._stop_flag:  # bị dừng trong lúc chờ
            self.state.status = "paused"
            await self._emit(callback, "Đã tạm dừng.")
            return
        self.state.status = "running"
        self.state.error_msg = None
        self.save_state()

        try:
            self._setup_logger()
            await self.setup()
            start, end = self.chapter_range()

            for n in range(start, end + 1):
                if self._stop_flag:
                    self.state.status = "paused"
                    await self._emit(callback, "Đã tạm dừng.")
                    self.log("Người dùng tạm dừng.")
                    return
                if n in self.state.completed_chapters:
                    continue

                self.state.current_chapter = n
                await self._emit(callback, f"Đang bắt đầu chương {n}...")

                t0 = time.time()
                try:
                    await self.process_chapter(n, callback)
                except JobStopped as e:
                    self.state.status = "paused"
                    self.state.error_msg = str(e)
                    await self._emit(callback, f"Tạm dừng ở chương {n}: {e}")
                    self.log(f"⏸ Chương {n} | Tạm dừng: {e}", logging.WARNING)
                    return
                except Exception as e:
                    self.state.status = "error"
                    self.state.error_msg = f"Lỗi ở chương {n}: {e}"
                    await self._emit(callback)
                    self.log(f"✗ Chương {n} | LỖI: {e}", logging.ERROR)
                    if self._logger:
                        self._logger.exception(e)
                    return

                self.state.completed_chapters.append(n)
                await self._emit(callback, f"Hoàn thành chương {n}!")
                self.log(f"✓ Chương {n} | Hoàn thành trong {time.time() - t0:.1f}s")

            self.state.status = "completed"
            self.state.current_chapter = None
            await self._emit(callback, "Đã hoàn thành toàn bộ tác vụ!")
            self.log(f"===== HOÀN THÀNH: {len(self.state.completed_chapters)} chương =====")
        except Exception as e:
            self.state.status = "error"
            self.state.error_msg = str(e)
            await self._emit(callback)
            self.log(f"LỖI HỆ THỐNG: {e}", logging.CRITICAL)
        finally:
            try:
                await self.teardown()
            except Exception:
                pass
