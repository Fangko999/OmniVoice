"""AI Đạo diễn âm thanh: văn bản chương -> segments {voice, text, speed, pause_after}.

- Chia chương thành khúc ~2.500 ký tự theo đoạn văn, kèm ngữ cảnh khúc trước.
- Gọi Gemini qua AccountPool (luân phiên nhiều tài khoản).
- Chuẩn hóa: voice ∈ {narrator, male, female} (mập mờ -> male), kẹp speed/pause.
- Kiểm tra độ trung thành: AI không được bỏ/viết lại nội dung. Hỏng -> thử lại 1 lần
  -> vẫn hỏng thì dùng tách vai theo ngoặc kép (split_roles) cho khúc đó, đánh dấu fallback.
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Callable, Optional

from core.account_pool import AccountPool, get_pool
from core.text_processor import TextProcessor

ROLES = ("narrator", "male", "female")
SPEED_MIN, SPEED_MAX = 0.8, 1.3
PAUSE_MIN, PAUSE_MAX = 0.1, 2.0
DEFAULT_PAUSE = 0.4
FIDELITY_THRESHOLD = 0.95
CHUNK_CHARS = 2500
CONTEXT_PARAS = 2

SYSTEM_PROMPT = """Bạn là Đạo diễn Âm thanh cho hệ thống đọc truyện Text-to-Speech.
Nhiệm vụ: chia ĐOẠN TRUYỆN CẦN PHÂN TÍCH thành các segment để đọc diễn cảm.
CHỈ TRẢ VỀ DUY NHẤT MỘT MẢNG JSON, KHÔNG GIẢI THÍCH, KHÔNG MARKDOWN.

Quy tắc giọng (chỉ 3 giá trị):
- "narrator": lời dẫn truyện, miêu tả, hành động, suy nghĩ không nằm trong lời thoại.
- "male": lời thoại nhân vật nam. NẾU KHÔNG RÕ NAM HAY NỮ -> "male".
- "female": lời thoại nhân vật nữ (dựa vào xưng hô, tên, đại từ "nàng/cô/bà/tỷ/muội...").
  Truyện tu tiên: tuổi tác không quan trọng, chỉ cần phân biệt giới tính.

Mỗi phần tử: {"text": "...", "voice": "narrator|male|female", "speed": 1.0, "pause_after": 0.4}
- text: GIỮ NGUYÊN 100% TỪ NGỮ GỐC, đúng thứ tự, không bỏ sót, không tóm tắt, không thêm từ.
  Chỉ được phép thêm/bớt dấu câu ("...", ",") để tạo nhịp ngắt. Bỏ dấu ngoặc kép bao lời thoại.
- speed (0.8-1.3): gay cấn/tức giận/vội vã 1.15-1.3; buồn bã/trầm tư/thì thầm 0.85-0.95; bình thường 1.0.
- pause_after (giây, 0.1-2.0): khoảng lặng sau segment. Bình thường 0.3-0.5; chuyển cảnh/kết đoạn
  căng thẳng 0.8-1.5; lời thoại dồn dập 0.15-0.25.
"""


# ---------------------------------------------------------------- helpers
def chunk_paragraphs(paragraphs: list[str], max_chars: int = CHUNK_CHARS) -> list[list[str]]:
    chunks, cur, size = [], [], 0
    for p in paragraphs:
        if cur and size + len(p) > max_chars:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += len(p) + 1
    if cur:
        chunks.append(cur)
    return chunks


def _strip_fence(s: str) -> str:
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    # Cắt đúng phần mảng JSON nếu có rác ở đầu/cuối
    start, end = s.find("["), s.rfind("]")
    if start != -1 and end > start:
        s = s[start:end + 1]
    return s


def _clamp(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return round(max(lo, min(hi, v)), 2)


def parse_and_normalize(raw: str) -> list[dict]:
    data = json.loads(_strip_fence(raw), strict=False)
    if isinstance(data, dict):
        data = data.get("segments", [])
    if not isinstance(data, list):
        raise ValueError("AI không trả về mảng JSON")
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = re.sub(r"\s+", " ", str(item.get("text", ""))).strip().strip('"“”').strip()
        if not text:
            continue
        voice = str(item.get("voice", "")).strip().lower()
        if voice not in ROLES:
            voice = "male"
        out.append({
            "voice": voice,
            "text": text,
            "speed": _clamp(item.get("speed"), SPEED_MIN, SPEED_MAX, 1.0),
            "pause_after": _clamp(item.get("pause_after"), PAUSE_MIN, PAUSE_MAX, DEFAULT_PAUSE),
        })
    if not out:
        raise ValueError("AI trả về mảng rỗng")
    return out


def _norm_for_compare(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    return re.sub(r"[\W_]+", "", s)


def fidelity(original: str, segments: list[dict]) -> float:
    a = _norm_for_compare(original)
    b = _norm_for_compare("".join(seg["text"] for seg in segments))
    if not a:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def fallback_segments(paragraphs: list[str]) -> list[dict]:
    out = []
    for p in paragraphs:
        for s in TextProcessor.split_roles(p, "narrator", "male"):
            out.append({"voice": s["voice"], "text": s["text"], "speed": 1.0,
                        "pause_after": DEFAULT_PAUSE, "fallback": True})
    return out


def build_prompt(chunk: list[str], context: list[str]) -> str:
    parts = [SYSTEM_PROMPT]
    if context:
        parts.append("NGỮ CẢNH TRƯỚC ĐÓ (chỉ để hiểu ai đang nói, KHÔNG đưa vào kết quả):\n" + "\n".join(context))
    parts.append("ĐOẠN TRUYỆN CẦN PHÂN TÍCH:\n" + "\n".join(chunk))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- main
class AIDirector:
    def __init__(self, pool: Optional[AccountPool] = None, model: str = "gemini-flash",
                 log: Callable[[str], None] = print):
        self.pool = pool or get_pool()
        self.model = model
        self.log = log

    async def direct_chunk(self, chunk: list[str], context: list[str], should_stop=None) -> tuple[list[dict], bool]:
        """Trả về (segments, is_fallback)."""
        original = "\n".join(chunk)
        prompt = build_prompt(chunk, context)
        for attempt in range(2):
            raw = await self.pool.generate(prompt, model=self.model, should_stop=should_stop)
            try:
                segs = parse_and_normalize(raw)
            except Exception as e:
                self.log(f"  JSON không hợp lệ (lần {attempt + 1}): {e}")
                continue
            score = fidelity(original, segs)
            if score >= FIDELITY_THRESHOLD:
                return segs, False
            self.log(f"  Độ trung thành thấp {score:.2f} (lần {attempt + 1}), thử lại...")
        self.log("  -> Dùng tách vai theo ngoặc kép cho khúc này (fallback).")
        return fallback_segments(chunk), True

    async def direct_chapter(self, paragraphs: list[str], should_stop=None,
                             on_progress: Callable[[int, int], object] = None) -> tuple[list[dict], int]:
        """Trả về (segments, số khúc bị fallback)."""
        paragraphs = [c for c in (TextProcessor.clean(p) for p in paragraphs) if c]
        if not paragraphs:
            return [], 0
        chunks = chunk_paragraphs(paragraphs)
        segments, fallbacks, context = [], 0, []
        for i, chunk in enumerate(chunks, 1):
            if on_progress:
                r = on_progress(i, len(chunks))
                if hasattr(r, "__await__"):
                    await r
            segs, fb = await self.direct_chunk(chunk, context, should_stop)
            segments.extend(segs)
            fallbacks += int(fb)
            context = chunk[-CONTEXT_PARAS:]
        return segments, fallbacks
