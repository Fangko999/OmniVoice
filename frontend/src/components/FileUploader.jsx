import { useState, useRef } from 'react';
import axios from 'axios';
import { UploadCloud, Loader2, BookOpen } from 'lucide-react';

const API_BASE = '/api';

export default function FileUploader({ onUploadSuccess }) {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      checkFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      checkFile(e.target.files[0]);
    }
  };

  const checkFile = (selectedFile) => {
    if (!selectedFile.name.endsWith('.epub')) {
      setError('Vui lòng chọn file định dạng .epub');
      setFile(null);
      return;
    }
    setError('');
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await axios.post(`${API_BASE}/upload/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      onUploadSuccess(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Lỗi kết nối tới máy chủ');
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel" style={{ textAlign: 'center', padding: '64px 32px' }}>
      <h2 style={{ marginBottom: '32px' }}>Tải Truyện Lên Hệ Thống</h2>
      
      <div 
        className={dragActive ? 'dashed-box active' : 'dashed-box'}
        style={{
          padding: '64px',
          background: dragActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
          cursor: 'pointer',
          transition: 'all 0.3s',
          marginBottom: '32px',
          boxShadow: dragActive ? '0 0 30px rgba(139, 92, 246, 0.2)' : 'none',
          transform: dragActive ? 'scale(1.02)' : 'scale(1)'
        }}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
      >
        <input 
          ref={inputRef}
          type="file" 
          accept=".epub"
          onChange={handleChange} 
          style={{ display: 'none' }} 
        />
        
        {file ? (
          <div className="animate-slide-up" style={{ animation: 'slideUpFade 0.4s ease-out' }}>
            <div style={{
              width: 80, height: 80, margin: '0 auto 24px',
              background: 'var(--primary-glow)', borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px var(--primary-glow)'
            }}>
              <BookOpen size={40} color="var(--text-main)" />
            </div>
            <h3 style={{ marginBottom: '8px', fontSize: '1.4rem' }}>{file.name}</h3>
            <p style={{ color: 'var(--text-muted)' }}>{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        ) : (
          <div>
            <UploadCloud 
              size={64} 
              color={dragActive ? "var(--primary)" : "var(--text-muted)"} 
              style={{ margin: '0 auto 24px', transition: 'all 0.3s', transform: dragActive ? 'translateY(-10px)' : 'none' }} 
            />
            <h3 style={{ marginBottom: '12px', fontSize: '1.3rem' }}>
              {dragActive ? 'Thả file vào đây!' : 'Kéo thả file EPUB vào đây'}
            </h3>
            <p style={{ color: 'var(--text-muted)' }}>hoặc click để chọn file từ máy tính</p>
          </div>
        )}
      </div>

      {error && <p style={{ color: 'var(--danger)', marginBottom: '24px', fontWeight: 500 }}>{error}</p>}
      
      <button 
        className="btn btn-primary glow-pulse" 
        onClick={handleUpload} 
        disabled={!file || loading}
        style={{ minWidth: '240px', padding: '16px 32px', fontSize: '1.1rem' }}
      >
        {loading ? (
          <><Loader2 className="animate-spin-slow" /> Đang phân tích...</>
        ) : (
          'Tiếp tục'
        )}
      </button>
    </div>
  );
}
