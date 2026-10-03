import copy
import os
import sys
import numpy as np
import threading
import torch
from concurrent.futures import ThreadPoolExecutor

# Luôn ưu tiên Kokoro-Vietnamese nằm trong thư mục dự án (kể cả khi máy có bản `pip install -e`
# trỏ tới đường dẫn cũ) -> chuyển cả thư mục dự án đi nơi khác vẫn chạy.
kokoro_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Kokoro-Vietnamese/src'))
if os.path.isdir(kokoro_path) and kokoro_path not in sys.path:
    sys.path.insert(0, kokoro_path)

from kokoro_vietnamese import KokoroVietnamese
import kokoro_vietnamese.core
import re

# Khắc phục lỗi Kokoro đọc các từ tiếng Việt không dấu thành tiếng Anh (to -> too)
original_phonemize = kokoro_vietnamese.core.phonemize

def patched_phonemize(text: str) -> str:
    ps = original_phonemize(text)
    replacements = {
        r'(?<!\S)tuː(?!\S)': 'tˈɔ',         # to
        r'(?<!\S)nˈoʊ(?!\S)': 'nˈɔ',       # no
        r'(?<!\S)dˈuː(?!\S)': 'zˈɔ',       # do
        r'(?<!\S)ʂˈoʊ(?!\S)': 'ʂˈɔ',       # so
        r'(?<!\S)mˈiː(?!\S)': 'mˈɛ',       # me
        r'(?<!\S)bˈiː(?!\S)': 'bˈɛ',       # be
        r'(?<!\S)hiː(?!\S)': 'hˈɛ',        # he
        r'(?<!\S)mˈaɪ(?!\S)': 'mˈi',       # my
        r'(?<!\S)bˈaɪ(?!\S)': 'bˈi',       # by
    }
    for pattern, replacement in replacements.items():
        ps = re.sub(pattern, replacement, ps)
    return ps

kokoro_vietnamese.core.phonemize = patched_phonemize

# ----------------------------------------------------------------------------
# Cache toàn cục: MỘT model Kokoro cho mỗi device, mỗi giọng chỉ nạp thêm voicepack
# (vài MB). Trước đây mỗi giọng / mỗi job nạp một bản model riêng -> tốn VRAM và
# không được giải phóng giữa các lần chạy.
# ----------------------------------------------------------------------------
_CACHE_LOCK = threading.Lock()
_BASE_ENGINES: dict[str, KokoroVietnamese] = {}            # device -> engine gốc (giữ model)
_VOICE_ENGINES: dict[tuple[str, str], KokoroVietnamese] = {}  # (device, voice) -> engine
# Một ThreadPool dùng chung để tránh tạo/hủy thread liên tục (rò rỉ RAM)
_EXECUTOR = ThreadPoolExecutor(max_workers=3)

# Kokoro ném lỗi nếu một câu > 510 âm vị (~370 ký tự tiếng Việt). Chia nhỏ trước cho an toàn.
MAX_PHONEMES = 480
LONG_SENTENCE_CHARS = 300   # câu ngắn hơn thì không cần đếm âm vị
PIECE_CHARS = 250


def _split_long(sentence: str) -> list[str]:
    """Chia câu quá dài tại dấu phẩy/chấm phẩy/hai chấm; không có thì chia đôi theo từ."""
    core = kokoro_vietnamese.core
    if len(sentence) < LONG_SENTENCE_CHARS or len(core.phonemize(sentence)) <= MAX_PHONEMES:
        return [sentence]
    pieces, cur = [], ""
    for part in re.split(r"(?<=[,;:])\s+", sentence):
        if cur and len(cur) + len(part) + 1 > PIECE_CHARS:
            pieces.append(cur)
            cur = part
        else:
            cur = f"{cur} {part}".strip()
    if cur:
        pieces.append(cur)
    if len(pieces) < 2:
        words = sentence.split()
        if len(words) < 2:
            return [sentence]
        mid = len(words) // 2
        pieces = [" ".join(words[:mid]), " ".join(words[mid:])]
    return [x for p in pieces for x in _split_long(p)]


def safe_pieces(text: str) -> list[str]:
    """Các đoạn đều dưới giới hạn âm vị của Kokoro; [text] nếu không có câu nào quá dài."""
    sentences = kokoro_vietnamese.core.split_text(text)
    if all(len(s) < LONG_SENTENCE_CHARS for s in sentences):
        return [text]
    return [p for s in sentences for p in _split_long(s)]


