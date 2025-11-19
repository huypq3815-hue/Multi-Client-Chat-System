#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatSphere Server – Windows + Linux/macOS Compatible
Đã fix 100% lỗi tiếng Việt + signal handler trên Windows
"""

import asyncio
import websockets
import json
import re
import base64
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from collections import defaultdict, deque
import traceback

# server modules
from server.history_manager import get_default as get_history_manager
from server.file_transfer import add_chunk as ft_add_chunk, cleanup_expired

# ================= CONFIG =================
HOST = "0.0.0.0"
PORT = 6789

MAX_HISTORY = 500
MAX_USERNAME_LEN = 24
MAX_MESSAGE_LEN = 4000
MAX_FILE_SIZE = 3 * 1024 * 1024      # 3MB
RATE_LIMIT_MESSAGES = 6
RATE_LIMIT_SECONDS = 2
HISTORY_FILE = "chat_history.json"
LOG_FILE = "chat.log"

ADMINS = {"admin", "mod"}  # đổi tên admin ở đây

# ================= LOGGING – FIX TIẾNG VIỆT TRÊN WINDOWS =================
logger = logging.getLogger("ChatSphere")
logger.setLevel(logging.INFO)

# Console handler – dùng utf-8 trên Windows
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', '%H:%M:%S'))

# File handler – rotating log
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))

logger.addHandler(console)
logger.addHandler(file_handler)

# ================= STATE =================
USERS = {}
USER_ROLES = {}
TYPING = set()
HIST = get_history_manager()
REACTIONS = defaultdict(lambda: defaultdict(int))
RATE_QUEUE = defaultdict(lambda: deque())

# ================= UTILS =================
def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def generate_id():
    # id based on current in-memory history length
    return f"msg_{len(HIST.all())+1:06d}"

def is_valid_username(name: str) -> bool:
    return bool(name and len(name) <= MAX_USERNAME_LEN and re.match(r'^[a-zA-Z0-9_\-\.]+$', name))

def is_admin(username: str) -> bool:
    return username.lower() in (a.lower() for a in ADMINS)

def load_history():
    try:
        HIST.load()
        logger.info(f"Đã tải {len(HIST.all())} tin nhắn từ lịch sử")
    except Exception as e:
        logger.error(f"Lỗi tải lịch sử: {e}")

def save_history():
    try:
        HIST.save()
        logger.info("Đã lưu lịch sử")
    except Exception as e:
        logger.error(f"Lỗi lưu lịch sử: {e}")

def add_to_history(msg: dict):
    msg["id"] = generate_id()
    msg["time"] = now_iso()
    HIST.add(msg)
    # trim reactions if necessary
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
    if not USERS: return
    payload = json.dumps(obj, ensure_ascii=False)
    tasks = [
        ws.send(payload)
        for name, ws in USERS.items()
        if not exclude or name not in exclude
    ]
    if tasks:
        # run gather and log any exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                # attempt to identify which user send failed
                try:
                    target_name = list(USERS.keys())[i]
                except Exception:
                    target_name = f"index:{i}"
                logger.error(f"Error sending to {target_name}: {res}")
                logger.debug(traceback.format_exc())

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
        await ws.send(json.dumps({"type": "error", "text": "Tên chỉ được dùng a-z, 0-9, _, -, ."}))
        await ws.close(1008)
        return None
    if name in USERS:
        await ws.send(json.dumps({"type": "error", "text": "Tên này đã có người dùng"}))
        await ws.close(1008)
        return None

    USERS[name] = ws
    USER_ROLES[name] = {"admin"} if is_admin(name) else set()
    logger.info(f"{name} đã tham gia → {len(USERS)} online")

    for msg in HIST.recent(100):
        try: await ws.send(json.dumps(msg, ensure_ascii=False))
        except: pass

    await system_message(f"{name} đã tham gia phòng chat")
    await send_user_list()
    return name

async def handle_group(ws, data: dict, username: str):
    if rate_limited(username): return

    text = (data.get("text") or "").strip()
    file = data.get("file")

    if not text and not file: return
    if text and len(text) > MAX_MESSAGE_LEN:
        await ws.send(json.dumps({"type": "error", "text": f"Tin quá dài (> {MAX_MESSAGE_LEN} ký tự)"}))
        return

    msg = {"type": "group", "from": username, "text": text or ""}

    if file:
        try:
            raw = base64.b64decode(file["data"])
            if len(raw) > MAX_FILE_SIZE:
                await ws.send(json.dumps({"type": "error", "text": "File quá lớn (>3MB)"}))
                return
            msg["file"] = {
                "name": file["name"][:100],
                "type": file["type"],
                "size": len(raw),
                "data": file["data"]
            }
        except: return

    add_to_history(msg)
    await broadcast(msg)

async def handle_private(ws, data: dict, username: str):
    if rate_limited(username): return
    to = data.get("to")
    text = (data.get("text") or "").strip()
    if not (to and text): return

    if to not in USERS:
        await ws.send(json.dumps({"type": "system", "text": f"Người dùng {to} đang offline"}))
        return

    msg = {"type": "private", "from": username, "to": to, "text": text, "time": now_iso()}
    add_to_history(msg)
    await USERS[to].send(json.dumps(msg, ensure_ascii=False))
    await ws.send(json.dumps(msg, ensure_ascii=False))

async def handle_typing(data: dict, username: str):
    is_typing = bool(data.get("isTyping"))
    if is_typing: TYPING.add(username)
    else: TYPING.discard(username)
    # do not broadcast typing event back to sender
    await broadcast({"type": "typing", "from": username, "isTyping": is_typing}, exclude={username})


async def handle_file_chunk(ws, data: dict, username: str):
    """Handle chunked file upload via messages of type 'file_chunk'.

    Expected data: {
        'upload_id': str,
        'index': int,
        'total': int,
        'data': base64str,
        'name': str,
        'type': str,
        'size': int
    }
    """
    upload_id = data.get('upload_id')
    try:
        index = int(data.get('index', 0))
        total = int(data.get('total', 0))
    except Exception:
        return
    b64 = data.get('data')
    meta = {'name': data.get('name', ''), 'type': data.get('type', ''), 'size': data.get('size', 0)}
    if not (upload_id and b64 and total > 0):
        return

    # add chunk and check if completed
    try:
        raw, meta_ret = ft_add_chunk(upload_id, index, total, b64, meta)
        logger.debug(f"Received file_chunk upload_id={upload_id} index={index}/{total} from={username}")
    except Exception as e:
        logger.error(f"Error in ft_add_chunk for upload_id={upload_id}: {e}")
        logger.debug(traceback.format_exc())
        return
    # cleanup expired uploads from time to time
    cleanup_expired()

    if raw is not None:
        # file assembled - check size and broadcast as group message
        logger.info(f"File assembled upload_id={upload_id} name={meta_ret.get('name','')} size={len(raw)} from={username}")
        if len(raw) > MAX_FILE_SIZE:
            await ws.send(json.dumps({"type": "error", "text": "File quá lớn (>3MB)"}))
            return
        b64_full = base64.b64encode(raw).decode('ascii')
        msg = {"type": "group", "from": username, "text": "", "file": {"name": meta_ret.get('name','')[:100], "type": meta_ret.get('type',''), "size": len(raw), "data": b64_full}}
        add_to_history(msg)
        try:
            await broadcast(msg)
        except Exception as e:
            logger.error(f"Error broadcasting assembled file upload_id={upload_id}: {e}")
            logger.debug(traceback.format_exc())

async def handle_reaction(data: dict, username: str):
    msg_id = data.get("id")
    emoji = data.get("emoji", "")[:4]
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
        await ws.send(json.dumps({"type": "system", "text": f"Online: {', '.join(sorted(USERS.keys()))}"}))
    elif text.startswith("/kick ") and is_admin(username):
        target = text[6:].strip()
        if target in USERS and not is_admin(target):
            await USERS[target].close(4000, "Bị kick")
            await system_message(f"{target} đã bị kick bởi {username}")
    elif text.startswith("/ban ") and is_admin(username):
        target = text[5:].strip()
        if target in USERS:
            await USERS[target].close(4001, "Bị ban vĩnh viễn")
            await system_message(f"{target} đã bị ban bởi {username}")

# ================= MAIN HANDLER =================
async def handler(ws):
    username = None
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except:
                continue

            typ = data.get("type")

            if typ == "login" and username is None:
                username = await handle_login(ws, data)
                if not username: return
                continue

            if not username:
                await ws.close(1008)
                return

            text = data.get("text", "")
            if typ == "group" and text.startswith("/"):
                await handle_admin_command(ws, text, username)
                continue

            if typ == "group": await handle_group(ws, data, username)
            elif typ == "private": await handle_private(ws, data, username)
            elif typ == "typing": await handle_typing(data, username)
            elif typ == "reaction": await handle_reaction(data, username)
            elif typ == "file_chunk": await handle_file_chunk(ws, data, username)

    except websockets.ConnectionClosed as e:
        # Log close code & reason for diagnostics
        try:
            logger.info(f"ConnectionClosed(code={e.code}, reason={e.reason}) for user={username}")
        except Exception:
            logger.info(f"ConnectionClosed for user={username}")
    except Exception as e:
        # Log full traceback for debugging
        logger.error(f"Unhandled exception in handler for user={username}: {e}")
        logger.debug(traceback.format_exc())
    finally:
        if username and username in USERS:
            try:
                del USERS[username]
            except Exception:
                logger.debug(f"Error deleting user from USERS: {traceback.format_exc()}")
            TYPING.discard(username)
            RATE_QUEUE.pop(username, None)
            logger.info(f"{username} đã thoát → {len(USERS)} online")
            try:
                await system_message(f"{username} đã rời phòng chat")
            except Exception as e:
                logger.error(f"Error broadcasting system_message after {username} left: {e}")
                logger.debug(traceback.format_exc())
            try:
                await send_user_list()
            except Exception as e:
                logger.error(f"Error sending user list after {username} left: {e}")
                logger.debug(traceback.format_exc())

# ================= SERVER START – Windows Compatible =================
async def main():
    load_history()
    logger.info(f"ChatSphere Server đang chạy tại ws://{HOST}:{PORT}")

    server = await websockets.serve(
        handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=10 * 1024 * 1024,
    )

    # Windows: không dùng signal handler → dùng try/except KeyboardInterrupt
    try:
        await asyncio.Future()  # chạy mãi mãi
    except KeyboardInterrupt:
        logger.info("Đang tắt server...")
    finally:
        save_history()
        server.close()
        await server.wait_closed()
        logger.info("Server đã dừng. Tạm biệt!")

if __name__ == "__main__":
    asyncio.run(main())