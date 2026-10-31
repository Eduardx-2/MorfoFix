"""Content-addressed bounded RAM/disk cache. No pickle and no network."""
from collections import OrderedDict
from pathlib import Path
from threading import RLock
import hashlib
import json
import os
import tempfile
from zipfile import BadZipFile
import numpy as np


class InferenceCache:
    def __init__(self, directory=None, max_bytes=128*1024**2, disk_bytes=1024**3):
        self.directory = Path(directory) if directory else None
        self.max_bytes, self.disk_bytes = max_bytes, disk_bytes
        self.ram = OrderedDict()
        self.bytes = 0
        self.lock = RLock()
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(image_sha1, geom_hash, kind, model_sha256, params):
        raw = json.dumps([image_sha1, geom_hash, kind, model_sha256, params], sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key):
        with self.lock:
            if key in self.ram:
                self.ram.move_to_end(key)
                return {k:v.copy() for k,v in self.ram[key].items()}
            if self.directory:
                path = self.directory / f"{key}.npz"
                try:
                    with np.load(path, allow_pickle=False) as data:
                        value = {k:data[k] for k in data.files}
                    os.utime(path, None)
                    self._remember(key, value)
                    return {k:v.copy() for k,v in value.items()}
                except (OSError, ValueError, EOFError, BadZipFile):
                    pass
            return None

    def _remember(self, key, value):
        if key in self.ram:
            self.bytes -= sum(a.nbytes for a in self.ram.pop(key).values())
        size = sum(a.nbytes for a in value.values())
        if size > self.max_bytes:
            return
        self.ram[key] = {k:v.copy() for k,v in value.items()}
        self.bytes += size
        while self.bytes > self.max_bytes:
            _, old = self.ram.popitem(last=False)
            self.bytes -= sum(a.nbytes for a in old.values())

    def put_memory(self, key, **arrays):
        with self.lock:
            self._remember(key, arrays)

    def put(self, key, **arrays):
        with self.lock:
            self._remember(key, arrays)
            if not self.directory:
                return
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    np.savez_compressed(stream, **arrays)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, self.directory/f"{key}.npz")
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            files = sorted(self.directory.glob("*.npz"), key=lambda p:p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            for path in files:
                if total <= self.disk_bytes:
                    break
                total -= path.stat().st_size
                path.unlink(missing_ok=True)
