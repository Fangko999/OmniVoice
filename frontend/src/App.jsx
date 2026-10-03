import { useCallback, useState } from 'react';
import { Zap, BrainCircuit, Clapperboard } from 'lucide-react';
import AnimatedBackground from './components/AnimatedBackground';
import FastModeTab from './tabs/FastModeTab';
import DirectorTab from './tabs/DirectorTab';
import RenderTab from './tabs/RenderTab';
import { store } from './constants';
import './index.css';

const TABS = [
  { id: 'fast', label: 'Đọc Nhanh', desc: 'EPUB → Audio, tách thoại theo ngoặc kép', icon: Zap },
  { id: 'director', label: 'AI Đạo Diễn', desc: 'EPUB → Kịch bản phân vai, nhịp đọc', icon: BrainCircuit },
  { id: 'render', label: 'Thu Âm Kịch Bản', desc: 'Kịch bản → Audio diễn cảm', icon: Clapperboard }
];

function App() {
  const [tab, setTab] = useState(store.get('tab', 'fast'));
  const [handoff, setHandoff] = useState(null);
  const [editorOpen, setEditorOpen] = useState({ director: false, render: false });

  const switchTab = (id) => {
    setTab(id);
    store.set('tab', id);
  };

  const sendToRender = useCallback((dir) => {
    setHandoff({ dir, t: Date.now() });
    switchTab('render');
  }, []);

  const onDirectorEditor = useCallback((v) => setEditorOpen(s => ({ ...s, director: v })), []);
  const onRenderEditor = useCallback((v) => setEditorOpen(s => ({ ...s, render: v })), []);
  const wide = editorOpen[tab];

  return (
    <>
      <AnimatedBackground />
      <div className={`app-container ${wide ? 'wide' : ''}`}>
        <header className="header animate-slide-up" style={{ marginBottom: wide ? 24 : 36 }}>
          <div className="logo-wrapper">
            <div className="audio-bars">
              {[1, 2, 3, 4, 5].map(i => <span key={i} className="bar" />)}
            </div>
            <h1 className="logo-text" style={wide ? { fontSize: '2.4rem' } : undefined}>OmniVoice</h1>
          </div>
          {!wide && <p className="subtitle">Hệ thống chuyển đổi EPUB sang Audiobook tiếng Việt</p>}
        </header>

        <nav className="tab-nav animate-slide-up" role="tablist" aria-label="Chế độ làm việc">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                aria-selected={tab === t.id}
                className={`tab-btn ${tab === t.id ? 'active' : ''}`}
                onClick={() => switchTab(t.id)}
              >
                <Icon size={20} />
                <span className="tab-text">
                  <span className="tab-label">{t.label}</span>
                  <span className="tab-desc">{t.desc}</span>
                </span>
              </button>
            );
          })}
        </nav>

        {/* Không unmount tab khi chuyển để giữ tiến trình và WebSocket */}
        <div role="tabpanel" hidden={tab !== 'fast'}><FastModeTab /></div>
        <div role="tabpanel" hidden={tab !== 'director'}>
          <DirectorTab onSendToRender={sendToRender} onEditorToggle={onDirectorEditor} />
        </div>
        <div role="tabpanel" hidden={tab !== 'render'}>
          <RenderTab incomingDir={handoff} onEditorToggle={onRenderEditor} />
        </div>
      </div>
    </>
  );
}

export default App;
