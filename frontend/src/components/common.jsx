import { useEffect, useState } from 'react';
import axios from 'axios';
import { FolderOpen } from 'lucide-react';
import { API_BASE } from '../constants';

/** Lấy đường dẫn mặc định từ backend một lần */
let _defaultsPromise = null;
export function useDefaults() {
  const [defaults, setDefaults] = useState(null);
  useEffect(() => {
    if (!_defaultsPromise) {
      _defaultsPromise = axios.get(`${API_BASE}/utils/defaults`).then(r => r.data).catch(() => ({}));
    }
    _defaultsPromise.then(setDefaults);
  }, []);
  return defaults;
}

export async function pickFolder() {
  try {
    const res = await axios.get(`${API_BASE}/utils/select_folder`);
    return res.data.path || '';
  } catch {
    return '';
  }
}

export function FolderInput({ id, label, value, onChange, placeholder, hint }) {
  return (
    <div className="form-group" style={{ marginBottom: 0 }}>
      {label && <label htmlFor={id}>{label}</label>}
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          id={id}
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}
        />
        <button
          type="button"
          className="btn"
          title="Mở hộp thoại chọn thư mục"
          style={{ padding: '0 18px' }}
          onClick={async () => {
            const p = await pickFolder();
            if (p) onChange(p);
          }}
        >
          <FolderOpen size={20} />
        </button>
      </div>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

export function NumberField({ id, label, value, onChange, min, max, step = 1 }) {
  const clamp = (v) => {
    if (min !== undefined) v = Math.max(min, v);
    if (max !== undefined) v = Math.min(max, v);
    return Math.round(v * 100) / 100;
  };
  return (
    <div className="form-group" style={{ marginBottom: 0 }}>
      {label && <label htmlFor={id}>{label}</label>}
      <div className="number-input-wrapper">
        <input
          id={id}
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={e => onChange(e.target.value === '' ? '' : parseFloat(e.target.value))}
          onBlur={e => onChange(clamp(parseFloat(e.target.value) || min || 0))}
        />
        <div className="number-input-controls">
          <button type="button" onClick={() => onChange(clamp((parseFloat(value) || 0) + step))}>▲</button>
          <button type="button" onClick={() => onChange(clamp((parseFloat(value) || 0) - step))}>▼</button>
        </div>
      </div>
    </div>
  );
}

export function Section({ icon: Icon, title, color = 'var(--primary)', children, style }) {
  return (
    <div className="ov-section" style={style}>
      <h3 className="ov-section-title" style={{ color }}>
        {Icon && <Icon size={20} />} {title}
      </h3>
      {children}
    </div>
  );
}
