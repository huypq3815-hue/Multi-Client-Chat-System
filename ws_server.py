#!/usr/bin/env python3
"""
ChatSphere WebSocket Server – Ultimate Edition
Supports: group, private, typing, history, file, emoji, reactions, rate-limit, file log
"""

import asyncio
import websockets
import json
import re
import base64
import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque

# ================= CONFIG =================
HOST = "0.0.0.0"
PORT = 6789
MAX_HISTORY = 500
MAX_USERNAME_LEN = 24
MAX_MESSAGE_LEN = 2000
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
RATE_LIMIT = 5  # messages per second per user
HISTORY_FILE = "chat_history.json"
LOG_FILE = "chat.log"

# ================= LOGGING =================
logger = logging.getLogger("ChatServer")
logger.setLevel(logging.INFO)

# Console: màu
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'INFO': '\033[92m',      # xanh lá
        'WARNING': '\033[93m',   # vàng
        'ERROR': '\033[91m',     # đỏ
        'DEBUG': '\033[94m',     # xanh dương
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
))

# File: rotating 5MB
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# ================= STATE =================
USERS = {}                    # username -> websocket
TYPING = set()
HISTORY = []
MESSAGE_ID_COUNTER = 0
RATE_LIMIT_QUEUE = defaultdict(lambda: deque())  # username -> deque of timestamps

# ================= UTILS =================
def now_iso():
    return datetime.now().isoformat(timespec='seconds')

def generate_id():
    global MESSAGE_ID_COUNTER
    MESSAGE_ID_COUNTER += 1
    return f"msg_{MESSAGE_ID_COUNTER}"

def is_valid_username(name):
    return bool(name and len(name) <= MAX_USERNAME_LEN and re.match(r'^[a-zA-Z0-9_\-\.]+$', name))

def load_history():
    global HISTORY
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                HISTORY = data[-MAX_HISTORY:]
            logger.info(f"Loaded {len(HISTORY)} messages from history")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(HISTORY[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
        logger.info("History saved")
    except Exception as e:
        logger.error(f"Failed to save history: {e}")

def add_to_history(msg):
    msg["id"] = generate_id()
    HISTORY.append(msg)
    if len(HISTORY) > MAX_HISTORY:
        HISTORY.pop(0)

def is_rate_limited(username):
    now = asyncio.get_event_loop().time()
    queue = RATE_LIMIT_QUEUE[username]
    # Xóa tin nhắn cũ hơn 1s
    while queue and queue[0] < now - 1.0:
        queue.popleft()
    if len(queue) >= RATE_LIMIT:
        return True
    queue.append(now)
    return False

# ================= BROADCAST =================
async def broadcast(msg_obj, exclude=None):
    msg = json.dumps(msg_obj)
    tasks = []
    for username, ws in USERS.items():
        if exclude and username in exclude:
            continue
        tasks.append(ws.send(msg))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def notify_user_list():
    await broadcast({"type": "user_list", "users": list(USERS.keys())})

async def notify_system(text, exclude=None):
    msg = {"type": "system", "text": text, "time": now_iso()}
    add_to_history(msg)
    await broadcast(msg, exclude)

# ================= HANDLERS =================
async def handle_login(ws, data):
    username = data.get("username", "").strip()
    if not is_valid_username(username):
        await ws.send(json.dumps({"type": "system", "text": "Invalid username (a-z, 0-9, _, -, . only)"}))
        await ws.close(code=1008)
        return None
    if username in USERS:
        await ws.send(json.dumps({"type": "system", "text": "Username already taken"}))
        await ws.close(code=1008)
        return None

    USERS[username] = ws
    logger.info(f"{username} connected ({len(USERS)} online)")

    # Gửi lịch sử
    for msg in HISTORY[-100:]:
        try:
            await ws.send(json.dumps(msg))
        except:
            pass

    await notify_system(f"{username} joined the chat")
    await notify_user_list()
    return username

async def handle_group(data):
    from_user = data.get("from")
    text = data.get("text", "").strip()
    file_data = data.get("file")  # {"name": "", "type": "", "data": "base64"}

    if not from_user or (not text and not file_data):
        return
    if text and len(text) > MAX_MESSAGE_LEN:
        return

    if is_rate_limited(from_user):
        return

    msg = {
        "type": "group",
        "from": from_user,
        "text": text or "",
        "time": now_iso()
    }
    if file_data:
        try:
            raw = base64.b64decode(file_data["data"])
            if len(raw) > MAX_FILE_SIZE:
                return
            msg["file"] = {
                "name": file_data["name"],
                "type": file_data["type"],
                "size": len(raw),
                "data": file_data["data"]
            }
        except:
            return

    add_to_history(msg)
    await broadcast(msg)

async def handle_private(data):
    from_user = data.get("from")
    to_user = data.get("to")
    text = data.get("text", "").strip()

    if not all([from_user, to_user, text]) or len(text) > MAX_MESSAGE_LEN:
        return

    if is_rate_limited(from_user):
        return

    msg = {
        "type": "private",
        "from": from_user,
        "to": to_user,
        "text": text,
        "time": now_iso()
    }
    add_to_history(msg)

    sent = False
    if to_user in USERS:
        await USERS[to_user].send(json.dumps(msg))
        sent = True
    if from_user in USERS:
        await USERS[from_user].send(json.dumps(msg))
        sent = True
    if not sent:
        await notify_system(f"User {to_user} is offline", exclude={from_user})

async def handle_typing(data):
    username = data.get("from")
    is_typing = data.get("isTyping", False)
    if not username:
        return
    if is_typing:
        TYPING.add(username)
    else:
        TYPING.discard(username)
    await broadcast({
        "type": "typing",
        "from": username,
        "isTyping": is_typing
    })

async def handle_reaction(data):
    username = data.get("from")
    msg_id = data.get("id")
    emoji = data.get("emoji", "")
    if not all([username, msg_id, emoji]) or len(emoji) > 3:
        return
    reaction = {"type": "reaction", "from": username, "id": msg_id, "emoji": emoji, "time": now_iso()}
    await broadcast(reaction)

# ================= MAIN HANDLER =================
async def handler(ws):
    username = None
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "login" and username is None:
                username = await handle_login(ws, data)
                if not username:
                    return
                continue

            if username is None:
                await ws.close(code=1008)
                return

            if msg_type == "group":
                await handle_group(data)
            elif msg_type == "private":
                await handle_private(data)
            elif msg_type == "typing":
                await handle_typing(data)
            elif msg_type == "reaction":
                await handle_reaction(data)

    except websockets.ConnectionClosed as e:
        logger.info(f"Connection closed: {e.code}")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if username and username in USERS:
            del USERS[username]
            TYPING.discard(username)
            RATE_LIMIT_QUEUE.pop(username, None)
            logger.info(f"{username} disconnected ({len(USERS)} online)")
            await notify_system(f"{username} left the chat")
            await notify_user_list()

# ================= SERVER START =================
async def main():
    load_history()
    logger.info(f"Server starting on ws://{HOST}:{PORT}")

    server = await websockets.serve(
        handler,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10,
        max_size=10 * 1024 * 1024  # 10MB
    )

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        save_history()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")