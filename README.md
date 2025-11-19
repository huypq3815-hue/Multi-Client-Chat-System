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
│ └── client_tk.py # Giao diện chat bằng Tkinter
│
├── grpc/
│ ├── proto/
│ │ └── chat.proto # Định nghĩa gRPC service
│ └── grpc_server.py # Server gRPC để query danh sách user/lịch sử
│
├── websocket_gateway/
│ └── ws_gateway.py # Gateway WebSocket (cho client web)
│
├── requirements.txt
├── .gitignore
└── README.md



---

##  Công nghệ sử dụng
| Thành phần      | Công nghệ               | Mục đích |
|-----------------|------------             |----------|
| Giao tiếp mạng  | **TCP Socket, SSL/TLS** | Truyền dữ liệu thời gian thực và bảo mật |
| Xử lý song song | **Threading**           | Mỗi client là một luồng độc lập |
| CSDL            | **SQLite3**             | Lưu lịch sử trò chuyện |
| Giao diện       | **Tkinter (Python GUI)**| Chat nhóm, chat riêng |
| API mở rộng     | **gRPC**                | Lấy danh sách người dùng và lịch sử |
| Chat qua web    | **WebSocket (aiohttp)** | Cho phép chat bằng trình duyệt |

---

## Hướng dẫn chạy (Demo nhanh trên Windows / PowerShell)

Các bước dưới đây giả định bạn đang ở thư mục dự án `Multi-Client-Chat-System`.

1) Chuẩn bị môi trường (một lần):

```powershell
# chuyển vào thư mục dự án
cd "..."

# (tùy chọn) tạo virtualenv và kích hoạt
python -m venv .venv
. .venv\Scripts\Activate.ps1

# cài dependencies cơ bản
python -m pip install --upgrade pip
python -m pip install websockets
```

2) Chạy WebSocket server (server Python sẽ lắng nghe trên `ws://0.0.0.0:6789`):

```powershell
python .\ws_server.py
# Dùng Ctrl+C để dừng server
```

3) Mở client web (trình duyệt):

Bạn cần serve `index.html` từ thư mục chứa file — không chạy `http.server` từ thư mục khác (sẽ báo 404).

```powershell
# Từ cùng thư mục dự án
python -m http.server 8000 --directory .
# Mở trình duyệt tới: http://localhost:8000/index.html
```

4) Dùng giao diện web:

- Nhập `username` rồi bấm `Join Chat`.
- Dùng nút đính kèm (📎) để chọn file, file sẽ được gửi theo chunk và sau khi server lắp lại sẽ hiển thị như một tin nhắn có link tải xuống.

5) Kiểm tra log & debug:

- File log nằm ở `chat.log` trong cùng thư mục; để xem realtime dùng PowerShell:

```powershell
Get-Content .\chat.log -Wait -Tail 200
```

- Nếu upload không thành công, kiểm tra:
	- Kiểm tra console của trình duyệt (F12) để xem WebSocket errors.
	- Đảm bảo server Python (ws_server.py) đang chạy và không báo lỗi.
	- Kiểm tra giới hạn kích thước file: hiện tại tối đa là 3MB (hạn chế trong `ws_server.py` -> `MAX_FILE_SIZE`).

6) Chạy server ở background (tùy chọn):

```powershell
Start-Process -FilePath python -ArgumentList '.\ws_server.py' -PassThru | ForEach-Object { $_.Id } > server_pid.txt
# Dừng bằng Stop-Process -Id <PID>
```

7) Dọn dẹp: tôi đã xóa các script tạm (`test_client.py`, `repro_clients.py`, `server/ft_test.py`) khỏi repo.

Nếu bạn gặp lỗi cụ thể khi gửi file (ví dụ toast báo "Upload queued" nhưng file không xuất hiện ở chat), hãy gửi cho tôi:
- Đoạn log `chat.log` tại thời điểm upload;
- Console log của trình duyệt (F12) — đặc biệt WebSocket close code/reason;
- Tên file và kích thước bạn thử gửi.

---

Cần bổ sung phần hướng dẫn khác hoặc muốn tôi tạo script khởi động nhanh (`run.bat` / `start.ps1`)?



