# OmniVoice v3 — Tài liệu bối cảnh dự án

> **Dành cho người/AI mới mở dự án.** Đọc hết file này là đủ để hiểu và làm tiếp, không cần lịch sử chat cũ.
> Cập nhật lần cuối: 03/10/2026 (commit sau `63589bc`).

---

## 1. Dự án làm gì

Chuyển **truyện EPUB tiếng Việt → audiobook** (MP3/WAV, mỗi chương 1 file) bằng TTS **Kokoro-Vietnamese** chạy local (GPU nếu có).
Có tùy chọn dùng **AI Gemini (bản web, qua cookie)** làm "đạo diễn": phân vai, tốc độ, khoảng nghỉ cho từng câu.

Yêu cầu cốt lõi của chủ dự án (đừng phá vỡ):

- **Chỉ 3 vai/giọng:** `narrator` (dẫn truyện), `male` (thoại nam), `female` (thoại nữ). **Không rõ giới tính → `male`.** Không phân biệt tuổi (truyện tu tiên nhân vật già nhưng giọng trẻ).
- AI phải **giữ nguyên 100% chữ gốc** (chỉ được thêm/bớt dấu câu). Không bỏ, không tóm tắt, không lặp.
- Kịch bản AI tạo ra **lưu ra ổ đĩa** (JSON) để thu âm lúc nào cũng được, sửa tay được. **Chương đã sửa tay không bao giờ bị AI ghi đè.**
- Nhiều tài khoản Gemini **chạy luân phiên từng request** (không dùng cạn 1 tài khoản rồi mới đổi).
- Giao diện, thông báo, comment code: **tiếng Việt**. Commit message: tiếng Việt **không dấu**.

---

## 2. Ba tab trên giao diện

| Tab | Luồng | Job backend |
|---|---|---|
| **Đọc Nhanh** | Upload EPUB → chọn giọng dẫn/giọng thoại → cấu hình → audio. Tách thoại bằng **dấu ngoặc kép** (không AI). | `FastJob` (`core/batch_processor.py`) |
| **AI Đạo Diễn** | Upload EPUB → chọn phạm vi chương + thư mục lưu → Gemini phân vai → **thư mục kịch bản JSON**. Có trình sửa kịch bản. | `DirectorJob` (`core/director_job.py`) |
| **Thu Âm Kịch Bản** | Mở thư mục kịch bản bất kỳ → gán giọng Kokoro cho 3 vai → audio. | `RenderJob` (`core/render_job.py`) |

Nút "Thu âm ngay" ở tab AI Đạo Diễn chuyển thư mục kịch bản sang tab 3.

---

## 3. Cấu trúc thư mục

