import os
import soundfile as sf
import numpy as np
from pydub import AudioSegment

class AudioEncoder:
    @staticmethod
    def save_wav(audio: np.ndarray, path: str, sample_rate: int = 24000):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Prevent clipping/wrapping artifacts
        audio = np.clip(audio, -1.0, 1.0)
        sf.write(path, audio, sample_rate)
    
    @staticmethod
    def save_mp3(audio: np.ndarray, path: str, sample_rate: int = 24000, bitrate: str = "192k"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Prevent clipping/wrapping artifacts
        audio = np.clip(audio, -1.0, 1.0)
        
        # pydub works with int16 PCM data
        if audio.dtype != np.int16:
            # Scale to 16-bit integer range
            audio_int16 = np.int16(audio * 32767)
        else:
            audio_int16 = audio
            
        segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=audio_int16.dtype.itemsize,
            channels=1
        )
        
        segment.export(path, format="mp3", bitrate=bitrate)
