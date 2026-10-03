import { useEffect, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, BookOpen, FolderTree, Wand2, PenLine, ArrowRight, ArrowLeft, Sparkles } from 'lucide-react';
import FileUploader from '../components/FileUploader';
import ProgressDashboard from '../components/ProgressDashboard';
import AccountPoolStatus from '../components/AccountPoolStatus';
import ScriptEditor from '../components/ScriptEditor';
import { FolderInput, NumberField, Section, useDefaults } from '../components/common';
import { API_BASE, errMsg, store } from '../constants';

const fade = { initial: { opacity: 0, y: 30 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -30 }, transition: { duration: 0.35 } };

const safeName = (s) => (s || 'Truyen').replace(/[<>:"/\\|?*]+/g, '').trim().replace(/\s+/g, '_');
const joinPath = (a, b) => (a ? a.replace(/[\\/]+$/, '') + '\\' + b : b);

/** Tab AI Đạo Diễn: EPUB -> kịch bản JSON lưu trên ổ đĩa */
export default function DirectorTab({ onEditorToggle, onSendToRender }) {
  // Job đang theo dõi được nhớ qua localStorage -> F5 vẫn quay lại màn hình tiến trình
  const [saved] = useState(() => store.get('director_job', null));
  const [step, setStep] = useState(saved ? 3 : 1);
  const [book, setBook] = useState(saved?.book || null);
  const [root, setRoot] = useState(store.get('script_root', ''));
  const [scriptDir, setScriptDir] = useState(saved?.scriptDir || '');
  const [range, setRange] = useState({ start: 1, end: 1 });
  const [overwrite, setOverwrite] = useState(false);
  const [starting, setStarting] = useState(false);
  const [editing, setEditing] = useState(false);
  const defaults = useDefaults();

  useEffect(() => {
    if (!root && defaults?.script_dir) setRoot(defaults.script_dir);
  }, [defaults]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (book && step === 2) setScriptDir(joinPath(root, `${safeName(book.book_name)}_kichban`));
  }, [root, book, step]);

  useEffect(() => {
    store.set('director_job', step === 3 && book ? { book, scriptDir } : null);
  }, [step, book, scriptDir]);

  useEffect(() => { onEditorToggle?.(editing); }, [editing, onEditorToggle]);

  const onUploaded = (data) => {
    setBook(data);
    setRange({ start: 1, end: data.total_chapters });
    setStep(2);
  };

  const start = async () => {
    if (range.start > range.end) return alert('Chương bắt đầu phải nhỏ hơn hoặc bằng chương kết thúc');
    setStarting(true);
    try {
      store.set('script_root', root);
      await axios.post(`${API_BASE}/director/start`, {
        book_id: book.book_id,
        script_dir: scriptDir,
        start_chapter: range.start,
        end_chapter: range.end,
        overwrite
      });
      setStep(3);
    } catch (e) {
      alert('Không thể bắt đầu: ' + errMsg(e));
    } finally {
      setStarting(false);
    }
  };

  if (editing) {
    return <ScriptEditor scriptDir={scriptDir} voiceMap={store.get('voice_map', undefined)} onClose={() => setEditing(false)} />;
  }

  const total = range.end >= range.start ? range.end - range.start + 1 : 0;

  return (
    <AnimatePresence mode="wait">
      {step === 1 && (
        <motion.div key="d1" {...fade}>
          <div className="tab-intro">
            <Sparkles size={18} />
            <p>AI đọc từng chương, phân <b>Dẫn truyện / Nam / Nữ</b>, chọn tốc độ và khoảng nghỉ theo tình tiết, rồi lưu thành <b>kịch bản trên ổ đĩa</b>. Lúc nào muốn tạo audio thì mở kịch bản ở tab <b>Thu Âm Kịch Bản</b>.</p>
          </div>
          <FileUploader onUploadSuccess={onUploaded} />
        </motion.div>
      )}

      {step === 2 && book && (
        <motion.div key="d2" {...fade}>
          <div className="glass-panel static-panel" style={{ padding: 36 }}>
            <h2 className="panel-title"><BrainCircuit color="var(--primary)" /> Cấu hình AI Đạo Diễn</h2>
            <p className="muted" style={{ marginBottom: 28 }}>
              <BookOpen size={15} style={{ verticalAlign: -2 }} /> {book.book_name} · {book.total_chapters} chương
            </p>

            <div className="grid-2">
              <Section icon={Wand2} title="Phạm vi xử lý">
                <div className="grid-2" style={{ gap: 16 }}>
                  <NumberField id="dir-start" label="Từ chương" value={range.start} min={1} max={book.total_chapters}
                    onChange={v => setRange(r => ({ ...r, start: v }))} />
                  <NumberField id="dir-end" label={`Đến chương (max ${book.total_chapters})`} value={range.end} min={1} max={book.total_chapters}
                    onChange={v => setRange(r => ({ ...r, end: v }))} />
                </div>
                <label className="toggle-row">
                  <span className="toggle-switch">
                    <input type="checkbox" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />
                    <span className="toggle-slider" />
                  </span>
                  <span>
                    Chạy lại các chương đã có kịch bản
                    <small>Chương đã sửa tay sẽ không bao giờ bị ghi đè</small>
                  </span>
                </label>
              </Section>

              <Section icon={FolderTree} title="Lưu kịch bản" color="var(--success)">
                <FolderInput id="dir-root" label="Thư mục gốc" value={root} onChange={setRoot} placeholder="VD: D:\KichBan" />
                <div className="path-preview">
                  <span>Kịch bản sẽ lưu tại</span>
                  <input className="mono" value={scriptDir} onChange={e => setScriptDir(e.target.value)} />
                </div>
              </Section>
            </div>

            <div style={{ marginTop: 24 }}>
              <AccountPoolStatus />
            </div>

            <div className="panel-footer">
              <button className="btn" onClick={() => setStep(1)}><ArrowLeft size={18} /> Quay lại</button>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span className="muted">{total} chương</span>
                <button id="director-start-btn" className="btn btn-primary glow-pulse" disabled={!total || !scriptDir || starting} onClick={start}
                  style={{ padding: '14px 32px', fontSize: '1.1rem' }}>
                  <BrainCircuit size={20} /> {starting ? 'Đang khởi động...' : 'Bắt đầu phân tích'}
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {step === 3 && book && (
        <motion.div key="d3" {...fade}>
          <ProgressDashboard
            title="AI Đạo Diễn"
            wsPath={`/director/${book.book_id}/ws`}
            stopPath={`/director/${book.book_id}/stop`}
            startPath="/director/start"
            doneText={`Kịch bản đã lưu tại ${scriptDir}. Có thể sửa lại hoặc đem sang tab Thu Âm.`}
            onReset={() => { setBook(null); setStep(1); }}
            resetLabel="Truyện khác"
            doneActions={
              <button className="cyber-btn btn-success" onClick={() => onSendToRender?.(scriptDir)}>
                <ArrowRight size={18} /> Thu âm ngay
              </button>
            }
          >
            <div className="dash-toolbar">
              <AccountPoolStatus compact />
              <button id="director-open-editor" className="btn" onClick={() => setEditing(true)}>
                <PenLine size={16} /> Xem / sửa kịch bản
              </button>
            </div>
          </ProgressDashboard>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
