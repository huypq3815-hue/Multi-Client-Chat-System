import os
import json
import threading
from collections import deque

DEFAULT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'chat_history.json')
MAX_HISTORY = 500


class HistoryManager:
    """In-memory history manager with optional persistence to disk.

    Methods:
    - load(): load from file to RAM
    - save(): save RAM to file
    - add(msg): add message dict to RAM (will also add id/time if missing)
    - recent(n): return last n messages
    """

    def __init__(self, history_file: str = None, max_history: int = MAX_HISTORY):
        self._file = history_file or DEFAULT_HISTORY_FILE
        self._max = max_history
        self._lock = threading.Lock()
        self._dq = deque(maxlen=self._max)

    def load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with self._lock:
                for item in data[-self._max:]:
                    self._dq.append(item)
        except Exception:
            # ignore load errors
            pass

    def save(self):
        try:
            with self._lock:
                arr = list(self._dq)[-self._max:]
            with open(self._file, 'w', encoding='utf-8') as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, msg: dict):
        with self._lock:
            self._dq.append(msg)

    def recent(self, n: int = 100):
        with self._lock:
            return list(self._dq)[-n:]

    def all(self):
        with self._lock:
            return list(self._dq)


_default = HistoryManager()

def get_default():
    return _default
