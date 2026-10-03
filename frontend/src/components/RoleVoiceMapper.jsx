import { useRef, useState } from 'react';
import { Play, Square, Mic2 } from 'lucide-react';
import { ROLES, VOICES } from '../constants';

const ROLE_HINT = {
  narrator: 'Lời dẫn, miêu tả',
  male: 'Thoại nam + nhân vật không rõ giới tính',
  female: 'Thoại nữ'
};

/** Gán 3 vai (narrator / male / female) cho 3 giọng Kokoro */
export default function RoleVoiceMapper({ voiceMap, onChange }) {
  const [playing, setPlaying] = useState(null);
  const audioRef = useRef(null);

  const stop = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlaying(null);
  };

  const play = (role) => {
    stop();
    const a = new Audio(`/samples/${voiceMap[role]}.wav`);
    a.onended = () => setPlaying(null);
    a.play();
    audioRef.current = a;
    setPlaying(role);
  };

  return (
    <div className="role-mapper">
      {ROLES.map(r => {
        const isPlaying = playing === r.id;
        const sorted = [...VOICES].sort((a, b) => {
          const pref = r.id === 'female' ? 'F' : r.id === 'male' ? 'M' : null;
          if (!pref) return 0;
          return (a.gender === pref ? 0 : 1) - (b.gender === pref ? 0 : 1);
        });
        return (
          <div key={r.id} className={`role-card ${isPlaying ? 'playing' : ''}`} style={{ '--role-color': r.color }}>
            <div className="role-card-head">
              <span className="role-badge"><Mic2 size={14} /> {r.label}</span>
              <span className="role-hint">{ROLE_HINT[r.id]}</span>
            </div>
            <select
              id={`voice-${r.id}`}
              value={voiceMap[r.id]}
              onChange={e => { stop(); onChange({ ...voiceMap, [r.id]: e.target.value }); }}
            >
              {sorted.map(v => <option key={v.id} value={v.id}>{v.name} — {v.type}</option>)}
            </select>
            <button
              type="button"
              className="btn btn-sm"
              style={{ width: '100%', marginTop: 10 }}
              onClick={() => (isPlaying ? stop() : play(r.id))}
            >
              {isPlaying ? <Square size={14} /> : <Play size={14} />} {isPlaying ? 'Dừng' : 'Nghe thử'}
            </button>
          </div>
        );
      })}
    </div>
  );
}
