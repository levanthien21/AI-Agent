# AI Agent trả lời tin nhắn tự động theo lĩnh vực

Mỗi **lĩnh vực** (cửa hàng thời trang, phòng khám, bất động sản...) có kho kiến thức, vai trò và lời chào riêng. Bạn nạp Excel/CSV/TXT, agent chỉ trả lời dựa trên kiến thức đó (RAG, dùng Google Gemini), không bịa.

## Chạy

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # rồi điền GEMINI_API_KEY và ADMIN_KEY
uvicorn app.main:app --reload
```

- Trang quản trị: http://localhost:8000/admin (nhập `ADMIN_KEY` để đăng nhập)
- Trang demo widget: http://localhost:8000/demo?domain=ten-linh-vuc

## Cách dùng

1. Vào `/admin` → tạo lĩnh vực → chỉnh persona, lời chào, câu trả lời dự phòng.
2. Tải file lên (thử với `samples/faq_cua_hang.csv`) hoặc gõ trực tiếp.
3. Thử chat ngay trong trang quản trị.
4. Nhúng vào website:
   ```html
   <script src="http://SERVER/static/widget.js" data-domain="ten-linh-vuc"></script>
   ```

## Định dạng file

- **Excel/CSV**: dòng đầu là tên cột; mỗi dòng thành một mẩu kiến thức (`Câu hỏi | Trả lời`, hoặc `Sản phẩm | Giá | Tồn kho | Mô tả`...). Excel nhiều sheet được hỗ trợ.
- **TXT/MD**: tách theo đoạn (cách nhau dòng trống).
- Nạp lại file cùng tên sẽ thay thế bản cũ.

## API

| Method | Đường dẫn | Ghi chú |
|---|---|---|
| POST | `/api/chat` | `{domain, session_id, message}` → `{answer, sources}` (công khai) |
| GET/POST | `/api/domains` | cần header `X-Admin-Key` |
| PUT/DELETE | `/api/domains/{name}` | |
| POST | `/api/domains/{name}/upload` | multipart `file` |
| POST | `/api/domains/{name}/text` | `{source, text}` |

Endpoint `/api/chat` là điểm tích hợp để sau này nối Zalo OA, Messenger, Telegram (webhook gọi `agent.reply(domain, session_id, message)`).

## Cấu trúc

- `app/agent.py` – truy xuất + sinh câu trả lời, nhớ hội thoại theo phiên
- `app/store.py` – kho kiến thức từng lĩnh vực (`data/domains/<tên>/`)
- `app/ingest.py` – đọc Excel/CSV/TXT thành các đoạn và tạo embedding
- `app/main.py` – API FastAPI · `static/` – trang admin và widget

## Lưu ý khi triển khai thật

- Đặt `ADMIN_KEY` mạnh, dùng HTTPS, và đặt `ALLOWED_ORIGINS` đúng website của bạn.
- Lịch sử hội thoại lưu trong RAM (mất khi khởi động lại); chạy 1 worker. Quy mô lớn thì chuyển sang Redis/DB và vector DB.
