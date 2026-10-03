import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ai_director import (AIDirector, chunk_paragraphs, diff_chars, drop_repeats, fidelity,
                               parse_and_normalize)
from core import script_store
from models.schemas import ChapterScript, ScriptSegment


def test_chunking():
    paras = ["a" * 1000, "b" * 1000, "c" * 1000, "d" * 3000]
    chunks = chunk_paragraphs(paras, 2500)
    assert [len(c) for c in chunks] == [2, 1, 1]
    assert sum(chunks, []) == paras


def test_normalize_fence_and_clamp():
    raw = '```json\n[{"text":"“Ngươi là ai?”","voice":"Boy","speed":5,"pause_after":-1},' \
          '{"text":"Nàng cười.","voice":"female"},{"text":"  ","voice":"male"}]\n```'
    segs = parse_and_normalize(raw)
    assert len(segs) == 2
    assert segs[0] == {"voice": "male", "text": "Ngươi là ai?", "speed": 1.3, "pause_after": 0.1}
    assert segs[1]["voice"] == "female" and segs[1]["speed"] == 1.0 and segs[1]["pause_after"] == 0.4


def test_normalize_raw_newline_in_string():
    raw = '[{"text":"Dòng một\nDòng hai","voice":"narrator"}]'
    segs = parse_and_normalize(raw)
    assert segs[0]["text"] == "Dòng một Dòng hai"


def test_parse_line_format():
    raw = ('Đây là kết quả:\n```\nN|1.0|0.4|Hắn nói: "đi" rồi quay lưng.\n'
           'M|1,2|0,2|“Ngươi là ai?”\n'
           '- F | 0.9 | 0.8 | Ta... chỉ là khách | qua đường.\n'
           'narrator|||Kết.\ndòng rác\n```')
    segs = parse_and_normalize(raw)
    assert [s["voice"] for s in segs] == ["narrator", "male", "female", "narrator"]
    assert segs[0]["text"] == 'Hắn nói: "đi" rồi quay lưng.'
    assert segs[1] == {"voice": "male", "text": "Ngươi là ai?", "speed": 1.2, "pause_after": 0.2}
    assert segs[2]["text"] == "Ta... chỉ là khách | qua đường."
    assert segs[3]["speed"] == 1.0 and segs[3]["pause_after"] == 0.4


def test_parse_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_and_normalize("")


def test_fidelity():
    orig = 'Hắn nói: "Đi thôi." Rồi quay lưng.'
    good = [{"text": "Hắn nói:"}, {"text": "Đi thôi..."}, {"text": "Rồi, quay lưng."}]
    bad = [{"text": "Hắn bảo đi."}]
    assert fidelity(orig, good) > 0.99
    assert fidelity(orig, bad) < 0.8


# Phản hồi thật của Gemini (chương 2): dòng 5 bị cắt dở, dính mã dòng mới rồi phát lại từ dòng 1.
REWIND_ORIG = ("Tư chất sao. Nhìn ra ngoài cửa sổ, hắn cười khẩy. "
               "Đúng lúc này, một thiếu niên đi vào. \"Ca ca, sao huynh đứng đó?\" "
               "Thiếu niên này có dáng người thấp bé.")
REWIND_RAW = ("M|0.9|0.4|Tư chất sao.\n"
              "N|1.0|0.4|Nhìn ra ngoài cửa sổ, hắn cười khẩy.\n"
              "N|1.0|0.4|Đúng lúc này, một thiếu niên đi vào.\n"
              "M|1.1|0.3|Ca ca, sao huynh đứng đó?\n"
              "N|1.0|0.4|Thiếu niên này có dáng ngườiM|0.9|0.4|Tư chất sao.\n"
              "N|1.0|0.4|Nhìn ra ngoài cửa sổ, hắn cười khẩy.\n"
              "N|1.0|0.4|Đúng lúc này, một thiếu niên đi vào.\n"
              "M|1.1|0.3|Ca ca, sao huynh đứng đó?\n"
              "N|1.0|0.4|Thiếu niên này có dáng người thấp bé.")


def test_glued_line_is_split_and_cut_fragment_dropped():
    segs = parse_and_normalize(REWIND_RAW)
    texts = [s["text"] for s in segs]
    assert "Thiếu niên này có dáng người" not in texts          # mảnh cắt dở, bản đầy đủ có ở sau
    assert segs[4]["voice"] == "male" and segs[4]["text"] == "Tư chất sao." and segs[4]["speed"] == 0.9
    assert not any("|" in t for t in texts)
    # Mảnh cắt dở KHÔNG có bản đầy đủ phía sau thì giữ lại
    segs = parse_and_normalize("N|1.0|0.4|Một mảnh riêngM|1.1|0.3|Câu khác.")
    assert [s["text"] for s in segs] == ["Một mảnh riêng", "Câu khác."]


def test_drop_repeats_removes_rewind():
    segs = drop_repeats(REWIND_ORIG, parse_and_normalize(REWIND_RAW))
    assert [s["text"] for s in segs] == [
        "Tư chất sao.", "Nhìn ra ngoài cửa sổ, hắn cười khẩy.", "Đúng lúc này, một thiếu niên đi vào.",
        "Ca ca, sao huynh đứng đó?", "Thiếu niên này có dáng người thấp bé."]
    assert diff_chars(REWIND_ORIG, segs) == (0, 0)