def _load_voice_engine(device: str, voice_id: str) -> KokoroVietnamese:
    key = (device, voice_id)
    with _CACHE_LOCK:
        if key in _VOICE_ENGINES:
            return _VOICE_ENGINES[key]
        base = _BASE_ENGINES.get(device)
        if base is None:
            engine = KokoroVietnamese(device=device, voice=voice_id)
            _BASE_ENGINES[device] = engine
        else:
            core = kokoro_vietnamese.core
            engine = copy.copy(base)  # dùng chung base.model
            filename = core.resolve_voicepack_filename(voice_id, None)
            engine.voicepack_path = core._download_or_resolve(
                core.DEFAULT_HF_REPO_ID, core.DEFAULT_VOICEPACK_FILE, filename)
            engine.voicepack = torch.load(engine.voicepack_path, map_location='cpu', weights_only=True)
        _VOICE_ENGINES[key] = engine
        return engine


class TTSEngine:
    VOICES = {
        "diem_trinh": "Diễm Trinh", "hung_thinh": "Hưng Thịnh",
        "mai_linh": "Mai Linh", "mai_loan": "Mai Loan",
        "manh_dung": "Mạnh Dũng", "my_yen": "Mỹ Yến",
        "ngoc_huyen": "Ngọc Huyền", "phat_tai": "Phát Tài",
        "thanh_dat": "Thành Đạt", "thuc_trinh": "Thục Trinh",
        "tuan_ngoc": "Tuấn Ngọc", "storyvert": "Storyvert",
        "duc_an": "Đức An", "duc_duy": "Đức Duy"
    }
    
    SAMPLE_TEXT = "Giữa một buổi chiều yên tĩnh, cô ấy kể lại câu chuyện bằng một giọng nói ấm áp và chậm rãi."
    
    def __init__(self, narrator_voice: str = "my_yen", dialogue_voice: str = "thanh_dat", device: str = None):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        # Giữ lại để tương thích với code cũ (preview, log). Giọng thực tế lấy từ segment['voice'].
        self.narrator_voice = narrator_voice
        self.dialogue_voice = dialogue_voice
        self._executor = _EXECUTOR

    def get_voice_engine(self, voice_id: str):
        try:
            return _load_voice_engine(self.device, voice_id)
        except RuntimeError as e:
            if self.device == "cpu":
                raise
            print(f"Cảnh báo: không tải được trên {self.device} ({e}). Đang chuyển về CPU...")
            self.device = "cpu"
            return _load_voice_engine("cpu", voice_id)
        
    def _synthesize(self, segment: dict) -> np.ndarray:
        """Tổng hợp 1 segment; ném lỗi nếu thất bại."""
        text = (segment.get('text') or '').strip()
        if not text:
            return np.array([], dtype=np.float32)
        engine = self.get_voice_engine(segment.get('voice') or self.narrator_voice)
        speed = float(segment.get('speed', 1.0))
        pieces = safe_pieces(text)
        if len(pieces) == 1:
            return engine.synthesize(text, speed=speed)[0]
        core = kokoro_vietnamese.core
        chunks = [engine.synthesize(p, speed=speed)[0] for p in pieces]
        return core.merge_audio_chunks(chunks, round(core.SAMPLE_RATE * core.DEFAULT_CROSSFADE_MS / 1000))

    def synthesize_segment(self, segment: dict) -> np.ndarray:
        """Dùng cho nghe thử: lỗi -> mảng rỗng."""
        try:
            return self._synthesize(segment)
        except Exception as e:
            print(f"TTS Error on segment: {segment.get('text', '')} - {e}")
            return np.array([])

    def synthesize_chapter(self, segments: list[dict], gap_seconds: float = 0.4, sample_rate: int = 24000,
                           failures: list | None = None) -> np.ndarray:
        """Ghép audio các segment. Mỗi segment có thể có 'pause_after' (giây) để ghi đè gap_seconds.

        Segment lỗi được thử lại 1 lần; vẫn lỗi thì bỏ qua và ghi (text, lỗi) vào `failures`
        để job báo cho người dùng (trước đây bị nuốt im lặng -> mất câu trong audio).
        """
        def one(seg):
            last = None
            for _ in range(2):
                try:
                    return self._synthesize(seg)
                except Exception as e:
                    last = e
            if failures is not None:
                failures.append((seg.get('text', ''), f"{type(last).__name__}: {last}"))
            return np.array([], dtype=np.float32)

        final_audio = []
        # Dùng executor cố định để tránh tràn RAM
        results = list(self._executor.map(one, segments))

        for seg, audio in zip(segments, results):
            if len(audio) > 0:
                pause = seg.get('pause_after')
                pause = gap_seconds if pause is None else float(pause)
                final_audio.append(audio)
                final_audio.append(np.zeros(int(sample_rate * pause), dtype=np.float32))

        if final_audio:
            return np.concatenate(final_audio)
        return np.array([])