```
OmniVoice/
├─ Start_OmniVoice.bat        # Launcher: kiểm tra Python/npm/Kokoro/ffmpeg, cài thư viện thiếu, bật backend+frontend, mở trình duyệt
├─ README.md                  # Hướng dẫn ngắn
├─ PROJECT_CONTEXT.md         # (file này)
├─ AGENTS.md                  # Trỏ AI tới file này
├─ Kokoro-Vietnamese/         # REPO RIÊNG (gitignored) - TTS engine, import qua sys.path
├─ test_book.epub             # Sách thử (gitignored, *.epub) = "Cổ Chân Nhân Dịch Full", 3808 chương
├─ backend/                   # FastAPI - PHẢI chạy với cwd = backend/ (mọi đường dẫn tương đối tính từ đây)
│  ├─ main.py                 # App, CORS, đăng ký router, /api/utils/defaults, /api/utils/select_folder (hộp thoại Tk)
│  ├─ requirements.txt
│  ├─ accounts.json           # BÍ MẬT (gitignored): cookie Gemini. Mẫu: accounts.example.json
│  ├─ pre_generate_samples.py # Sinh file nghe thử giọng vào frontend/public/samples/
│  ├─ core/
│  │  ├─ job_base.py          # Khung job theo chương: state, log, vòng lặp, TTS_LOCK, render_chapter_audio, safe_dirname
│  │  ├─ batch_processor.py   # FastJob (Đọc Nhanh) + estimate_avg_chars, resolve_book_name, output_root
│  │  ├─ director_job.py      # DirectorJob (AI Đạo Diễn)
│  │  ├─ render_job.py        # RenderJob (Thu âm) + render_job_id(script_dir)
│  │  ├─ ai_director.py       # Prompt, parse, chống lặp, kiểm tra độ trung thành, chia khúc, fallback
│  │  ├─ account_pool.py      # Pool tài khoản Gemini luân phiên
│  │  ├─ script_store.py      # Đọc/ghi thư mục kịch bản (manifest + chuong_XXXX.json), is_edited
│  │  ├─ tts_engine.py        # Bọc Kokoro: cache model, chia câu quá dài, thử lại, báo đoạn lỗi
│  │  ├─ audio_encoder.py     # Ghi WAV (soundfile) / MP3 (pydub+ffmpeg), ghi nguyên tử qua file .part
│  │  ├─ epub_parser.py       # Đọc EPUB: TOC → spine → heading; lấy đoạn văn <p>
│  │  ├─ text_processor.py    # clean() bỏ chú thích; split_roles() tách theo ngoặc kép
│  │  └─ ws_hub.py            # WebSocket theo kênh + spawn() giữ tham chiếu task nền
│  ├─ routers/                # upload, preview, batch, director, render, scripts, accounts
│  ├─ models/schemas.py       # Pydantic: state, config, ChapterScript, ScriptManifest...
│  ├─ tests/                  # pytest: test_director.py, test_account_pool.py, test_core.py
│  ├─ uploads/                # (gitignored) EPUB đã upload, tên = <book_id>.epub (uuid4)
│  ├─ state/                  # (gitignored) trạng thái job + accounts_usage.json
│  └─ outputs/                # (gitignored) thư mục audio mặc định
└─ frontend/                  # React 19 + Vite 8, CSS thuần (index.css), framer-motion, lucide-react, axios
   ├─ vite.config.js          # proxy /api -> http://127.0.0.1:8000
   ├─ public/samples/*.wav    # file nghe thử 14 giọng
   └─ src/
      ├─ App.jsx              # 3 tab, KHÔNG unmount tab khi chuyển (giữ WebSocket)
      ├─ constants.js         # API_BASE='/api', WS_BASE (dev: ws://127.0.0.1:8000/api), VOICES, ROLES, store (localStorage 'ov:*'), errMsg
      ├─ tabs/                # FastModeTab, DirectorTab, RenderTab
      └─ components/          # FileUploader, VoiceSelector, BatchConfig, ProgressDashboard, ScriptEditor,
                              # RoleVoiceMapper, AccountPoolStatus, common (FolderInput, NumberField, Section, useDefaults)
```

---

## 4. Định dạng dữ liệu

### 4.1 Thư mục kịch bản (contract giữa tab 2 và tab 3)

```
<script_dir>/                     # mặc định: <thư mục gốc>\<Tên_truyện>_kichban
  manifest.json
  chuong_0001.json ... chuong_NNNN.json
  logs/director_YYYYMMDD_HHMMSS.log
```

`manifest.json`:
```json
{ "format": "omnivoice-script", "version": 1, "book_name": "...", "source_epub": "<đường dẫn tuyệt đối, chỉ để tham khảo>",
  "total_chapters": 3808,
  "chapters": { "1": { "title": "...", "status": "done", "fallback_chunks": 0, "edited": false } } }
```

