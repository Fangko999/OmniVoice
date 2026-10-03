import { useState } from 'react';
import axios from 'axios';
import { ArrowRight, ArrowLeft, Rocket, FolderOpen, BrainCircuit, HardDrive, Settings2, Clock } from 'lucide-react';
import { formatTime } from '../utils';

const API_BASE = '/api';

export default function BatchConfig({ bookData, initialConfig, onStart, onBack }) {
  const [config, setConfig] = useState(initialConfig);

  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleSelectFolder = async () => {
    try {
      const res = await axios.get(`${API_BASE}/utils/select_folder`);
      if (res.data.path) {
        handleChange('output_dir', res.data.path);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleStart = () => {
    let finalStart = Math.max(1, Math.min(config.start_chapter, bookData?.total_chapters || 1));
    let finalEnd = Math.max(1, Math.min(config.end_chapter, bookData?.total_chapters || 1));
    
    if (finalStart > finalEnd) {
      alert('Lỗi: Chương bắt đầu không được lớn hơn chương kết thúc!');
      return;
    }
    
    onStart({
      ...config,
      start_chapter: finalStart,
      end_chapter: finalEnd
    });
  };

  const finalStart = Math.max(1, Math.min(config.start_chapter, bookData?.total_chapters || 1));
  const finalEnd = Math.max(1, Math.min(config.end_chapter, bookData?.total_chapters || 1));
  const totalTasks = finalEnd >= finalStart ? finalEnd - finalStart + 1 : 0;
  
  const avgChars = bookData?.avg_chars_per_chapter || 2000;
  
  const estimatedSecsPerChar = parseFloat(localStorage.getItem('ai_sec_per_char') || '0.0025');
    
  const remainingSecs = totalTasks > 0 ? totalTasks * avgChars * estimatedSecsPerChar : 0;
  
  const etaStr = remainingSecs > 0 ? formatTime(remainingSecs) : 'Không hợp lệ';

  return (
    <div className="glass-panel" style={{ padding: '40px' }}>
      <h2 style={{ marginBottom: '32px', fontSize: '2rem' }}>Cấu Hình Tiến Trình</h2>
      
      <div className="grid-2">
        <div style={{ background: 'rgba(0,0,0,0.3)', padding: '24px', borderRadius: '16px', border: '1px solid var(--surface-border)' }}>
          <h3 style={{ marginBottom: '24px', fontSize: '1.2rem', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings2 size={20} /> Tham số xuất bản
          </h3>
          
          <div className="grid-2" style={{ gap: '16px', alignItems: 'flex-end' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Từ chương</label>
              <div className="number-input-wrapper">
                <input 
                  type="number" 
                  min={1} max={bookData?.total_chapters} 
                  value={config.start_chapter}
                  onChange={e => handleChange('start_chapter', parseInt(e.target.value) || 1)}
                />
                <div className="number-input-controls">
                  <button type="button" onClick={() => handleChange('start_chapter', Math.min((config.start_chapter || 0) + 1, bookData?.total_chapters || 9999))}>▲</button>
                  <button type="button" onClick={() => handleChange('start_chapter', Math.max((config.start_chapter || 0) - 1, 1))}>▼</button>
                </div>
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Đến chương (Max: {bookData?.total_chapters})</label>
              <div className="number-input-wrapper">
                <input 
                  type="number" 
                  min={1} max={bookData?.total_chapters} 
                  value={config.end_chapter}
                  onChange={e => handleChange('end_chapter', parseInt(e.target.value) || 1)}
                />
                <div className="number-input-controls">
                  <button type="button" onClick={() => handleChange('end_chapter', Math.min((config.end_chapter || 0) + 1, bookData?.total_chapters || 9999))}>▲</button>
                  <button type="button" onClick={() => handleChange('end_chapter', Math.max((config.end_chapter || 0) - 1, 1))}>▼</button>
                </div>
              </div>
            </div>
          </div>
          
          <div className="form-group" style={{ marginTop: '16px' }}>
            <label>Khoảng nghỉ giữa các câu (giây)</label>
            <div className="number-input-wrapper">
              <input 
                type="number" 
                step="0.1"
                min={0}
                value={config.gap_seconds}
                onChange={e => handleChange('gap_seconds', parseFloat(e.target.value) || 0)}
              />
              <div className="number-input-controls">
                <button type="button" onClick={() => handleChange('gap_seconds', Math.round(((config.gap_seconds || 0) + 0.1) * 10) / 10)}>▲</button>
                <button type="button" onClick={() => handleChange('gap_seconds', Math.max(Math.round(((config.gap_seconds || 0) - 0.1) * 10) / 10, 0))}>▼</button>
              </div>
            </div>
          </div>
          
          <div className="form-group" style={{ marginTop: '16px', marginBottom: 0 }}>
            <label>Định dạng xuất file</label>
            <select 
              value={config.format}
              onChange={e => handleChange('format', e.target.value)}
            >
              <option value="mp3">MP3 (Nén, tiết kiệm dung lượng)</option>
              <option value="wav">WAV (Chất lượng gốc Studio)</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>


          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '24px', borderRadius: '16px', border: '1px solid var(--surface-border)' }}>
            <h3 style={{ marginBottom: '20px', fontSize: '1.2rem', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HardDrive size={20} /> Lưu trữ
            </h3>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Thư mục đích trên máy tính</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input 
                  type="text" 
                  value={config.output_dir}
                  onChange={e => handleChange('output_dir', e.target.value)}
                  placeholder="VD: D:\Audiobooks"
                  style={{ flex: 1, fontFamily: 'var(--font-mono)' }}
                />
                <button className="btn" onClick={handleSelectFolder} title="Mở hộp thoại chọn thư mục" style={{ padding: '0 20px' }}>
                  <FolderOpen size={20} />
                </button>
              </div>
              <div style={{ marginTop: '12px', background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '8px', border: '1px dashed rgba(255,255,255,0.1)' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Folder tạo ra sẽ là:</p>
                <p style={{ fontFamily: 'var(--font-mono)', color: 'var(--success)', marginTop: '4px', wordBreak: 'break-all' }}>
                  {config.output_dir}\{bookData?.book_name || 'Ten_Truyen'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '48px', alignItems: 'center' }}>
        <button className="btn" onClick={onBack} style={{ padding: '12px 24px' }}>
          <ArrowLeft size={18} /> Quay lại
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ textAlign: 'right' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem', display: 'block', marginBottom: '4px' }}>Dự kiến hoàn thành:</span>
            <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
              <Clock size={16} /> {etaStr}
            </span>
          </div>
          <button 
            className="btn btn-primary glow-pulse" 
            onClick={handleStart}
            style={{ padding: '16px 40px', fontSize: '1.2rem', borderRadius: '16px' }}
            disabled={remainingSecs <= 0}
          >
            <Rocket size={24} style={{ marginRight: '8px' }} /> 
            KHỞI ĐỘNG HỆ THỐNG
          </button>
        </div>
      </div>
    </div>
  );
}
