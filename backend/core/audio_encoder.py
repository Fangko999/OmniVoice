import os
import soundfile as sf
import numpy as np
from pydub import AudioSegment


def _part_path(path: str) -> str:
    root, ext = os.path.splitext(path)
    return f"{root}.part{ext}"


def _atomic(path: str, write):
    """Ghi ra file tạm rồi đổi tên: tắt máy/crash giữa chừng không để lại file hỏng mà
    Thu âm lại tưởng là đã xong (nó bỏ qua chương có audio mới hơn kịch bản)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = _part_path(path)
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class AudioEncoder:
    @staticmethod
    def save_wav(audio: np.ndarray, path: str, sample_rate: int = 24000):
        # Prevent clipping/wrapping artifacts
        audio = np.clip(audio, -1.0, 1.0)
        _atomic(path, lambda p: sf.write(p, audio, sample_rate, format="WAV"))

    @staticmethod
    def save_mp3(audio: np.ndarray, path: str, sample_rate: int = 24000, bitrate: str = "192k"):
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

        _atomic(path, lambda p: segment.export(p, format="mp3", bitrate=bitrate))