`chuong_0001.json` (`ChapterScript`):
```json
{ "chapter": 1, "title": "...", "model": "gemini-flash", "created_at": "2026-10-03T14:00:00", "edited": false,
  "segments": [ { "voice": "narrator|male|female", "text": "...", "speed": 1.0, "pause_after": 0.4, "fallback": false } ] }
```
- `speed` khi lưu tay bị kẹp 0.5–2.0, `pause_after` 0–5 s. AI chỉ được tạo speed 0.8–1.3, pause 0.1–2.0.
- `fallback: true` = đoạn AI không xử lý được, dùng tách theo ngoặc kép → tab 3 cảnh báo "chương cần kiểm tra".
- `edited: true` = người dùng đã lưu qua trình sửa (PUT /api/scripts/chapter) → AI không ghi đè.
- File đọc bằng `utf-8-sig` (chịu được BOM nếu sửa bằng Notepad). Ghi nguyên tử (`.tmp` → `os.replace`).

### 4.2 Định dạng AI trả về (mỗi dòng một segment)
```
VAI|tốc độ|nghỉ|nội dung        ví dụ:  N|1.0|0.4|Hắn ngẩng đầu.   M|1.2|0.2|Ngươi là ai?   F|0.9|0.8|Ta...
```
Không dùng JSON (dấu ngoặc kép trong thoại làm JSON vỡ); vẫn đọc được JSON nếu AI lỡ trả.

### 4.3 `backend/accounts.json` (bí mật)
```json
{ "settings": { "min_delay": 1.0, "max_delay": 2.5, "exhausted_hours": 6, "cooldown_minutes": 10 },
  "accounts": [ { "name": "acc1", "secure_1psid": "...", "secure_1psidts": "...", "enabled": true, "daily_limit": null, "proxy": null } ] }
```
Lấy cookie `__Secure-1PSID` và `__Secure-1PSIDTS` từ gemini.google.com (DevTools → Application → Cookies). Settings khác có mặc định: `max_consecutive_errors=3`, `ip_block_minutes=[5,10,15]`, `init_timeout=60`.

### 4.4 `backend/state/`
- `<book_id>.fast.json`, `<book_id>.director.json`, `render_<md5(script_dir)[:12]>.render.json`: trạng thái job (status, completed_chapters, config, current_log, error_msg...). File cũ dạng `<book_id>.json` là state Đọc Nhanh kiểu cũ (vẫn đọc được).
- `accounts_usage.json`: số request/ngày, trạng thái, `until`, đuôi cookie của từng tài khoản.
- Status: `idle | waiting | running | paused | completed | error`. Server khởi động lại mà file ghi `running/waiting` → tự đổi thành `paused` ("Bị gián đoạn...").

