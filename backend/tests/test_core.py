"""Test các hàm tiện ích lõi (không cần GPU / Gemini)."""
import json
import os

import numpy as np
import pytest

from core import job_base, script_store
from core.audio_encoder import AudioEncoder
from core.job_base import JobBase, safe_dirname
from models.schemas import ChapterScript, RenderState, ScriptSegment


def test_safe_dirname_windows_invalid_chars():
    assert safe_dirname('Cổ Chân Nhân: Quyển 1?') == "Cổ Chân Nhân Quyển 1"
    assert safe_dirname('a/b\\c|d*e"f<g>h') == "a b c d e f g h"
    assert safe_dirname("Tên truyện... ") == "Tên truyện"
    assert safe_dirname("") == "Truyen"
    assert safe_dirname(None) == "Truyen"


class _DummyJob(JobBase):
    kind = "dummy"

    def _state_cls(self):
        return RenderState

    def _new_state(self):
        return RenderState(job_id=self.job_id, book_name="x", status="idle", total_chapters=3,
                           completed_chapters=[], current_chapter=None, config=None,
                           current_log="", error_msg=None)


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_base, "STATE_DIR", str(tmp_path))
    return tmp_path


def test_stale_running_state_becomes_paused(state_dir):
    job = _DummyJob("j1")
    job.state.status = "running"
    job.state.completed_chapters = [1]
    job.save_state()
    again = _DummyJob("j1")  # giống server khởi động lại
    assert again.state.status == "paused"
    assert again.state.completed_chapters == [1]
    assert again.state.error_msg


def test_corrupt_or_bom_state(state_dir):
    p = os.path.join(state_dir, "j2.dummy.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{hỏng")
    assert _DummyJob("j2").state.status == "idle"  # file hỏng -> tạo mới, không crash

    data = _DummyJob("j3").state.model_dump()
    data["completed_chapters"] = [2]
    with open(os.path.join(state_dir, "j3.dummy.json"), "w", encoding="utf-8-sig") as f:
        json.dump(data, f)  # có BOM (sửa bằng Notepad)
    assert _DummyJob("j3").state.completed_chapters == [2]


def test_is_edited(tmp_path):
    d = str(tmp_path)
    script_store.create_or_open_project(d, "Truyện", 2)
    script_store.save_chapter(d, ChapterScript(chapter=1, segments=[ScriptSegment(text="a")]))
    assert not script_store.is_edited(d, 1)
    script_store.save_chapter(d, ChapterScript(chapter=1, segments=[ScriptSegment(text="b")]), user_edit=True)
    assert script_store.is_edited(d, 1)
    assert not script_store.is_edited(d, 2)  # chưa có file


def test_audio_encoder_atomic(tmp_path):
    audio = np.zeros(2400, dtype=np.float32)
    out = str(tmp_path / "chuong_0001.wav")
    AudioEncoder.save_wav(audio, out)
    assert os.listdir(tmp_path) == ["chuong_0001.wav"]  # không còn file .part
