import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  Save, X, Play, Square, Loader2, Scissors, Merge, Plus, Trash2, AlertTriangle, PenLine, ChevronLeft, ChevronRight
} from 'lucide-react';
import { API_BASE, ROLES, errMsg } from '../constants';

let _key = 0;
const withKeys = (segs) => segs.map(s => ({ ...s, _k: ++_key }));
const stripKeys = (segs) => segs.map(({ _k, ...s }) => s); // eslint-disable-line no-unused-vars

const DEFAULT_MAP = { narrator: 'my_yen', male: 'tuan_ngoc', female: 'ngoc_huyen' };

function AutoTextarea({ value, onChange, onCursor, id }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = el.scrollHeight + 'px';
    }
  }, [value]);
  const report = (e) => onCursor(e.target.selectionStart);
  return (
    <textarea
      id={id}
      ref={ref}
      rows={1}
      className="seg-text"
      value={value}
      onChange={e => { onChange(e.target.value); report(e); }}
      onSelect={report}
      onClick={report}
      onKeyUp={report}
    />
  );
}

/**
 * Trình sửa kịch bản đầy đủ: sửa text / giọng / tốc độ / khoảng nghỉ,
 * tách - gộp - chèn - xóa segment, đổi vai hàng loạt, nghe thử từng segment.
 */