### 4.5 Audio đầu ra
`<output_dir>\<tên truyện đã lọc ký tự cấm Windows>\chuong_0001.mp3` + `logs\<kind>_YYYYMMDD_HHMMSS.log`. Dữ liệu của chủ dự án đang ở `E:\TruyenAudio\` (kịch bản: `E:\TruyenAudio\Cổ_Chân_Nhân_Dịch_Full_kichban`).

---

## 5. Vòng đời job (`core/job_base.py`)

1. Router `POST .../start`: tạo job (parse EPUB trong thread), gán `state.config`, gọi `prepare()` để tính chương bỏ qua, đặt `status="running"` (chặn bấm Start 2 lần → 409), `spawn(job.run(callback))`.
2. `run()`: job dùng GPU (`uses_gpu=True`: Fast, Render) phải lấy `TTS_LOCK` → **chỉ 1 job Kokoro chạy cùng lúc**, job sau ở `waiting`. DirectorJob không dùng GPU nên chạy song song được.
3. `_run()`: mở file log, `setup()`, lặp chương trong `[start, end]`, bỏ qua `completed_chapters`, gọi `process_chapter(n)`. `JobStopped` → `paused`; lỗi khác → `error` (dừng cả job). Mỗi `_emit` lưu state + broadcast qua WebSocket. Kết thúc đóng file log.
4. Dừng: `POST .../stop` đặt cờ, job dừng **sau chương/khúc hiện tại**. "Tiếp tục chạy" trên UI = gửi lại `state.config` tới `/start`.

Logic bỏ qua chương khi chạy lại:
- **Đọc Nhanh:** chương đã có file `chuong_XXXX.<format>` trong thư mục lưu hiện tại.
- **AI Đạo Diễn:** chương đã có file kịch bản, trừ chương còn khúc fallback (chưa sửa tay) → làm lại. Bật "Chạy lại các chương đã có" → làm lại tất cả trừ chương `edited`. Trong `process_chapter` còn kiểm tra `is_edited` trước khi gọi AI và trước khi lưu (người dùng sửa giữa chừng).
- **Thu âm:** chương có audio **mới hơn** file kịch bản (sửa kịch bản → tự thu lại).

WebSocket: `/api/{batch|director|render}/{id}/ws` gửi state JSON đầy đủ mỗi lần cập nhật. Frontend `ProgressDashboard` tự kết nối lại sau 3 s, giữ tối đa 300 dòng log.

---

## 6. AI Đạo Diễn chi tiết (`core/ai_director.py`)

- Đoạn văn được `TextProcessor.clean()` (bỏ `(*...)`, `[Dịch:...]`, `[Chú...]`, `[TL:...]`, `(Tên cũ...)`, dấu `*`, chữ hoa đứng một mình → thường).
- Chia khúc ~**2500 ký tự** theo đoạn (`CHUNK_CHARS`), kèm **2 đoạn cuối khúc trước** làm ngữ cảnh (`CONTEXT_PARAS`), không đưa vào kết quả.
- Mỗi khúc: gọi pool → `parse_and_normalize` → `drop_repeats` → kiểm tra **fidelity ≥ 0.95**, **thừa ≤ 20 ký tự**, **thiếu ≤ 30 ký tự** (so sánh sau khi bỏ dấu câu/khoảng trắng, NFC, lowercase).
- Hỏng → thử lại tối đa **3 lần** → **chia đôi khúc** (tối đa 2 cấp, mỗi nửa 2 lần) → vẫn hỏng thì **fallback** `split_roles` (ngoặc kép, thoại → male) và đánh dấu `fallback`.
- **Lỗi "Gemini tua lại"** (đã sửa, commit `963fb02`): Gemini web đôi khi cắt dở một dòng, dính mã `M|0.9|0.4|` của dòng mới vào giữa, rồi phát lại vài dòng trước → audio đọc lặp câu. Xử lý: `_GLUED_RE` tách dòng dính, `drop_cut_heads` bỏ mảnh cắt dở nếu phía sau có dòng đầy đủ, `drop_repeats` (duyệt ngược) bỏ segment xuất hiện nhiều hơn số lần trong bản gốc / chép từ ngữ cảnh / trùng liền kề.
- **Prompt không được nhắc tới TTS/âm thanh/giọng đọc** — Gemini web hay từ chối ("tôi không tạo được âm thanh"). Prompt hiện nói rõ "tác vụ xử lý văn bản thuần túy".
- Model mặc định `gemini-flash` (tên model của thư viện `gemini_webapi`), request `temporary=True` (không lưu lịch sử chat).

### Pool tài khoản (`core/account_pool.py`)
- Round-robin **từng request**, giãn cách ngẫu nhiên 1–2.5 s giữa các request (toàn pool).
- `UsageLimitExceededError` → `exhausted` tới `quota_reset` (+30 s) nếu biết, không thì 6 giờ.
- Hạn mức đọc từ thuộc tính nội bộ `client._quotas` của gemini_webapi (`action_id == 11` = Gemini Flash), làm mới mỗi 10 request; `remaining <= 0` → bỏ qua tài khoản. Con số này có thể lệch với % hiển thị trên web.
- `AuthError` → `auth_failed` tới khi cookie trong accounts.json đổi (tự nhận khi reload).
- Lỗi chứa `UNAUTHENTICATED` → đóng client để lần sau đăng nhập lại từ cookie (thường do `__Secure-1PSIDTS` bị trình duyệt xoay vòng).
- Lỗi khác 3 lần liên tiếp → `cooldown` 10 phút. `TemporarilyBlockedError` (429 chặn IP) → **cả pool** nghỉ 5/10/15 phút.
- Không còn tài khoản nào và không ai sắp hồi → `AllAccountsExhausted` → job `paused` kèm lý do. `daily_limit` (tùy chọn) → hết lượt tới ngày mới.
- `pool.load()` đọc lại accounts.json mỗi lần Start job AI; UI có nút reload (`POST /api/accounts/reload`).

---

## 7. TTS (`core/tts_engine.py` + Kokoro-Vietnamese)

- Một model Kokoro cho mỗi device (cuda/cpu), mỗi giọng chỉ nạp thêm voicepack (`_BASE_ENGINES`, `_VOICE_ENGINES`). Lỗi CUDA → tự chuyển CPU.
- `synthesize_chapter` chạy song song 3 thread (`_EXECUTOR`), mỗi segment lỗi **thử lại 1 lần**, vẫn lỗi thì bỏ qua và **ghi WARNING vào log** (trước đây bị nuốt im lặng). Cả chương rỗng → lỗi.
- **Giới hạn Kokoro: một câu ≤ 510 âm vị (~370 ký tự tiếng Việt)**, quá là ném lỗi. `safe_pieces()` chia câu ≥ 300 ký tự có > 480 âm vị tại `, ; :` rồi theo từ, ghép lại có crossfade 50 ms.
- `patched_phonemize` sửa từ tiếng Việt không dấu bị đọc kiểu tiếng Anh (to, no, do, so, me, be, he, my, by).
- 14 giọng: my_yen, thanh_dat, diem_trinh, hung_thinh, mai_linh, mai_loan, manh_dung, ngoc_huyen, phat_tai, thuc_trinh, tuan_ngoc, duc_an, duc_duy, storyvert. Mặc định tab 3: narrator=my_yen, male=tuan_ngoc, female=ngoc_huyen.
- `tts_engine` chèn `<dự án>/Kokoro-Vietnamese/src` vào **đầu** `sys.path` → luôn dùng bản trong thư mục dự án (máy đang có bản `pip install -e` cũ trỏ tới `E:\New folder\Kokoro-Vietnamese` – thư mục này không còn, không sao).
- Model tải từ Hugging Face (`contextboxai/Kokoro-Vietnamese`, `hexgrad/Kokoro-82M`) vào cache người dùng (`~/.cache/huggingface`) – máy mới cần internet lần đầu.
- MP3 cần **ffmpeg** trong PATH (pydub). Python ≥ 3.13 cần `audioop-lts` (đã có trong requirements).

---

## 8. API (prefix `/api`)

| Method | Đường dẫn | Ghi chú |
|---|---|---|
| POST | `/upload/upload` | multipart `file` (.epub, không phân biệt hoa thường) → `{book_id, book_name, total_chapters, avg_chars_per_chapter}` |
| POST | `/preview/preview` | `{voice_id, text, speed}` → WAV |
| POST | `/preview/preview_chapter` | `{book_id, narrator_voice, dialogue_voice?, reading_mode, speed}` → WAV 5 đoạn đầu chương 1 |
| POST | `/batch/{book_id}/start` | `BatchConfigRequest` → `{skipped}`; `/stop`, `GET /state`, `WS /ws` |
| POST | `/director/start` | `DirectorConfigRequest {book_id, script_dir, start_chapter, end_chapter, model, overwrite}`; `/{book_id}/stop`, `/state`, `/ws` |
| POST | `/render/start` | `RenderConfigRequest {script_dir, voice_map, start_chapter, end_chapter, global_speed, gap_seconds, format, output_dir}` → `{job_id, skipped}`; `/{job_id}/stop`, `/state`, `/ws`; `GET /render/job_id?script_dir=` |
| POST | `/scripts/open` | `{script_dir}` → `{script_dir, manifest, available_chapters}` |
| GET/PUT | `/scripts/chapter?dir=&n=` | đọc / lưu chương (PUT đánh dấu `edited`) |
| GET/POST | `/accounts`, `/accounts/reload` | trạng thái pool |
| GET | `/utils/defaults`, `/utils/select_folder` | thư mục mặc định; hộp thoại chọn thư mục (Tkinter, chạy trên máy server) |

---

## 9. Frontend – điểm cần biết

- `store` = localStorage khóa `ov:<key>`: `tab`, `voice_map`, `output_dir`, `script_root`, `recent_scripts`, `render_speed/gap/format`, và **job đang theo dõi** `fast_job`, `director_job`, `render_job` (F5 vẫn quay lại màn hình tiến trình; bấm "Truyện khác/Kịch bản khác" thì xóa).
- Ước tính thời gian (ETA) lưu tốc độ ở localStorage `ai_sec_per_char`, `director_sec_per_char`, `render_sec_per_char`.
- `ScriptEditor`: sửa text/vai/tốc độ/nghỉ, tách (theo con trỏ)/gộp/chèn/xóa, đổi vai hàng loạt, nghe thử từng segment, lọc "Cần kiểm tra", Ctrl+S lưu, cảnh báo khi rời trang chưa lưu.
- Kiểm tra: `cd frontend; npm run lint` (oxlint – hiện còn ~23 cảnh báo phong cách, 0 lỗi) và `npm run build`.

---

## 10. Cài đặt, chạy, test

```powershell
# Lần đầu (máy mới)
#  - Python 3.10+ (đang dùng 3.12), Node.js 18+, ffmpeg trong PATH
git clone https://github.com/iamdinhthuan/Kokoro-Vietnamese Kokoro-Vietnamese   # nếu chưa có thư mục này
python -m pip install -e Kokoro-Vietnamese        # cài torch/transformers/vig2p... của Kokoro
python -m pip install -r backend\requirements.txt
cd frontend; npm install; cd ..
copy backend\accounts.example.json backend\accounts.json   # rồi điền cookie

