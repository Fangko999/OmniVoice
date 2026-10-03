import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ai_director import (AIDirector, chunk_paragraphs, fidelity, parse_and_normalize)
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


def test_fidelity():
    orig = 'Hắn nói: "Đi thôi." Rồi quay lưng.'
    good = [{"text": "Hắn nói:"}, {"text": "Đi thôi..."}, {"text": "Rồi, quay lưng."}]
    bad = [{"text": "Hắn bảo đi."}]
    assert fidelity(orig, good) > 0.99
    assert fidelity(orig, bad) < 0.8


class FakePool:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def generate(self, prompt, model=None, should_stop=None):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def test_direct_chunk_retry_then_fallback():
    chunk = ['Hắn nói: "Đi thôi."']
    pool = FakePool(['[{"text":"Tóm tắt","voice":"narrator"}]', 'không phải json'])
    d = AIDirector(pool=pool, log=lambda m: None)
    segs, fb = asyncio.run(d.direct_chunk(chunk, []))
    assert fb is True and len(pool.prompts) == 2
    assert [s["voice"] for s in segs] == ["narrator", "male"]
    assert all(s["fallback"] for s in segs)


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
