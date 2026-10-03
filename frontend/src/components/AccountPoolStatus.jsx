import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { KeyRound, RefreshCw, ShieldAlert } from 'lucide-react';
import { API_BASE, errMsg } from '../constants';

const STATUS_LABEL = {
  active: 'Sẵn sàng',
  cooldown: 'Nghỉ tạm do lỗi',
  exhausted: 'Hết hạn mức',
  auth_failed: 'Cookie hỏng',
  disabled: 'Tắt'
};

const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '');

export default function AccountPoolStatus({ pollMs = 10000, compact = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/accounts`);
      setData(r.data);
    } catch (e) {
      setData({ accounts: [], error: errMsg(e) });
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => { if (!document.hidden) load(); }, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs]);

  const reload = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API_BASE}/accounts/reload`);
      setData(r.data);
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setLoading(false);
    }
  };

  const accounts = data?.accounts || [];
  const usable = accounts.filter(a => a.status === 'active').length;

  return (
    <div className={`account-pool ${compact ? 'compact' : ''}`}>
      <div className="account-pool-head">
        <span className="account-pool-title">
          <KeyRound size={16} /> Tài khoản Gemini
          <span className={`pool-count ${usable === 0 ? 'empty' : ''}`}>{usable}/{accounts.length} sẵn sàng</span>
        </span>
        <button id="reload-accounts-btn" className="btn btn-sm" onClick={reload} disabled={loading} title="Đọc lại accounts.json">
          <RefreshCw size={14} className={loading ? 'animate-spin-slow' : ''} /> Tải lại
        </button>
      </div>

      {data?.error && (
        <p className="pool-error"><ShieldAlert size={14} /> {data.error}</p>
      )}
      {data?.ip_blocked_until && (
        <p className="pool-error"><ShieldAlert size={14} /> IP đang bị Gemini tạm chặn tới {fmtTime(data.ip_blocked_until)}</p>
      )}

      <div className="account-chips">
        {accounts.map(a => (
          <div key={a.name} className={`account-chip st-${a.status}`} title={a.last_error || ''}>
            <span className="chip-dot" />
            <span className="chip-name">{a.name}</span>
            <span className="chip-meta">
              {STATUS_LABEL[a.status] || a.status}
              {a.until ? ` · tới ${fmtTime(a.until)}` : ''}
              {` · ${a.requests_today}${a.daily_limit ? '/' + a.daily_limit : ''} req`}
              {a.quota_total ? ` · còn ${Math.round((a.quota_remaining / a.quota_total) * 100)}%` : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
