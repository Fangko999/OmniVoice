# OmniVoice v3

Chuyển truyện EPUB thành audio tiếng Việt bằng Kokoro TTS, có tùy chọn AI (Gemini) phân vai và đạo diễn âm thanh.

## 3 tab

| Tab | Chức năng |
|---|---|
| **Đọc Nhanh** | EPUB → audio ngay, tách dẫn truyện / thoại bằng quy tắc (không cần AI). |
| **AI Đạo Diễn** | EPUB → thư mục kịch bản JSON (vai: dẫn truyện / nam / nữ, tốc độ, khoảng nghỉ). Lưu ra ổ đĩa, sửa được mọi thứ. |
| **Thu Âm Kịch Bản** | Mở thư mục kịch bản → gán giọng cho 3 vai → xuất MP3/WAV. |

## Cài đặt

1. Python 3.10+, Node.js 18+, ffmpeg (trong PATH, để xuất MP3).
2. Kokoro-Vietnamese (repo riêng, không nằm trong repo này):
   ```
   git clone https://github.com/iamdinhthuan/Kokoro-Vietnamese
   pip install -e Kokoro-Vietnamese
   ```
3. Tài khoản Gemini (chỉ cần cho tab AI Đạo Diễn): copy `backend/accounts.example.json` → `backend/accounts.json`, điền cookie `__Secure-1PSID` / `__Secure-1PSIDTS`. Nhiều tài khoản sẽ chạy luân phiên. **Không commit file này.**
4. Chạy `Start_OmniVoice.bat` — tự cài thư viện còn thiếu, bật backend (:8000), frontend (:5173) và mở trình duyệt.

## Test

```
cd backend
python -m pytest tests -q
```
