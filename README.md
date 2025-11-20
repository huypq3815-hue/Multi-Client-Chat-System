#  HỆ THỐNG CHAT ĐA NỀN TẢNG (MULTI-CLIENT CHAT SYSTEM)

## Giới thiệu dự án
Đây là **đồ án cuối kỳ môn Lập trình mạng** – xây dựng một hệ thống chat client–server cho phép nhiều người dùng giao tiếp **thời gian thực**, có khả năng **bảo mật kết nối**, **chat nhóm**, **chat riêng tư**, và **lưu lịch sử trò chuyện**.

Dự án được phát triển bằng **Python**, sử dụng **socket TCP/SSL**, **đa luồng (multi-threading)**, và **Tkinter** cho giao diện người dùng.

---

## Tính năng chính
Chat nhóm thời gian thực (broadcast)  
Chat riêng tư giữa hai người  
Lưu lịch sử chat bằng SQLite  
Thông báo khi người dùng tham gia/rời khỏi phòng  
Kết nối bảo mật với SSL/TLS  
Gửi file đính kèm qua TCP/SSL   
Chat qua WebSocket (phiên bản mở rộng)  
API gRPC để lấy danh sách người dùng / lịch sử chat 

---

## Kiến trúc hệ thống
multi_chat/
├── server/
│ ├── server.py # Server TCP/SSL, quản lý client và broadcast
│ ├── certs/ # Chứa chứng chỉ SSL (cert.pem, key.pem)
│ └── chat_history.db # CSDL lưu lịch sử chat (SQLite)
│
├── client/
```markdown
# HỆ THỐNG CHAT ĐA NỀN TẢNG (Multi-Client Chat System)

Phiên bản chứa một server WebSocket viết bằng Python và một client web tĩnh. Mục tiêu: demo chat nhóm, chat riêng, gửi file theo chunk, lưu lịch sử, và tùy chọn kích hoạt WSS khi có `cert.pem`/`key.pem`.

--

## Tính năng chính
- Chat nhóm (broadcast)
- Chat riêng tư giữa hai người (nhập `@username message`)
- Gửi file theo chunk (assembled on server)
- Hiển thị danh sách người đang online + typing indicator
- Lưu lịch sử (file JSON) và giới hạn lịch sử
- Hỗ trợ WSS nếu cung cấp `cert.pem` / `key.pem`

--

## Yêu cầu
- Python 3.8+
- Một virtualenv khuyến nghị (tự động kích hoạt nếu `.venv` tồn tại)
- Packages: `websockets`, `cryptography` (nếu bạn tạo certs)

Ví dụ cài nhanh:

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install websockets cryptography
```

--

## Cấu trúc chính (tóm tắt)
- `index.html`, `style.css`, `ws_client.js` — client web tĩnh
- `server/ws_server.py` — WebSocket server (entry)
- `server/history_manager.py` — quản lý lịch sử (in-memory + persist JSON)
- `server/file_transfer.py` — ghép chunk upload tạm thời
- `create_cert.py` — tạo `cert.pem`/`key.pem` (tùy chọn)

--

## Chạy nhanh (Quick Start)

Lưu ý: các lệnh dưới giả định bạn đang ở thư mục dự án `Multi-Client-Chat-System`.

1) Kích hoạt virtualenv (nếu dùng):

```powershell
cd "C:\path\to\Multi-Client-Chat-System"
. .venv\Scripts\Activate.ps1
```

2) Khởi server WebSocket (2 cách):

- Chạy trực tiếp:

```powershell
python .\server\ws_server.py
```

- Hoặc chạy như module (khuyến nghị khi chạy trong project root):

```powershell
python -m server.ws_server
```

3) Serve client (từ thư mục dự án) và mở trang web:

```powershell
python -m http.server 8000 --directory .
# Mở: http://localhost:8000/index.html
```






