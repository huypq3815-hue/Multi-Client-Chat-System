import base64
import threading
import time
from collections import defaultdict

# Temporary uploads storage. Keyed by upload_id.
# Each entry: { 'meta': {...}, 'chunks': dict(index->data), 'total': int, 'created': timestamp }
_UPLOADS = {}
_LOCK = threading.Lock()

UPLOAD_TTL = 60 * 10  # keep incomplete uploads for 10 min

def add_chunk(upload_id: str, index: int, total: int, data_b64: str, meta: dict = None):
    """Add one chunk to an upload. Returns True if completed and assembled bytes.

    - upload_id: unique id provided by client
    - index: 0-based chunk index
    - total: total number of chunks expected
    - data_b64: base64 string of chunk
    - meta: optional metadata like name/type/size
    """
    with _LOCK:
        ent = _UPLOADS.get(upload_id)
        if not ent:
            ent = {'meta': meta or {}, 'chunks': {}, 'total': total, 'created': time.time()}
            _UPLOADS[upload_id] = ent
        ent['chunks'][index] = data_b64
        ent['total'] = total

        if len(ent['chunks']) == total:
            # assemble: decode each base64 part separately then join bytes
            parts = [ent['chunks'][i] for i in range(total)]
            try:
                decoded_parts = [base64.b64decode(p) for p in parts]
                raw = b''.join(decoded_parts)
            except Exception:
                raw = None
            # cleanup
            del _UPLOADS[upload_id]
            return raw, ent.get('meta')
    return None, None

def cleanup_expired():
    now = time.time()
    with _LOCK:
        to_del = [k for k, v in _UPLOADS.items() if now - v.get('created', 0) > UPLOAD_TTL]
        for k in to_del:
            del _UPLOADS[k]

def chunk_bytes(b: bytes, chunk_size: int = 4096):
    """Yield base64-encoded string chunks from bytes for transmission in sequence."""
    i = 0
    while i < len(b):
        part = b[i:i+chunk_size]
        yield base64.b64encode(part).decode('ascii')
        i += chunk_size
