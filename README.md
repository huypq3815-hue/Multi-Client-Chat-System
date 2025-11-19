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


