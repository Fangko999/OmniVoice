# Hướng dẫn cho AI làm việc với dự án OmniVoice

- **Đọc `PROJECT_CONTEXT.md` trước khi làm bất cứ việc gì** – chứa kiến trúc, định dạng dữ liệu, quy tắc và các bẫy đã gặp.
- Trả lời người dùng bằng tiếng Việt, ngắn gọn. Comment code tiếng Việt. Commit message tiếng Việt không dấu.
- Giữ 3 vai `narrator/male/female` (không rõ → `male`); AI phải giữ nguyên chữ gốc; không bao giờ ghi đè chương `edited`.
- Backend chạy với cwd = `backend/`. Test: `cd backend; python -m pytest tests -q`. Frontend: `npm run lint`, `npm run build`.
- Không sửa file JSON bằng PowerShell (mojibake + BOM) – dùng Python. Không commit `backend/accounts.json`.
- Sau khi sửa lỗi/thêm tính năng quan trọng, cập nhật mục liên quan trong `PROJECT_CONTEXT.md`.
