import { useEffect, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Clapperboard, FolderOpen, Mic2, Settings2, HardDrive, PenLine, Rocket, ArrowLeft, AlertTriangle, History, FileText } from 'lucide-react';
import ProgressDashboard from '../components/ProgressDashboard';
import RoleVoiceMapper from '../components/RoleVoiceMapper';
import ScriptEditor from '../components/ScriptEditor';
import { FolderInput, NumberField, Section, useDefaults } from '../components/common';
import { API_BASE, errMsg, store } from '../constants';

const fade = { initial: { opacity: 0, y: 30 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -30 }, transition: { duration: 0.35 } };
const DEFAULT_MAP = { narrator: 'my_yen', male: 'tuan_ngoc', female: 'ngoc_huyen' };

function addRecent(dir) {
  const list = store.get('recent_scripts', []).filter(d => d !== dir);
  store.set('recent_scripts', [dir, ...list].slice(0, 8));
}

/** Tab Thu Âm Kịch Bản: mở thư mục kịch bản bất kỳ -> gán giọng -> render */
export default function RenderTab({ incomingDir, onEditorToggle }) {
  const [step, setStep] = useState(1);
  const [dirInput, setDirInput] = useState('');
  const [project, setProject] = useState(null); // { script_dir, manifest, available_chapters }
  const [opening, setOpening] = useState(false);
  const [voiceMap, setVoiceMap] = useState(store.get('voice_map', DEFAULT_MAP));
  const [cfg, setCfg] = useState({
    start: 1, end: 1,
    global_speed: store.get('render_speed', 1.0),
    gap_seconds: store.get('render_gap', 0.4),
    format: store.get('render_format', 'mp3'),
    output_dir: store.get('output_dir', '')
  });
  const [jobId, setJobId] = useState(null);
  const [editing, setEditing] = useState(false);
  const [recent, setRecent] = useState(store.get('recent_scripts', []));
  const defaults = useDefaults();

  useEffect(() => {
    if (!cfg.output_dir && defaults?.output_dir) setCfg(c => ({ ...c, output_dir: defaults.output_dir }));
  }, [defaults]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { onEditorToggle?.(editing); }, [editing, onEditorToggle]);
  useEffect(() => { store.set('voice_map', voiceMap); }, [voiceMap]);

  const open = async (dir) => {
    if (!dir) return;
    setOpening(true);
    try {
      const r = await axios.post(`${API_BASE}/scripts/open`, { script_dir: dir });
      const avail = r.data.available_chapters;
      setProject(r.data);
      setDirInput(dir);
      setCfg(c => ({ ...c, start: avail[0] || 1, end: avail[avail.length - 1] || 1 }));
      addRecent(dir);
      setRecent(store.get('recent_scripts', []));
      setStep(2);
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setOpening(false);
    }
  };

  useEffect(() => {
    if (incomingDir?.dir) open(incomingDir.dir);
  }, [incomingDir]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    if (cfg.start > cfg.end) return alert('Chương bắt đầu phải nhỏ hơn hoặc bằng chương kết thúc');
    store.set('render_speed', cfg.global_speed);
    store.set('render_gap', cfg.gap_seconds);
    store.set('render_format', cfg.format);
    store.set('output_dir', cfg.output_dir);
    try {
      const r = await axios.post(`${API_BASE}/render/start`, {
        script_dir: project.script_dir,
        voice_map: voiceMap,
        start_chapter: cfg.start,
        end_chapter: cfg.end,
        global_speed: cfg.global_speed,
        gap_seconds: cfg.gap_seconds,
        format: cfg.format,
        output_dir: cfg.output_dir
      });
      setJobId(r.data.job_id);
      setStep(3);
    } catch (e) {
      alert('Không thể bắt đầu: ' + errMsg(e));
    }
  };

  if (editing && project) {
    return <ScriptEditor scriptDir={project.script_dir} voiceMap={voiceMap} onClose={() => { setEditing(false); open(project.script_dir); }} />;
  }

  const m = project?.manifest;
  const avail = project?.available_chapters || [];
  const chapters = m ? Object.values(m.chapters) : [];
  const fallbackCount = chapters.filter(c => c.fallback_chunks > 0).length;
  const editedCount = chapters.filter(c => c.edited).length;
  const inRange = avail.filter(n => n >= cfg.start && n <= cfg.end).length;

  return (
    <AnimatePresence mode="wait">
      {step === 1 && (
        <motion.div key="r1" {...fade}>
          <div className="glass-panel static-panel" style={{ padding: 36 }}>
            <h2 className="panel-title"><Clapperboard color="var(--accent)" /> Mở kịch bản</h2>
            <p className="muted" style={{ marginBottom: 24 }}>Chọn thư mục kịch bản do tab AI Đạo Diễn tạo ra (có file <span className="mono">manifest.json</span>).</p>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <FolderInput id="render-dir" label="Thư mục kịch bản" value={dirInput} onChange={setDirInput} placeholder="VD: D:\KichBan\Pham_Nhan_Tu_Tien_kichban" />
              </div>
              <button id="render-open-btn" className="btn btn-primary" disabled={!dirInput || opening} onClick={() => open(dirInput)} style={{ height: 50 }}>
                <FolderOpen size={18} /> {opening ? 'Đang mở...' : 'Mở'}
              </button>
            </div>

            {recent.length > 0 && (
              <div className="recent-list">
                <h4><History size={15} /> Mở gần đây</h4>
                {recent.map(d => (
                  <button key={d} className="recent-item" onClick={() => open(d)}>
                    <FileText size={15} /> <span className="mono">{d}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}

      {step === 2 && project && (
        <motion.div key="r2" {...fade}>
          <div className="glass-panel static-panel" style={{ padding: 36 }}>
            <div className="panel-head-row">
              <div>
                <h2 className="panel-title"><Clapperboard color="var(--accent)" /> {m.book_name}</h2>
                <p className="muted mono small">{project.script_dir}</p>
              </div>
              <button id="render-edit-btn" className="btn" onClick={() => setEditing(true)}><PenLine size={16} /> Sửa kịch bản</button>
            </div>

            <div className="stat-row">
              <div className="stat"><b>{avail.length}</b><span>chương có kịch bản</span></div>
              <div className="stat"><b>{m.total_chapters}</b><span>tổng số chương</span></div>
              <div className={`stat ${fallbackCount ? 'warn' : ''}`}><b>{fallbackCount}</b><span>chương cần kiểm tra</span></div>
              <div className="stat"><b>{editedCount}</b><span>chương đã sửa tay</span></div>
            </div>
            {fallbackCount > 0 && (
              <p className="inline-warn"><AlertTriangle size={14} /> Có {fallbackCount} chương AI không xử lý hết, phần đó dùng cách tách theo ngoặc kép. Nên mở “Sửa kịch bản” → lọc “Cần kiểm tra”.</p>
            )}

            <Section icon={Mic2} title="Gán giọng cho 3 vai" style={{ marginTop: 24 }}>
              <RoleVoiceMapper voiceMap={voiceMap} onChange={setVoiceMap} />
            </Section>

            <div className="grid-2" style={{ marginTop: 24 }}>
              <Section icon={Settings2} title="Tham số">
                <div className="grid-2" style={{ gap: 16 }}>
                  <NumberField id="render-start" label="Từ chương" value={cfg.start} min={1} max={m.total_chapters} onChange={v => setCfg(c => ({ ...c, start: v }))} />
                  <NumberField id="render-end" label="Đến chương" value={cfg.end} min={1} max={m.total_chapters} onChange={v => setCfg(c => ({ ...c, end: v }))} />
                  <NumberField id="render-speed" label="Tốc độ tổng (×)" value={cfg.global_speed} min={0.5} max={2} step={0.05} onChange={v => setCfg(c => ({ ...c, global_speed: v }))} />
                  <NumberField id="render-gap" label="Nghỉ mặc định (s)" value={cfg.gap_seconds} min={0} max={3} step={0.1} onChange={v => setCfg(c => ({ ...c, gap_seconds: v }))} />
                </div>
                <p className="field-hint">Tốc độ tổng nhân với tốc độ AI chọn cho từng đoạn. “Nghỉ mặc định” chỉ dùng cho đoạn không có khoảng nghỉ riêng.</p>
              </Section>
              <Section icon={HardDrive} title="Xuất file" color="var(--success)">
                <div className="form-group">
                  <label htmlFor="render-format">Định dạng</label>
                  <select id="render-format" value={cfg.format} onChange={e => setCfg(c => ({ ...c, format: e.target.value }))}>
                    <option value="mp3">MP3 (nén)</option>
                    <option value="wav">WAV (gốc)</option>
                  </select>
                </div>
                <FolderInput id="render-out" label="Thư mục lưu audio" value={cfg.output_dir} onChange={v => setCfg(c => ({ ...c, output_dir: v }))}
                  hint={`Audio sẽ nằm trong: ${cfg.output_dir}\\${m.book_name}`} />
              </Section>
            </div>

            <div className="panel-footer">
              <button className="btn" onClick={() => setStep(1)}><ArrowLeft size={18} /> Chọn kịch bản khác</button>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span className="muted">{inRange} chương sẽ được thu âm</span>
                <button id="render-start-btn" className="btn btn-primary glow-pulse" disabled={!inRange || !cfg.output_dir} onClick={start}
                  style={{ padding: '14px 32px', fontSize: '1.1rem' }}>
                  <Rocket size={20} /> Bắt đầu thu âm
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {step === 3 && jobId && (
        <motion.div key="r3" {...fade}>
          <ProgressDashboard
            title="Thu Âm Kịch Bản"
            wsPath={`/render/${jobId}/ws`}
            stopPath={`/render/${jobId}/stop`}
            startPath="/render/start"
            resetLabel="Kịch bản khác"
            onReset={() => { setProject(null); setStep(1); }}
            doneActions={
              <button className="cyber-btn" onClick={() => setStep(2)}><Settings2 size={18} /> Quay lại cấu hình</button>
            }
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
