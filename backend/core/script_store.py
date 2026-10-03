"""Đọc/ghi thư mục kịch bản trên ổ đĩa (độc lập với EPUB và server).

<script_dir>/
    manifest.json
    chuong_0001.json
    ...
"""
import json
import os
import threading
from datetime import datetime
from typing import Optional

from models.schemas import ChapterScript, ManifestChapter, ScriptManifest

MANIFEST = "manifest.json"
_lock = threading.Lock()


def _atomic_write(path: str, text: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def chapter_path(script_dir: str, n: int) -> str:
    return os.path.join(script_dir, f"chuong_{n:04d}.json")


def is_valid_script_dir(script_dir: str) -> bool:
    p = os.path.join(script_dir, MANIFEST)
    if not os.path.isfile(p):
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("format") == "omnivoice-script"
    except Exception:
        return False


def load_manifest(script_dir: str) -> ScriptManifest:
    with open(os.path.join(script_dir, MANIFEST), "r", encoding="utf-8") as f:
        return ScriptManifest(**json.load(f))


def save_manifest(script_dir: str, manifest: ScriptManifest):
    _atomic_write(os.path.join(script_dir, MANIFEST), manifest.model_dump_json(indent=2))


def create_or_open_project(script_dir: str, book_name: str, total_chapters: int,
                           source_epub: str = "", titles: Optional[list[str]] = None) -> ScriptManifest:
    with _lock:
        if is_valid_script_dir(script_dir):
            m = load_manifest(script_dir)
            m.total_chapters = max(m.total_chapters, total_chapters)
        else:
            m = ScriptManifest(book_name=book_name, total_chapters=total_chapters, source_epub=source_epub)
        for i, t in enumerate(titles or [], 1):
            ch = m.chapters.setdefault(str(i), ManifestChapter())
            if not ch.title:
                ch.title = t
        save_manifest(script_dir, m)
        return m


def load_chapter(script_dir: str, n: int) -> Optional[ChapterScript]:
    p = chapter_path(script_dir, n)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return ChapterScript(**json.load(f))


def save_chapter(script_dir: str, script: ChapterScript, *, user_edit: bool = False,
                 fallback_chunks: Optional[int] = None):
    """Lưu chương + cập nhật manifest. user_edit=True -> đánh dấu đã sửa tay."""
    if user_edit:
        script.edited = True
    if not script.created_at:
        script.created_at = datetime.now().isoformat(timespec="seconds")
    _atomic_write(chapter_path(script_dir, script.chapter), script.model_dump_json(indent=2))
    with _lock:
        m = load_manifest(script_dir)
        ch = m.chapters.setdefault(str(script.chapter), ManifestChapter())
        ch.status = "done"
        if script.title:
            ch.title = script.title
        ch.edited = script.edited
        if fallback_chunks is not None:
            ch.fallback_chunks = fallback_chunks
        elif not any(s.fallback for s in script.segments):
            ch.fallback_chunks = 0
        if script.chapter > m.total_chapters:
            m.total_chapters = script.chapter
        save_manifest(script_dir, m)


def done_chapters(script_dir: str) -> list[int]:
    """Các chương có file kịch bản thật sự trên đĩa."""
    out = []
    if not os.path.isdir(script_dir):
        return out
    for name in os.listdir(script_dir):
        if name.startswith("chuong_") and name.endswith(".json"):
            try:
                out.append(int(name[7:-5]))
            except ValueError:
                pass
    return sorted(out)