export default function ScriptEditor({ scriptDir, voiceMap = DEFAULT_MAP, onClose }) {
  const [manifest, setManifest] = useState(null);
  const [available, setAvailable] = useState([]);
  const [filter, setFilter] = useState('all');
  const [current, setCurrent] = useState(null);
  const [script, setScript] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [playing, setPlaying] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(null);
  const [error, setError] = useState('');
  const cursorRef = useRef({ idx: -1, pos: 0 });
  const audioRef = useRef(null);

  const openProject = useCallback(async () => {
    try {
      const r = await axios.post(`${API_BASE}/scripts/open`, { script_dir: scriptDir });
      setManifest(r.data.manifest);
      setAvailable(r.data.available_chapters);
      return r.data;
    } catch (e) {
      setError(errMsg(e));
      return null;
    }
  }, [scriptDir]);

  useEffect(() => {
    openProject().then(d => {
      if (d?.available_chapters?.length) loadChapter(d.available_chapters[0], true);
    });
  }, [openProject]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cảnh báo khi đóng tab trình duyệt mà chưa lưu
  useEffect(() => {
    const h = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);

  const confirmDiscard = () => !dirty || window.confirm('Chương hiện tại có thay đổi chưa lưu. Bỏ thay đổi?');

  const loadChapter = async (n, force = false) => {
    if (!force && !confirmDiscard()) return;
    stopAudio();
    try {
      const r = await axios.get(`${API_BASE}/scripts/chapter`, { params: { dir: scriptDir, n } });
      setScript({ ...r.data, segments: withKeys(r.data.segments) });
      setCurrent(n);
      setDirty(false);
      setSelected(new Set());
      setError('');
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const save = useCallback(async () => {
    if (!script || saving) return;
    setSaving(true);
    try {
      const payload = { ...script, segments: stripKeys(script.segments) };
      const r = await axios.put(`${API_BASE}/scripts/chapter`, payload, { params: { dir: scriptDir } });
      setScript({ ...r.data, segments: withKeys(r.data.segments) });
      setDirty(false);
      openProject();
    } catch (e) {
      alert('Lưu thất bại: ' + errMsg(e));
    } finally {
      setSaving(false);
    }
  }, [script, saving, scriptDir, openProject]);

  // Ctrl+S
  useEffect(() => {
    const h = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        save();
      }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [save]);

  // -------------------------------------------------------- segment ops
  const mutate = (fn) => {
    setScript(prev => ({ ...prev, segments: fn([...prev.segments]) }));
    setDirty(true);
  };
  const update = (i, patch) => mutate(segs => { segs[i] = { ...segs[i], ...patch }; return segs; });
  const remove = (i) => mutate(segs => { segs.splice(i, 1); return segs; });
  const insertAfter = (i) => mutate(segs => {
    const base = segs[i] || { voice: 'narrator', speed: 1.0, pause_after: 0.4 };
    segs.splice(i + 1, 0, { voice: base.voice, text: '', speed: 1.0, pause_after: 0.4, fallback: false, _k: ++_key });
    return segs;
  });
  const split = (i) => {
    const seg = script.segments[i];
    const pos = cursorRef.current.idx === i ? cursorRef.current.pos : Math.floor(seg.text.length / 2);
    const a = seg.text.slice(0, pos).trim();
    const b = seg.text.slice(pos).trim();
    if (!a || !b) {
      alert('Đặt con trỏ vào giữa đoạn văn để tách.');
      return;
    }
    mutate(segs => {
      segs.splice(i, 1, { ...seg, text: a, _k: ++_key }, { ...seg, text: b, _k: ++_key });
      return segs;
    });
  };
  const mergeNext = (i) => mutate(segs => {
    if (i >= segs.length - 1) return segs;
    const a = segs[i], b = segs[i + 1];
    segs.splice(i, 2, { ...a, text: `${a.text} ${b.text}`.trim(), pause_after: b.pause_after, fallback: a.fallback || b.fallback });
    return segs;
  });
  const setRoleForSelected = (voice) => {
    if (!selected.size) return;
    mutate(segs => segs.map(s => (selected.has(s._k) ? { ...s, voice } : s)));
  };
  const toggleSel = (k) => setSelected(prev => {
    const n = new Set(prev);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });

  // -------------------------------------------------------- preview
  const stopAudio = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlaying(null);
  };
  const preview = async (seg) => {
    stopAudio();
    if (!seg.text.trim()) return;
    setLoadingPreview(seg._k);
    try {
      const r = await axios.post(`${API_BASE}/preview/preview`, {
        voice_id: voiceMap[seg.voice] || voiceMap.narrator,
        text: seg.text,
        speed: seg.speed || 1.0
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(r.data);
      const a = new Audio(url);
      a.onended = () => { setPlaying(null); URL.revokeObjectURL(url); };
      a.play();
      audioRef.current = a;
      setPlaying(seg._k);
    } catch (e) {
      alert('Không tạo được âm thanh: ' + errMsg(e));
    } finally {
      setLoadingPreview(null);
    }
  };

  // -------------------------------------------------------- derived
  const chapterList = useMemo(() => {
    if (!manifest) return [];
    return available
      .map(n => ({ n, ...(manifest.chapters[String(n)] || {}) }))
      .filter(c => filter === 'all' || (filter === 'fallback' && c.fallback_chunks > 0) || (filter === 'edited' && c.edited));
  }, [manifest, available, filter]);

  const counts = useMemo(() => {
    const c = { narrator: 0, male: 0, female: 0 };
    script?.segments.forEach(s => { c[s.voice] = (c[s.voice] || 0) + 1; });
    return c;
  }, [script]);

  const idxInAvail = available.indexOf(current);
  const roleOf = (id) => ROLES.find(r => r.id === id);

  if (error && !manifest) {
    return (
      <div className="editor-shell">
        <div className="alert-box alert-error"><AlertTriangle /> <div><h4>Không mở được kịch bản</h4><p>{error}</p></div></div>
        <button className="btn" onClick={onClose}><X size={16} /> Đóng</button>
      </div>
    );
  }

  return (
    <div className="editor-shell">
      <div className="editor-topbar">
        <div className="editor-title">
          <PenLine size={20} />
          <div>
            <h2>Trình sửa kịch bản</h2>
            <p>{manifest?.book_name} · <span className="mono">{scriptDir}</span></p>
          </div>
        </div>
        <div className="editor-actions">
          {dirty && <span className="dirty-dot">● Chưa lưu</span>}
          <button id="editor-save-btn" className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving ? <Loader2 size={16} className="animate-spin-slow" /> : <Save size={16} />} Lưu (Ctrl+S)
          </button>
          <button id="editor-close-btn" className="btn" onClick={() => { if (confirmDiscard()) { stopAudio(); onClose(); } }}>
            <X size={16} /> Đóng
          </button>
        </div>
      </div>

      <div className="editor-body">
        {/* Danh sách chương */}
        <aside className="editor-sidebar">
          <div className="filter-tabs">
            {[['all', 'Tất cả'], ['fallback', 'Cần kiểm tra'], ['edited', 'Đã sửa']].map(([k, l]) => (
              <button key={k} className={filter === k ? 'active' : ''} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <div className="chapter-list">
            {chapterList.length === 0 && <p className="muted small" style={{ padding: 12 }}>Không có chương nào.</p>}
            {chapterList.map(c => (
              <button
                key={c.n}
                className={`chapter-item ${current === c.n ? 'active' : ''}`}
                onClick={() => current !== c.n && loadChapter(c.n)}
              >
                <span className="ch-num">{c.n}</span>
                <span className="ch-title">{c.title || `Chương ${c.n}`}</span>
                {c.fallback_chunks > 0 && <AlertTriangle size={13} className="ch-warn" title="Có đoạn AI không xử lý được" />}
                {c.edited && <PenLine size={13} className="ch-edited" />}
              </button>
            ))}
          </div>
        </aside>

        {/* Nội dung chương */}
        <section className="editor-main">
          {!script ? (
            <div className="flex-center muted" style={{ height: 300 }}>Chọn một chương để sửa</div>
          ) : (
            <>
              <div className="chapter-head">
                <button className="btn btn-sm" disabled={idxInAvail <= 0} onClick={() => loadChapter(available[idxInAvail - 1])}><ChevronLeft size={16} /></button>
                <h3>{script.title || `Chương ${script.chapter}`}</h3>
                <button className="btn btn-sm" disabled={idxInAvail < 0 || idxInAvail >= available.length - 1} onClick={() => loadChapter(available[idxInAvail + 1])}><ChevronRight size={16} /></button>
                <div className="role-counts">
                  {ROLES.map(r => <span key={r.id} style={{ '--role-color': r.color }}>{r.label}: {counts[r.id]}</span>)}
                </div>
              </div>

              <div className={`bulk-bar ${selected.size ? 'show' : ''}`}>
                <span>Đã chọn {selected.size} đoạn → đổi vai:</span>
                {ROLES.map(r => (
                  <button key={r.id} className="role-pill" style={{ '--role-color': r.color }} onClick={() => setRoleForSelected(r.id)}>{r.label}</button>
                ))}
                <button className="btn btn-sm" onClick={() => setSelected(new Set())}>Bỏ chọn</button>
              </div>

              <div className="segments">
                {script.segments.map((s, i) => {
                  const role = roleOf(s.voice);
                  return (
                    <div key={s._k} className={`seg-row ${s.fallback ? 'is-fallback' : ''} ${selected.has(s._k) ? 'is-selected' : ''}`} style={{ '--role-color': role?.color }}>
                      <div className="seg-gutter">
                        <input type="checkbox" checked={selected.has(s._k)} onChange={() => toggleSel(s._k)} />
                        <span className="seg-idx">{i + 1}</span>
                      </div>
                      <div className="seg-content">
                        <div className="seg-controls">
                          <select className="seg-role" value={s.voice} onChange={e => update(i, { voice: e.target.value })}>
                            {ROLES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                          </select>
                          <label className="seg-num" title="Tốc độ đọc">
                            Tốc độ
                            <input type="number" step="0.05" min="0.5" max="2" value={s.speed}
                              onChange={e => update(i, { speed: parseFloat(e.target.value) || 1 })} />
                          </label>
                          <label className="seg-num" title="Khoảng lặng sau đoạn (giây)">
                            Nghỉ
                            <input type="number" step="0.1" min="0" max="5" value={s.pause_after ?? ''} placeholder="mặc định"
                              onChange={e => update(i, { pause_after: e.target.value === '' ? null : parseFloat(e.target.value) })} />
                          </label>
                          {s.fallback && <span className="fallback-tag" title="AI không xử lý được đoạn này, đã dùng tách theo ngoặc kép"><AlertTriangle size={12} /> fallback</span>}
                          <div className="seg-tools">
                            <button title="Nghe thử" onClick={() => (playing === s._k ? stopAudio() : preview(s))} disabled={loadingPreview !== null && loadingPreview !== s._k}>
                              {loadingPreview === s._k ? <Loader2 size={14} className="animate-spin-slow" /> : playing === s._k ? <Square size={14} /> : <Play size={14} />}
                            </button>
                            <button title="Tách tại vị trí con trỏ" onClick={() => split(i)}><Scissors size={14} /></button>
                            <button title="Gộp với đoạn sau" onClick={() => mergeNext(i)} disabled={i === script.segments.length - 1}><Merge size={14} /></button>
                            <button title="Chèn đoạn mới phía sau" onClick={() => insertAfter(i)}><Plus size={14} /></button>
                            <button title="Xóa đoạn" className="danger" onClick={() => remove(i)}><Trash2 size={14} /></button>
                          </div>
                        </div>
                        <AutoTextarea
                          id={`seg-${s._k}`}
                          value={s.text}
                          onChange={text => update(i, { text })}
                          onCursor={pos => { cursorRef.current = { idx: i, pos }; }}
                        />
                      </div>
                    </div>
                  );
                })}
                {script.segments.length === 0 && (
                  <button className="btn" onClick={() => insertAfter(-1)}><Plus size={16} /> Thêm đoạn</button>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