def test_drop_repeats_keeps_legit_repeats_and_drops_context():
    orig = "Không dám. Không dám. Nhất định nhớ kĩ."
    segs = [{"text": "Mưa rơi."}, {"text": "Không dám."}, {"text": "Không dám."},
            {"text": "Nhất định nhớ kĩ."}, {"text": "Câu AI sửa chữ."}]
    out = drop_repeats(orig, segs, context="Trời tối. Mưa rơi.")
    assert [s["text"] for s in out] == ["Không dám.", "Không dám.", "Nhất định nhớ kĩ.", "Câu AI sửa chữ."]
    # Câu ngắn bị lặp liền nhau (chương 6): "ôi" nằm trong "tôi", "thôi" nên phép đếm không bắt được
    orig = "Tôi không thích, thôi đi. Ôi... Gia lão thở dài."
    segs = [{"text": "Tôi không thích, thôi đi."}, {"text": "Ôi..."}, {"text": "Ôi..."}, {"text": "Gia lão thở dài."}]
    assert [s["text"] for s in drop_repeats(orig, segs)] == ["Tôi không thích, thôi đi.", "Ôi...", "Gia lão thở dài."]


def test_diff_chars_catches_duplicate_that_ratio_misses():
    para = "Đây là một câu văn khá dài để làm nền cho bài kiểm tra. " * 40
    dup = "Phương Nguyên, ngoan ngoãn giao Xuân Thu Thiền ra đây!"
    segs = [{"text": dup}, {"text": dup}, {"text": para}]
    assert fidelity(dup + para, segs) > 0.95          # tỉ lệ khớp không phát hiện được
    extra, missing = diff_chars(dup + para, segs)
    assert extra > 20 and missing == 0


class FakePool:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def generate(self, prompt, model=None, should_stop=None):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def test_direct_chunk_retry_then_fallback():
    chunk = ['Hắn nói: "Đi thôi."']
    pool = FakePool(['[{"text":"Tóm tắt","voice":"narrator"}]', 'không phải json', ''])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk(chunk, []))
    assert fb is True and len(pool.prompts) == 3
    assert [s["voice"] for s in segs] == ["narrator", "male"]
    assert all(s["fallback"] for s in segs)


def test_direct_chunk_recovers_on_third_try():
    chunk = ['Hắn nói: "Đi thôi."']
    pool = FakePool(['', '[{"text": "Hắn nói: "Đi thôi.""}]', 'N|1.0|0.3|Hắn nói:\nM|1.1|0.4|Đi thôi.'])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk(chunk, []))
    assert fb is False and [s["voice"] for s in segs] == ["narrator", "male"]


def test_direct_chunk_salvages_rewind_without_retry():
    pool = FakePool([REWIND_RAW])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk([REWIND_ORIG], []))
    assert fb is False and len(pool.prompts) == 1 and len(segs) == 5


def test_direct_chunk_retries_when_ai_adds_text():
    chunk = ["Hắn đứng dậy. " * 30]
    added = "N|1.0|0.4|" + chunk[0] + " Một câu hoàn toàn do AI tự bịa ra thêm vào."
    pool = FakePool([added, "N|1.0|0.4|" + chunk[0]])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk(chunk, []))
    assert fb is False and len(pool.prompts) == 2


def test_direct_chunk_splits_and_isolates_failure():
    chunk = ["Đoạn một yên bình.", "Đoạn hai máu me."]
    pool = FakePool(["Tôi không được lập trình để làm điều đó."] * 3   # cả khúc: hỏng 3 lần
                    + ["N|1.0|0.4|Đoạn một yên bình."]                # nửa đầu: OK
                    + ["Tôi không thể giúp."] * 2)                     # nửa sau: hỏng 2 lần
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk(chunk, []))
    assert fb is True and len(pool.prompts) == 6
    assert segs[0]["text"] == "Đoạn một yên bình." and "fallback" not in segs[0]
    assert segs[1]["text"] == "Đoạn hai máu me." and segs[1]["fallback"] is True


def test_direct_chapter_passes_context():
    paras = ["x" * 2000, "y" * 2000]
    reply1 = json.dumps([{"text": "x" * 2000, "voice": "narrator"}])
    reply2 = json.dumps([{"text": "y" * 2000, "voice": "narrator"}])
    pool = FakePool([reply1, reply2])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chapter(paras))
    assert fb == 0 and len(segs) == 2
    assert "NGỮ CẢNH" not in pool.prompts[0] and "NGỮ CẢNH" in pool.prompts[1]


def test_script_store_roundtrip(tmp_path):
    d = str(tmp_path / "kb")
    script_store.create_or_open_project(d, "Truyện A", 3, titles=["C1", "C2", "C3"])
    assert script_store.is_valid_script_dir(d)
    s = ChapterScript(chapter=2, title="C2", segments=[ScriptSegment(text="abc", voice="female", pause_after=0.8)])
    script_store.save_chapter(d, s, fallback_chunks=1)
    m = script_store.load_manifest(d)
    assert m.chapters["2"].status == "done" and m.chapters["2"].fallback_chunks == 1
    assert script_store.done_chapters(d) == [2]
    loaded = script_store.load_chapter(d, 2)
    loaded.segments[0].text = "sửa tay"
    script_store.save_chapter(d, loaded, user_edit=True)
    m = script_store.load_manifest(d)
    assert m.chapters["2"].edited is True
    assert script_store.load_chapter(d, 2).segments[0].text == "sửa tay"
    # Mở lại không làm mất dữ liệu
    script_store.create_or_open_project(d, "Truyện A", 3)
    assert script_store.load_manifest(d).chapters["2"].edited is True
