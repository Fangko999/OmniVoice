import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Play, Pause, AlertTriangle, CheckCircle, RefreshCw, Terminal, Clock, Activity } from 'lucide-react';
import { formatTime } from '../utils';

import { API_BASE, WS_BASE } from '../constants';

export default function ProgressDashboard({
  bookId,
  onReset,
  wsPath,
  stopPath,
  startPath,
  title = 'Cốt Lõi Xử Lý',
  resetLabel = 'Tạo Truyện Mới',
  doneText = 'Toàn bộ Audio đã được tạo thành công và lưu vào thư mục đích.',
  doneActions = null,
  children = null
}) {
  wsPath = wsPath || `/batch/${bookId}/ws`;
  stopPath = stopPath || `/batch/${bookId}/stop`;
  startPath = startPath || `/batch/${bookId}/start`;
  const [state, setState] = useState(null);
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);
  const logEndRef = useRef(null);
  const [eta, setEta] = useState(null);
  const [startTime, setStartTime] = useState(null);

  useEffect(() => {
    if (state?.status === 'running') {
      if (!startTime) setStartTime(Date.now());
    } else if (state?.status === 'completed' || state?.status === 'idle') {
      setStartTime(null);
    }
  }, [state?.status, startTime]);

  useEffect(() => {
    if (!state || state.status !== 'running') return;
    
    let startChapter = state.config?.start_chapter || 1;
    let endChapter = state.config?.end_chapter || state.total_chapters;
    let totalTasks = endChapter - startChapter + 1;
    let completed = state.completed_chapters.filter(c => c >= startChapter && c <= endChapter).length;
    let remaining = totalTasks - completed;
    
    if (remaining <= 0) {
      setEta("Sắp hoàn thành...");
      return;
    }
    
    let avgChars = state.avg_chars_per_chapter || 2000;
    const kind = wsPath.split('/')[1];
    const paceKey = kind === 'batch' ? 'ai_sec_per_char' : `${kind}_sec_per_char`;
    let estimatedSecsPerChar = parseFloat(localStorage.getItem(paceKey) || '0.0025');
    
    if (completed > 0 && startTime) {
       let elapsed = (Date.now() - startTime) / 1000;
       let actualPacePerChap = Math.max(elapsed / completed, 1); 
       let actualPacePerChar = actualPacePerChap / avgChars;
       estimatedSecsPerChar = (actualPacePerChar * 0.7) + (estimatedSecsPerChar * 0.3);
       localStorage.setItem(paceKey, estimatedSecsPerChar);
    }
    
    let remainingSecs = Math.ceil(remaining * avgChars * estimatedSecsPerChar);
    setEta(formatTime(remainingSecs));
  }, [state, startTime, wsPath]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  useEffect(() => {
    if (!wsPath) return;
    let closedByUs = false;
    setState(null);
    setLogs([]);

    const connectWs = () => {
      const ws = new WebSocket(`${WS_BASE}${wsPath}`);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(data);
          
          if (data.current_log) {
            setLogs(prev => {
              if (prev.length > 0 && prev[prev.length - 1].msg === data.current_log) {
                return prev;
              }
              return [...prev, { time: new Date().toLocaleTimeString(), msg: data.current_log }];
            });
          }
        } catch (e) {
          console.error("WS Parse Error", e);
        }
      };

      ws.onclose = () => {
        if (!closedByUs) setTimeout(connectWs, 3000);
      };

      wsRef.current = ws;
    };

    connectWs();

    return () => {
      closedByUs = true;
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [wsPath]);

  const handlePause = async () => {
    try {
      await axios.post(`${API_BASE}${stopPath}`);
    } catch (err) {
      console.error(err);
    }
  };

  const handleResume = async () => {
    try {
      if (state && state.config) {
        await axios.post(`${API_BASE}${startPath}`, state.config);
      }
    } catch (err) {
      alert('Không thể tiếp tục: ' + (err.response?.data?.detail || err.message));
    }
  };

  if (!state) {
    return (
      <div className="glass-panel flex-center cyber-panel" style={{ padding: '80px', flexDirection: 'column' }}>
        <RefreshCw className="animate-spin-slow" size={64} color="var(--primary)" style={{ marginBottom: '24px' }} />
        <h3 style={{ color: 'var(--text-muted)' }}>Đang thiết lập liên kết hệ thống...</h3>
      </div>
    );
  }

  let start = state.config?.start_chapter || 1;
  let end = state.config?.end_chapter || state.total_chapters;
  let totalTasks = end - start + 1;
  let completed = state.completed_chapters.filter(c => c >= start && c <= end).length;
  let progressPercent = totalTasks > 0 ? (completed / totalTasks) * 100 : 0;

  let isRunning = state.status === 'running' || state.status === 'waiting';
  let isError = state.status === 'error';
  let isDone = state.status === 'completed';
  let isPausedWithReason = state.status === 'paused' && state.error_msg;
  
  return (
    <div className="glass-panel cyber-panel" style={{ padding: '40px', position: 'relative' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '40px' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Activity className={isRunning ? 'pulse-icon' : ''} color="var(--accent)" />
            {title}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`status-dot ${isRunning ? 'running' : isDone ? 'done' : 'error'}`}></span>
            Dự án: <span style={{ color: '#fff' }}>{state.book_name}</span>
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '16px' }}>
          {isRunning && (
            <button className="cyber-btn btn-warning" onClick={handlePause}>
              <Pause size={18} /> Tạm dừng
            </button>
          )}
          {(!isRunning && !isDone) && (
            <button className="cyber-btn btn-success" onClick={handleResume}>
              <Play size={18} /> Tiếp tục chạy
            </button>
          )}
          {isDone && doneActions}
          {isDone && onReset && (
            <button className="cyber-btn btn-primary" onClick={onReset}>
              <RefreshCw size={18} /> {resetLabel}
            </button>
          )}
        </div>
      </div>

      {children}

      {isPausedWithReason && (
        <div className="alert-box alert-warning animate-slide-up">
          <AlertTriangle size={28} />
          <div>
            <h4>Đã tạm dừng</h4>
            <p>{state.error_msg}</p>
          </div>
        </div>
      )}

      {isError && (
        <div className="alert-box alert-error animate-slide-up">
          <AlertTriangle size={28} />
          <div>
            <h4>Hệ thống báo lỗi</h4>
            <p>{state.error_msg}</p>
          </div>
        </div>
      )}

      {isDone && (
        <div className="alert-box alert-success animate-slide-up">
          <CheckCircle size={32} />
          <div>
            <h4>Hoàn thành xuất sắc!</h4>
            <p>{doneText}</p>
          </div>
        </div>
      )}

      {/* Tương lai 2D: Thanh Progress Cyberpunk */}
      <div className="cyber-progress-container">
        <div className="progress-header">
          <div className="progress-stats">
            <span className="label">Tiến độ tổng thể</span>
            <div className="value">{completed} / {totalTasks} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>chương</span></div>
          </div>
          <div className="progress-percent-wrapper">
            {isRunning && eta && (
              <div className="eta-badge">
                <Clock size={14} /> ETA: {eta}
              </div>
            )}
            <span className="progress-percent">{Math.round(progressPercent)}%</span>
          </div>
        </div>
        
        <div className="cyber-progress-track">
          <div className="cyber-progress-fill" style={{ width: `${progressPercent}%` }}>
            {isRunning && <div className="cyber-progress-glow"></div>}
          </div>
        </div>
      </div>

      {/* Terminal 2D Đỉnh Cao */}
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '2px', fontSize: '1rem' }}>
        <Terminal size={18} /> Terminal Hệ Thống
      </h3>
      
      <div className="cyber-terminal">
        <div className="terminal-scanline"></div>
        <div className="terminal-content">
          {logs.length === 0 ? (
            <div className="terminal-line">
              <span className="term-prefix">[SYS]</span>
              <span className="term-text blink">Khởi tạo luồng dữ liệu liên kết Kokoro AI...</span>
            </div>
          ) : (
            logs.map((log, i) => {
              const isErr = log.msg.includes('Lỗi');
              const isDone = log.msg.includes('Hoàn thành');
              const isInfo = log.msg.includes('luồng') || log.msg.includes('Chế độ');
              
              let prefix = '[RUN]';
              let colorClass = 'term-text';
              
              if (isErr) { prefix = '[ERR]'; colorClass = 'term-danger'; }
              else if (isDone) { prefix = '[OK]'; colorClass = 'term-success'; }
              else if (isInfo) { prefix = '[SYS]'; colorClass = 'term-info'; }

              return (
                <div key={i} className="terminal-line animate-slide-up" style={{ animationDuration: '0.3s' }}>
                  <span className="term-time">{log.time}</span>
                  <span className={`term-prefix ${colorClass}`}>{prefix}</span>
                  <span className={`term-message ${colorClass}`}>{log.msg}</span>
                </div>
              );
            })
          )}
          <div ref={logEndRef} style={{ height: '10px' }} />
        </div>
      </div>

    </div>
  );
}
