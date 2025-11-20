#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_server.py — ChatSphere WebSocket Server (multi-tab & multi-user safe, SSL ready)
"""

import asyncio
import websockets
import json
import re
import base64
import os
import ssl as ssl_module
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from collections import defaultdict, deque
import traceback

# server modules (you must have these in server/ package)
from server.history_manager import get_default as get_history_manager
from server.file_transfer import add_chunk as ft_add_chunk, cleanup_expired

# ================= CONFIG =================
HOST = "0.0.0.0"
PORT = 6789

MAX_HISTORY = 500
MAX_USERNAME_LEN = 24
MAX_MESSAGE_LEN = 4000
MAX_FILE_SIZE = 3 * 1024 * 1024  # 3MB
RATE_LIMIT_MESSAGES = 6
RATE_LIMIT_SECONDS = 2
LOG_FILE = "chat.log"

ADMINS = {"admin", "mod"}
ADMINS_LOWER = {a.lower() for a in ADMINS}

# Monotonic message sequence id (keeps ids simple and efficient)
MESSAGE_SEQ = 0

# ================= LOGGING =================
logger = logging.getLogger("ChatSphere")
logger.setLevel(logging.INFO)

console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', '%H:%M:%S'))

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))

logger.addHandler(console)
logger.addHandler(file_handler)

# ================= STATE =================
USERS = defaultdict(set)       # username -> set of websockets (multi-session)
USER_ROLES = {}
TYPING = set()
HIST = get_history_manager()
REACTIONS = defaultdict(lambda: defaultdict(int))
RATE_QUEUE = defaultdict(lambda: deque())

# ================= UTILITIES =================
def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def generate_id():
    global MESSAGE_SEQ
    MESSAGE_SEQ += 1
    return f"msg_{MESSAGE_SEQ:06d}"

def is_valid_username(name: str) -> bool:
    return bool(name and len(name) <= MAX_USERNAME_LEN and re.match(r'^[a-zA-Z0-9_\-\.]+$', name))

def is_admin(username: str) -> bool:
    if not username:
        return False
    return username.lower() in ADMINS_LOWER

def load_history():
    try:
        HIST.load()
        logger.info(f"Đã tải {len(HIST.all())} tin nhắn từ lịch sử")
    except Exception as e:
        logger.error(f"Lỗi tải lịch sử: {e}")
        logger.debug(traceback.format_exc())

def save_history():
    try:
        HIST.save()
        logger.info("Đã lưu lịch sử")
    except Exception as e:
        logger.error(f"Lỗi lưu lịch sử: {e}")
        logger.debug(traceback.format_exc())

def add_to_history(msg: dict):
    msg["id"] = generate_id()
    msg["time"] = now_iso()
    HIST.add(msg)
    if len(HIST.all()) > MAX_HISTORY:
        old = HIST.all()[0]
        REACTIONS.pop(old.get("id"), None)

def rate_limited(username: str) -> bool:
    now = asyncio.get_event_loop().time()
    q = RATE_QUEUE[username]
    while q and q[0] <= now - RATE_LIMIT_SECONDS:
        q.popleft()
    if len(q) >= RATE_LIMIT_MESSAGES:
        return True
    q.append(now)
    return False

# ================= BROADCAST =================
async def broadcast(obj: dict, exclude: set = None):
    if not USERS:
        return

    payload = json.dumps(obj, ensure_ascii=False)
    tasks = []

    for username, sessions in list(USERS.items()):
        if exclude and username in exclude:
            continue
        for ws in list(sessions):
            try:
                tasks.append(ws.send(payload))
            except Exception:
                sessions.discard(ws)
        if not sessions:
            USERS.pop(username, None)

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # disconnected websockets already removed above

async def send_user_list():
    await broadcast({"type": "user_list", "users": sorted(USERS.keys())})

async def system_message(text: str):
    msg = {"type": "system", "text": text, "time": now_iso()}
    add_to_history(msg)
    await broadcast(msg)

# ================= HANDLERS =================
async def handle_login(ws, data: dict):
    name = (data.get("username") or "").strip()
    if not is_valid_username(name):
        await ws.send(json.dumps({"type": "error", "text": "Tên chỉ được dùng a-z, 0-9, _, -, ."}, ensure_ascii=False))
        await ws.close(1008)
        return None

    USERS[name].add(ws)
    USER_ROLES[name] = {"admin"} if is_admin(name) else set()
    logger.info(f"{name} tham gia → tổng session: {sum(len(s) for s in USERS.values())}")

    for msg in HIST.recent(100):
        try:
            await ws.send(json.dumps(msg, ensure_ascii=False))
        except Exception:
            pass

    await system_message(f"{name} đã tham gia phòng chat")
    await send_user_list()
    return name

async def handle_group(ws, data: dict, username: str):
    if rate_limited(username): return

    text = (data.get("text") or "").strip()
    file = data.get("file")

    if not text and not file: return
    if text and len(text) > MAX_MESSAGE_LEN:
        await ws.send(json.dumps({"type": "error", "text": f"Tin quá dài (> {MAX_MESSAGE_LEN} ký tự)"}, ensure_ascii=False))
        return

    msg = {"type": "group", "from": username, "text": text or ""}

    if file:
        try:
            raw = base64.b64decode(file["data"])
            if len(raw) > MAX_FILE_SIZE:
                await ws.send(json.dumps({"type": "error", "text": "File quá lớn (>3MB)"}, ensure_ascii=False))
                return
            msg["file"] = {
                "name": file["name"][:100],
                "type": file["type"],
                "size": len(raw),
                "data": file["data"]
            }
        except Exception:
            logger.debug("Invalid file payload")
            return

    add_to_history(msg)
    await broadcast(msg)

async def handle_private(ws, data: dict, username: str):
    if rate_limited(username): return
    to = data.get("to")
    text = (data.get("text") or "").strip()
    if not (to and text): return

    if to not in USERS:
        await ws.send(json.dumps({"type": "system", "text": f"Người dùng {to} đang offline"}, ensure_ascii=False))
        return

    msg = {"type": "private", "from": username, "to": to, "text": text, "time": now_iso()}
    add_to_history(msg)
    for ws_to in list(USERS[to]):
        try:
            await ws_to.send(json.dumps(msg, ensure_ascii=False))
        except Exception:
            USERS[to].discard(ws_to)
    await ws.send(json.dumps(msg, ensure_ascii=False))

async def handle_typing(data: dict, username: str):
    is_typing = bool(data.get("isTyping"))
    if is_typing:
        TYPING.add(username)
    else:
        TYPING.discard(username)
    await broadcast({"type": "typing", "from": username, "isTyping": is_typing}, exclude={username})

async def handle_file_chunk(ws, data: dict, username: str):
    upload_id = data.get('upload_id')
    try:
        index = int(data.get('index', 0))
        total = int(data.get('total', 0))
    except Exception:
        return
    b64 = data.get('data')
    # client uses `file_type` to avoid clobbering the top-level `type` field
    meta = {'name': data.get('name', ''), 'type': data.get('file_type', '') or data.get('type', ''), 'size': data.get('size', 0)}
    if not (upload_id and b64 and total > 0):
        return

    try:
        logger.info("Receiving file chunk %s/%s upload_id=%s from=%s", index+1, total, upload_id, username)
        raw, meta_ret = ft_add_chunk(upload_id, index, total, b64, meta)
    except Exception as e:
        logger.error(f"Error in ft_add_chunk for upload_id={upload_id}: {e}")
        logger.debug(traceback.format_exc())
        try:
            await ws.send(json.dumps({"type": "file_error", "upload_id": upload_id, "text": "Server error processing chunk"}, ensure_ascii=False))
        except Exception:
            pass
        return

    cleanup_expired()

    # send a per-chunk ack to uploader so client can show progress
    try:
        await ws.send(json.dumps({"type": "file_ack", "upload_id": upload_id, "index": index, "total": total}, ensure_ascii=False))
    except Exception:
        pass

    if raw is not None:
        if not meta_ret:
            meta_ret = meta or {}
        logger.info(f"File assembled upload_id={upload_id} name={meta_ret.get('name','')} size={len(raw)} from={username}")
        if len(raw) > MAX_FILE_SIZE:
            await ws.send(json.dumps({"type": "error", "text": "File quá lớn (>3MB)"}, ensure_ascii=False))
            return
        b64_full = base64.b64encode(raw).decode('ascii')
        msg = {
            "type": "group",
            "from": username,
            "text": "",
            "file": {
                "name": meta_ret.get('name','')[:100],
                "type": meta_ret.get('type',''),
                "size": len(raw),
                "data": b64_full
            }
        }
        add_to_history(msg)
        # notify uploader that file is complete (and size)
        try:
            await ws.send(json.dumps({"type": "file_complete", "upload_id": upload_id, "name": meta_ret.get('name',''), "size": len(raw)}, ensure_ascii=False))
        except Exception:
            pass
        try:
            await broadcast(msg)
        except Exception as e:
            logger.error(f"Error broadcasting assembled file upload_id={upload_id}: {e}")
            logger.debug(traceback.format_exc())

async def handle_reaction(data: dict, username: str):
    msg_id = data.get("id")
    emoji = (data.get("emoji") or "")[:4]
    if not (msg_id and emoji): return
    REACTIONS[msg_id][emoji] += 1
    await broadcast({
        "type": "reaction",
        "id": msg_id,
        "emoji": emoji,
        "count": REACTIONS[msg_id][emoji],
        "from": username
    })

async def handle_admin_command(ws, text: str, username: str):
    if text == "/users":
        await ws.send(json.dumps({"type": "system", "text": f"Online: {', '.join(sorted(USERS.keys()))}"}, ensure_ascii=False))
    elif text.startswith("/kick ") and is_admin(username):
        target = text[6:].strip()
        if target in USERS and not is_admin(target):
            for ws_target in list(USERS[target]):
                await ws_target.close(4000, "Bị kick")
            await system_message(f"{target} đã bị kick bởi {username}")
    elif text.startswith("/ban ") and is_admin(username):
        target = text[5:].strip()
        if target in USERS:
            for ws_target in list(USERS[target]):
                await ws_target.close(4001, "Bị ban vĩnh viễn")
            await system_message(f"{target} đã bị ban bởi {username}")

# ================= MAIN HANDLER =================
async def handler(ws):
    username = None
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except Exception:
                continue

            typ = data.get("type")
            # log incoming message types for debugging file transfer issues
            try:
                logger.info("Incoming msg type=%s from=%s", typ, username or '<anon>')
            except Exception:
                pass

            if typ == "login" and username is None:
                username = await handle_login(ws, data)
                if not username:
                    return
                continue

            if not username:
                await ws.close(1008)
                return

            text = data.get("text", "")
            if typ == "group" and isinstance(text, str) and text.startswith("/"):
                await handle_admin_command(ws, text, username)
                continue

            if typ == "group":
                await handle_group(ws, data, username)
            elif typ == "private":
                await handle_private(ws, data, username)
            elif typ == "typing":
                await handle_typing(data, username)
            elif typ == "reaction":
                await handle_reaction(data, username)
            elif typ == "file_chunk":
                await handle_file_chunk(ws, data, username)

    except websockets.ConnectionClosed as e:
        try:
            logger.info(f"ConnectionClosed(code={e.code}, reason={e.reason}) for user={username}")
        except Exception:
            logger.info(f"ConnectionClosed for user={username}")
    except Exception as e:
        logger.error(f"Unhandled exception in handler for user={username}: {e}")
        logger.debug(traceback.format_exc())
    finally:
        if username:
            USERS[username].discard(ws)
            if not USERS[username]:
                USERS.pop(username, None)
                TYPING.discard(username)
                RATE_QUEUE.pop(username, None)
                logger.info(f"{username} đã thoát → tổng session còn: {sum(len(s) for s in USERS.values())}")
                try:
                    await system_message(f"{username} đã rời phòng chat")
                    await send_user_list()
                except Exception as e:
                    logger.error(f"Lỗi gửi system_message sau khi {username} rời: {e}")
                    logger.debug(traceback.format_exc())

# ================= SSL SUPPORT =================
def build_ssl_context_if_available():
    cert = "cert.pem"
    key = "key.pem"
    if os.path.exists(cert) and os.path.exists(key):
        try:
            ctx = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert, keyfile=key)
            logger.info("Loaded cert.pem & key.pem — WSS enabled")
            return ctx
        except Exception as e:
            logger.error(f"Không thể load cert/key: {e}")
            logger.debug(traceback.format_exc())
    return None

# ================= SERVER START =================
async def main():
    load_history()
    ssl_ctx = build_ssl_context_if_available()
    proto = "wss" if ssl_ctx else "ws"
    logger.info(f"ChatSphere Server đang chạy tại {proto}://{HOST}:{PORT}")

    server = await websockets.serve(
        handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=10 * 1024 * 1024,
        ssl=ssl_ctx,
    )

    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        logger.info("Đang tắt server...")
    finally:
        save_history()
        server.close()
        await server.wait_closed()
        logger.info("Server đã dừng. Tạm biệt!")

if __name__ == "__main__":
    asyncio.run(main())