# Chạy hằng ngày
Start_OmniVoice.bat            # backend :8000 + frontend :5173 + mở trình duyệt

# Chạy tay
cd backend;  python -m uvicorn main:app --host 127.0.0.1 --port 8000
cd frontend; npm run dev -- --port 5173 --strictPort

# Test backend (31 test, không cần GPU/Gemini)
cd backend;  python -m pytest tests -q
```
Sửa code backend → **phải khởi động lại backend** (không chạy `--reload`).

---

## 11. Chuyển dự án sang thư mục/máy khác

Copy **cả thư mục `OmniVoice`** (gồm cả các thư mục bị gitignore nếu muốn giữ dữ liệu):
- `Kokoro-Vietnamese/` (bắt buộc), `backend/accounts.json` (cookie), `backend/uploads/` (EPUB đã upload – cần cho tab AI Đạo Diễn/Đọc Nhanh tiếp tục sách cũ), `backend/state/` (tiến độ job, usage tài khoản), `frontend/node_modules/` (hoặc `npm install` lại).
- Không có đường dẫn tuyệt đối nào gắn với vị trí dự án trong code. Đường dẫn tuyệt đối chỉ nằm trong **dữ liệu**: `script_dir`/`output_dir` trong state (trỏ tới `E:\TruyenAudio\...` – vẫn đúng nếu ổ E còn), `manifest.source_epub` (chỉ tham khảo).
- `render_job_id` = md5 của đường dẫn kịch bản → đổi chỗ thư mục kịch bản thì job thu âm mới (vẫn bỏ qua chương đã có audio vì dựa vào file).
- localStorage của trình duyệt gắn với `http://localhost:5173`, không phụ thuộc thư mục.
- Máy mới: cài lại Python libs + Kokoro deps, ffmpeg, Node; lần đầu tải model Kokoro từ Hugging Face.

