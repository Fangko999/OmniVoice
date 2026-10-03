import os
import soundfile as sf
from core.tts_engine import TTSEngine
from core.audio_encoder import AudioEncoder

VOICES = [
    'my_yen', 'thanh_dat', 'diem_trinh', 'hung_thinh',
    'mai_linh', 'mai_loan', 'manh_dung', 'ngoc_huyen',
    'phat_tai', 'thuc_trinh', 'tuan_ngoc', 'duc_an',
    'duc_duy', 'storyvert'
]

TEXT = "Xin chào, đây là giọng đọc thử từ hệ thống Omni Voice."

def generate():
    out_dir = "../frontend/public/samples"
    os.makedirs(out_dir, exist_ok=True)
    
    engine = TTSEngine(device="cpu")
    
    for voice in VOICES:
        out_path = os.path.join(out_dir, f"{voice}.wav")
        if not os.path.exists(out_path):
            print(f"Generating {voice}...")
            segment = {"voice": voice, "text": TEXT, "speed": 1.0}
            audio = engine.synthesize_segment(segment)
            if len(audio) > 0:
                AudioEncoder.save_wav(audio, out_path)
                print(f"  -> Saved {out_path}")

if __name__ == "__main__":
    generate()
