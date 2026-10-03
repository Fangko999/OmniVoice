import { useEffect, useState } from 'react';
import axios from 'axios';
import { Upload, Headphones, Settings, PlayCircle } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import FileUploader from '../components/FileUploader';
import VoiceSelector from '../components/VoiceSelector';
import BatchConfig from '../components/BatchConfig';
import ProgressDashboard from '../components/ProgressDashboard';
import { useDefaults } from '../components/common';
import { API_BASE, store } from '../constants';

const stepAnim = {
  initial: { opacity: 0, rotateX: 20, y: 50 },
  animate: { opacity: 1, rotateX: 0, y: 0 },
  exit: { opacity: 0, rotateX: -20, y: -50 },
  transition: { duration: 0.5, ease: 'easeOut' }
};

/** Chế độ Đọc Nhanh — giữ nguyên luồng 4 bước cũ */
export default function FastModeTab() {
  const [step, setStep] = useState(1);
  const [bookData, setBookData] = useState(null); // { book_id, book_name, total_chapters }
  const [voiceConfig, setVoiceConfig] = useState({
    reading_mode: 'dual',
    narrator_voice: 'my_yen',
    dialogue_voice: 'thanh_dat'
  });
  const [batchConfig, setBatchConfig] = useState({
    start_chapter: 1,
    end_chapter: 1,
    speed: 1.0,
    gap_seconds: 0.5,
    format: 'mp3',
    output_dir: store.get('output_dir', '')
  });
  const defaults = useDefaults();

  useEffect(() => {
    if (defaults?.output_dir && !batchConfig.output_dir) {
      setBatchConfig(prev => ({ ...prev, output_dir: defaults.output_dir }));
    }
  }, [defaults]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUploadSuccess = (data) => {
    setBookData(data);
    setBatchConfig(prev => ({ ...prev, end_chapter: data.total_chapters }));
    setStep(2);
  };

  const handleStartBatch = async (finalConfig) => {
    try {
      store.set('output_dir', finalConfig.output_dir);
      setBatchConfig(finalConfig);
      await axios.post(`${API_BASE}/batch/${bookData.book_id}/start`, { ...voiceConfig, ...finalConfig });
      setStep(4);
    } catch (error) {
      alert('Lỗi khởi động tiến trình: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleReset = () => {
    setBookData(null);
    setStep(1);
  };

  const steps = [
    { num: 1, label: 'Upload EPUB', icon: Upload },
    { num: 2, label: 'Chọn Giọng', icon: Headphones },
    { num: 3, label: 'Cấu Hình', icon: Settings },
    { num: 4, label: 'Tiến Trình', icon: PlayCircle }
  ];

  return (
    <>
      <div className="stepper-container animate-slide-up" style={{ animationDelay: '0.1s' }}>
        <div className="stepper-line" />
        <div
          className="stepper-line-active"
          style={{ width: `calc(${(step - 1) / (steps.length - 1)} * 100% - 80px)` }}
        />
        {steps.map((s) => {
          const Icon = s.icon;
          const isActive = step === s.num;
          const isPast = step > s.num;
          let itemClass = 'step-item';
          if (isActive) itemClass += ' active';
          if (isPast) itemClass += ' past';
          return (
            <div key={s.num} className={itemClass} style={{ opacity: isActive || isPast ? 1 : 0.4 }}>
              <div className="step-icon-wrapper">
                <Icon size={20} />
              </div>
              <span style={{ fontWeight: isActive ? 600 : 400, fontSize: '0.9rem' }}>{s.label}</span>
            </div>
          );
        })}
      </div>

      <main style={{ perspective: '1000px' }}>
        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div key="step1" {...stepAnim}>
              <FileUploader onUploadSuccess={handleUploadSuccess} />
            </motion.div>
          )}
          {step === 2 && (
            <motion.div key="step2" {...stepAnim}>
              <VoiceSelector
                bookId={bookData?.book_id}
                bookName={bookData?.book_name}
                voiceConfig={voiceConfig}
                onChange={setVoiceConfig}
                onNext={() => setStep(3)}
                onBack={() => setStep(1)}
              />
            </motion.div>
          )}
          {step === 3 && (
            <motion.div key="step3" {...stepAnim}>
              <BatchConfig
                bookData={bookData}
                initialConfig={batchConfig}
                onStart={handleStartBatch}
                onBack={() => setStep(2)}
              />
            </motion.div>
          )}
          {step === 4 && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, scale: 0.8, z: -100 }}
              animate={{ opacity: 1, scale: 1, z: 0 }}
              exit={{ opacity: 0, scale: 1.2, z: 100 }}
              transition={{ duration: 0.7, type: 'spring', bounce: 0.4 }}
            >
              <ProgressDashboard bookId={bookData?.book_id} onReset={handleReset} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </>
  );
}
