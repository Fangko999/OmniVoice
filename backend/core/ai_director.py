"""AI Đạo diễn âm thanh: văn bản chương -> segments {voice, text, speed, pause_after}.

- Chia chương thành khúc ~2.500 ký tự theo đoạn văn, kèm ngữ cảnh khúc trước.
- Gọi Gemini qua AccountPool (luân phiên nhiều tài khoản).
- Chuẩn hóa: voice ∈ {narrator, male, female} (mập mờ -> male), kẹp speed/pause.
- AI trả về MỖI DÒNG MỘT SEGMENT dạng `VAI|tốc độ|nghỉ|nội dung` (không dùng JSON vì
  dấu ngoặc kép trong lời thoại hay làm JSON vỡ). Vẫn đọc được JSON nếu AI lỡ trả JSON.
- Kiểm tra độ trung thành: AI không được bỏ/viết lại nội dung. Hỏng -> thử lại (tối đa 3 lần)
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
ROLE_CODES = {"n": "narrator", "m": "male", "f": "female",
              "narrator": "narrator", "male": "male", "female": "female"}
MAX_ATTEMPTS = 3
SPLIT_ATTEMPTS = 2   # số lần thử cho mỗi nửa khi đã chia đôi khúc
MAX_SPLIT_DEPTH = 2  # chia tối đa 2 cấp (khúc -> 1/2 -> 1/4)
SPEED_MIN, SPEED_MAX = 0.8, 1.3
PAUSE_MIN, PAUSE_MAX = 0.1, 2.0
DEFAULT_PAUSE = 0.4
FIDELITY_THRESHOLD = 0.95
CHUNK_CHARS = 2500
CONTEXT_PARAS = 2

SYSTEM_PROMPT = """Bạn là biên tập viên kịch bản truyện. Đây là tác vụ XỬ LÝ VĂN BẢN THUẦN TÚY:
chia ĐOẠN TRUYỆN CẦN PHÂN TÍCH thành các câu/segment và gắn nhãn người nói cho từng segment.
Bạn chỉ cần trả về văn bản theo định dạng dưới đây, không cần tạo âm thanh hay hình ảnh.
CHỈ TRẢ VỀ CÁC DÒNG SEGMENT, KHÔNG GIẢI THÍCH, KHÔNG MARKDOWN, KHÔNG JSON.

Định dạng: MỖI SEGMENT MỘT DÒNG, 4 trường cách nhau bởi dấu |
VAI|tốc độ|nghỉ|nội dung
Ví dụ:
N|1.0|0.4|Hắn ngẩng đầu nhìn bầu trời âm u.
M|1.2|0.2|Ngươi là ai?
F|0.9|0.8|Ta... chỉ là một kẻ qua đường.

VAI (chỉ 3 giá trị):
- N: lời dẫn truyện, miêu tả, hành động, suy nghĩ không nằm trong lời thoại.
- M: lời thoại nhân vật nam. NẾU KHÔNG RÕ NAM HAY NỮ -> M.
- F: lời thoại nhân vật nữ (dựa vào xưng hô, tên, đại từ "nàng/cô/bà/tỷ/muội...").
  Truyện tu tiên: tuổi tác không quan trọng, chỉ cần phân biệt giới tính.

- nội dung: GIỮ NGUYÊN 100% TỪ NGỮ GỐC, đúng thứ tự, không bỏ sót, không tóm tắt, không thêm từ.
  Chỉ được phép thêm/bớt dấu câu ("...", ",") để tạo nhịp ngắt. Bỏ dấu ngoặc kép bao lời thoại.
  Nội dung nằm trên đúng một dòng.
- tốc độ (0.8-1.3): gay cấn/tức giận/vội vã 1.15-1.3; buồn bã/trầm tư/thì thầm 0.85-0.95; bình thường 1.0.
- nghỉ (giây, 0.1-2.0): khoảng lặng sau segment. Bình thường 0.3-0.5; chuyển cảnh/kết đoạn
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


