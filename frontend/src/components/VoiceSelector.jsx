import { useState, useRef } from 'react';
import axios from 'axios';
import { Play, Square, Loader2, ArrowRight, ArrowLeft, Mic2, User } from 'lucide-react';

import { API_BASE, VOICES } from '../constants';

export default function VoiceSelector({ bookId, bookName, voiceConfig, onChange, onNext, onBack }) {
  const [playing, setPlaying] = useState(null); // 'narrator_voice', 'dialogue_voice', 'chapter_preview'
  const [loadingAudio, setLoadingAudio] = useState(null);
  const audioRef = useRef(null);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setPlaying(null);
    }
  };

  const playStaticSample = (type) => {
    stopAudio();
    const voiceId = voiceConfig[type];
    const audio = new Audio(`/samples/${voiceId}.wav`);
    audioRef.current = audio;
    
    audio.onended = () => {
      setPlaying(null);
      audioRef.current = null;
    };
    
    audio.play();
    setPlaying(type);
  };

  const playChapterPreview = async () => {
    stopAudio();
    setLoadingAudio('chapter_preview');
    
    try {
      const response = await axios.post(`${API_BASE}/preview/preview_chapter`, {
        book_id: bookId,
        narrator_voice: voiceConfig.narrator_voice,
        dialogue_voice: voiceConfig.reading_mode === 'dual' ? voiceConfig.dialogue_voice : null,
        reading_mode: voiceConfig.reading_mode,
        speed: 1.0
      }, { responseType: 'blob' });
      
      const audioUrl = URL.createObjectURL(response.data);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      
      audio.onended = () => {
        setPlaying(null);
        URL.revokeObjectURL(audioUrl);
      };
      
      audio.play();
      setPlaying('chapter_preview');
    } catch (err) {
      alert('Lỗi tạo âm thanh nghe thử chương: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoadingAudio(null);
    }
  };

  const renderVoiceCard = (title, typeKey) => {
    const selectedId = voiceConfig[typeKey];
    const selectedVoice = VOICES.find(v => v.id === selectedId);
    const isPlaying = playing === typeKey;

    return (
      <div className={`glass-panel ${isPlaying ? 'active' : ''}`} style={{ padding: '24px', borderRadius: '16px' }}>
        <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Mic2 size={20} color="var(--primary)" /> {title}
        </h3>
        
        <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
          <div style={{
            width: '60px', height: '60px', borderRadius: '12px',
            background: isPlaying ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.3s',
            boxShadow: isPlaying ? '0 0 20px var(--primary-glow)' : 'none'
          }}>
            <User size={32} color={isPlaying ? 'white' : 'var(--text-muted)'} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="form-group" style={{ marginBottom: '0' }}>
              <select 
                value={selectedId}
                onChange={(e) => onChange({...voiceConfig, [typeKey]: e.target.value})}
                style={{ fontSize: '1.1rem', fontWeight: 600, padding: '10px 16px', marginBottom: '4px' }}
              >
                {VOICES.map(v => <option key={v.id} value={v.id}>{v.name} - {v.type}</option>)}
              </select>
            </div>
            {isPlaying && (
              <div className="audio-bars" style={{ height: '20px', marginTop: '8px', opacity: 0.8 }}>
                {[1,2,3,4,5,6,7,8].map(i => <span key={i} className="bar" style={{ width: '4px', background: 'var(--accent)' }} />)}
              </div>
            )}
          </div>
        </div>
        
        <button 
          className="btn" 
          style={{ 
            width: '100%', 
            background: isPlaying ? 'rgba(244, 63, 94, 0.2)' : 'rgba(255, 255, 255, 0.05)',
            borderColor: isPlaying ? 'var(--danger)' : 'rgba(255, 255, 255, 0.1)',
            color: isPlaying ? 'var(--danger)' : 'var(--text-main)'
          }}
          onClick={() => isPlaying ? stopAudio() : playStaticSample(typeKey)}
        >
          {isPlaying ? <Square size={18} /> : <Play size={18} />}
          {isPlaying ? 'Dừng phát' : 'Nghe Thử'}
        </button>
      </div>
    );
  };

  return (
    <div className="glass-panel" style={{ padding: '40px' }}>
      <h2 style={{ marginBottom: '8px', fontSize: '2rem' }}>Casting Giọng Đọc</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '32px', fontSize: '1.1rem' }}>
        Truyện đang xử lý: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{bookName}</span>
      </p>
      
      <div style={{ background: 'rgba(0,0,0,0.3)', padding: '24px', borderRadius: '16px', border: '1px solid var(--surface-border)', marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '16px', color: 'var(--primary)' }}>Chế Độ Đọc</h3>
        <select 
          value={voiceConfig.reading_mode}
          onChange={(e) => onChange({...voiceConfig, reading_mode: e.target.value})}
          style={{ width: '100%', padding: '12px 16px', fontSize: '1.1rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)' }}
        >
          <option value="dual">Phân 2 giọng (Người Dẫn Truyện & Nhân Vật)</option>
          <option value="single">Đọc 1 giọng (Đơn giọng toàn truyện)</option>
        </select>
      </div>
      
      <div className="grid-2">
        {renderVoiceCard(voiceConfig.reading_mode === 'single' ? 'Giọng Đọc Chính' : 'Lời Dẫn Truyện', 'narrator_voice')}
        {voiceConfig.reading_mode === 'dual' && renderVoiceCard('Lời Thoại (Nhân Vật)', 'dialogue_voice')}
      </div>
      
      {/* Chapter Preview Section */}
      <div style={{ 
        background: 'rgba(0,0,0,0.3)', border: '1px solid var(--glass-border)',
        padding: '24px', borderRadius: '16px', marginTop: '32px', 
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' 
      }}>
        <div>
          <h3 style={{ marginBottom: '8px', color: 'var(--accent)' }}>Nghe Thử Trực Tiếp Đoạn Truyện</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0' }}>
            Hệ thống sẽ tổng hợp 3 câu đầu tiên trong sách với thiết lập giọng trên.
          </p>
        </div>
        
        <button 
          className={`btn ${playing === 'chapter_preview' ? '' : 'btn-primary'}`}
          style={{ 
            minWidth: '200px', padding: '16px',
            background: playing === 'chapter_preview' ? 'rgba(244, 63, 94, 0.2)' : '',
            borderColor: playing === 'chapter_preview' ? 'var(--danger)' : '',
            color: playing === 'chapter_preview' ? 'var(--danger)' : ''
          }}
          onClick={() => playing === 'chapter_preview' ? stopAudio() : playChapterPreview()}
          disabled={loadingAudio !== null}
        >
          {loadingAudio === 'chapter_preview' ? <Loader2 className="animate-spin-slow" size={20} /> :
           playing === 'chapter_preview' ? <Square size={20} /> : <Play size={20} />}
          <span style={{ fontWeight: 600 }}>
            {loadingAudio === 'chapter_preview' ? 'Đang tạo...' :
             playing === 'chapter_preview' ? 'Dừng phát' : 'Tạo Demo Bằng Sách Này'}
          </span>
        </button>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '48px' }}>
        <button className="btn" onClick={() => { stopAudio(); onBack(); }} style={{ padding: '12px 24px' }}>
          <ArrowLeft size={18} /> Quay lại
        </button>
        <button className="btn btn-primary" onClick={() => { stopAudio(); onNext(); }} style={{ padding: '12px 32px' }}>
          Tới Bước Cấu Hình <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