---

## 12. Lưu ý / bẫy đã gặp

- **Không sửa JSON bằng PowerShell** (`Get-Content | ConvertFrom-Json | ConvertTo-Json | Set-Content`): PowerShell 5 đọc sai UTF-8 → chữ Việt thành mojibake và thêm BOM. Dùng Python (`json.load`/`json.dump(ensure_ascii=False)`) hoặc trình sửa trên UI.
- Chạy script Python in tiếng Việt trên console Windows: đặt `$env:PYTHONIOENCODING='utf-8'`.
- EPUB "Cổ Chân Nhân" **tự nó có 6 cặp chương trùng nội dung** (1566/1567, 1629/1630, 1658/1659, 1823/1824, 2598/2599, 3048/3049) – không phải lỗi code.
- EPUB có thể chứa số chú thích dính vào chữ; AI hay bỏ các số đó → "thiếu vài ký tự" là bình thường (giới hạn 30).
- Gemini web: cookie `__Secure-1PSIDTS` bị xoay khi mở cùng tài khoản trên trình duyệt → lỗi UNAUTHENTICATED; pool tự đăng nhập lại, nếu vẫn lỗi thì lấy cookie mới và bấm reload tài khoản.
- `gemini_webapi` (bản 2.1.1) là thư viện không chính thức: thuộc tính `_quotas`, `_fetch_quota` là nội bộ, có thể đổi khi nâng cấp.
- Mọi đường dẫn tương đối (`uploads/`, `state/`, `outputs/`, `accounts.json`) tính từ **cwd = backend/**. Chạy uvicorn ở thư mục khác sẽ tạo dữ liệu sai chỗ.
- Thư viện có `print` tiếng Việt; log job ghi file UTF-8 trong `<thư mục lưu>/logs/`.

---

## 13. Lịch sử sửa lỗi chính (để không làm lại)

- `963fb02` – Chống lặp câu do Gemini "tua lại" (xem mục 6). Các chương 1, 2, 3, 5, 6, 9 của kịch bản Cổ Chân Nhân đã được sửa tay bằng script (bản sao lưu: `<script_dir>\_backup_truoc_khi_sua_lap\`, `chuong_0001.json.corrupt.bak`) → cần **thu âm lại** các chương này (tab 3 tự nhận vì kịch bản mới hơn audio).
- `63589bc` + commit sau – Rà soát lỗi tiềm ẩn:
  - TTS: chia câu > 510 âm vị (trước đây bị bỏ im lặng → mất câu), thử lại + ghi log đoạn lỗi; ghi audio nguyên tử (tắt máy giữa chừng không để lại file hỏng mà tab 3 tưởng đã xong).
  - State: đọc BOM, file hỏng → tạo mới, `running` cũ → `paused`; đóng file log khi job xong.
  - Tên thư mục truyện lọc ký tự cấm Windows (`: ? * " < > |`).
  - AI không ghi đè chương vừa sửa tay trong lúc job đang chạy.
  - Preview/upload/khởi tạo job chạy trong thread (không treo server/WebSocket); chống bấm Start 2 lần; giữ đúng mã lỗi 404/400.
  - EPUB: không dính chữ khi đoạn có thẻ inline (`Hắn <i>nói</i>`), tìm file theo href mã hóa URL/khác thư mục.
  - Đọc Nhanh bỏ qua chương theo file audio thật (đổi thư mục/định dạng thì làm lại).
  - Frontend: nhớ job đang chạy khi F5, giới hạn 300 dòng log, cho quay lại khi job lỗi/tạm dừng, nhận `.EPUB` viết hoa.
  - requirements: bỏ thư viện không dùng (google-api-*, requests, aiofiles), thêm `audioop-lts` cho Python 3.13+.
  - Kokoro import ưu tiên bản trong thư mục dự án.

### Việc có thể làm tiếp (chưa làm)
- Dọn ~23 cảnh báo oxlint (chủ yếu `set-state-in-effect`), chưa ảnh hưởng chạy.
- `format` trong config đang là `str` tự do (UI chỉ gửi `mp3`/`wav`).
- Ctrl+S của ScriptEditor bắt phím toàn cửa sổ (nếu mở trình sửa ở cả 2 tab cùng lúc thì cả hai cùng lưu).