_LINE_RE = re.compile(
    r"^\s*[-*\d.)\s]*\[?(n|m|f|narrator|male|female)\]?\s*\|\s*([\d.,]*)\s*\|\s*([\d.,]*)\s*\|(.*)$",
    re.I)


def _num(v: str):
    return v.replace(",", ".") if v else None


def _make_seg(voice: str, text, speed, pause) -> Optional[dict]:
    text = re.sub(r"\s+", " ", str(text or "")).strip().strip('"“”').strip()
    if not text:
        return None
    voice = str(voice or "").strip().lower()
    return {
        "voice": ROLE_CODES.get(voice, "male"),
        "text": text,
        "speed": _clamp(speed, SPEED_MIN, SPEED_MAX, 1.0),
        "pause_after": _clamp(pause, PAUSE_MIN, PAUSE_MAX, DEFAULT_PAUSE),
    }


def parse_lines(raw: str) -> list[dict]:
    out = []
    for line in raw.replace("```", "\n").splitlines():
        m = _LINE_RE.match(line)
        if m:
            seg = _make_seg(m.group(1), m.group(4), _num(m.group(2)), _num(m.group(3)))
            if seg:
                out.append(seg)
    return out


def parse_and_normalize(raw: str) -> list[dict]:
    """Đọc phản hồi AI: ưu tiên định dạng dòng `VAI|speed|pause|text`, sau đó mới thử JSON."""
    raw = raw or ""
    out = parse_lines(raw)
    if out:
        return out
    if not raw.strip():
        raise ValueError("AI trả về rỗng")
    data = json.loads(_strip_fence(raw), strict=False)
    if isinstance(data, dict):
        data = data.get("segments", [])
    if not isinstance(data, list):
        raise ValueError("AI không trả về mảng JSON")
    for item in data:
        if isinstance(item, dict):
            seg = _make_seg(item.get("voice"), item.get("text"), item.get("speed"), item.get("pause_after"))
            if seg:
                out.append(seg)
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

    async def direct_chunk(self, chunk: list[str], context: list[str], should_stop=None,
                           attempts: int = MAX_ATTEMPTS, depth: int = 0) -> tuple[list[dict], bool]:
        """Trả về (segments, is_fallback).

        Hỏng sau `attempts` lần -> chia đôi khúc (theo đoạn văn) rồi thử lại từng nửa, tối đa
        MAX_SPLIT_DEPTH cấp. Khúc nhỏ ít bị AI làm rơi chữ / từ chối hơn, nên chỉ phần nhỏ nhất
        thật sự lỗi mới phải dùng fallback.
        """
        original = "\n".join(chunk)
        prompt = build_prompt(chunk, context)
        for attempt in range(attempts):
            raw = await self.pool.generate(prompt, model=self.model, should_stop=should_stop)
            try:
                segs = parse_and_normalize(raw)
            except Exception as e:
                head = re.sub(r"\s+", " ", (raw or "")[:200])
                self.log(f"  Phản hồi không đọc được (lần {attempt + 1}): {e} | Đầu phản hồi: {head!r}")
                continue
            score = fidelity(original, segs)
            if score >= FIDELITY_THRESHOLD:
                return segs, False
            self.log(f"  Độ trung thành thấp {score:.2f} (lần {attempt + 1}), thử lại...")
        if len(chunk) >= 2 and depth < MAX_SPLIT_DEPTH:
            mid = len(chunk) // 2
            self.log(f"  -> Chia đôi khúc ({len(chunk)} đoạn) và thử lại từng nửa...")
            left, fb1 = await self.direct_chunk(chunk[:mid], context, should_stop, SPLIT_ATTEMPTS, depth + 1)
            right, fb2 = await self.direct_chunk(chunk[mid:], chunk[:mid][-CONTEXT_PARAS:], should_stop,
                                                 SPLIT_ATTEMPTS, depth + 1)
            return left + right, fb1 or fb2
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
