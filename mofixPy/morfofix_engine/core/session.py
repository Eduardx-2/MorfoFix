"""Almacén de sesiones en RAM."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from morfofix_engine.core.errors import EngineError
from morfofix_engine.core.state import SessionParams
from morfofix_engine.core.edit_state import EditState
from morfofix_engine.inference.face import Face
from morfofix_engine.inference.pose import Body
from morfofix_engine.io.load import ImageMeta, load_path, make_preview, decode_image


@dataclass
class Session:
    id: str
    source_path: Path | None
    original: np.ndarray
    preview: np.ndarray
    meta: ImageMeta
    faces: list[Face] | None = None
    bodies: list[Body] | None = None
    masks: dict[str, np.ndarray] = field(default_factory=dict)
    params: SessionParams = field(default_factory=SessionParams)
    edit_state: EditState = field(default_factory=EditState)
    registry: object | None = None
    created_at: float = field(default_factory=time.time)
    touched_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, max_sessions: int = 4, max_idle_s: int = 3600) -> None:
        self.max_sessions = max_sessions
        self.max_idle_s = max_idle_s
        self._sessions: dict[str, Session] = {}

    def create(self, src: Path | bytes, name: str = "upload") -> Session:
        self.gc()
        if isinstance(src, Path):
            img, meta = load_path(src)
            path: Path | None = src
        else:
            img, meta = decode_image(src, source_name=name)
            path = None
        sid = "s_" + secrets.token_hex(4)
        sess = Session(
            id=sid,
            source_path=path,
            original=img,
            preview=make_preview(img),
            meta=meta,
        )
        self._sessions[sid] = sess
        while len(self._sessions) > self.max_sessions:
            oldest = min(self._sessions.values(), key=lambda s: s.touched_at)
            self._sessions.pop(oldest.id, None)
        return sess

    def get(self, sid: str) -> Session:
        sess = self._sessions.get(sid)
        if sess is None:
            raise EngineError(404, "sesión inexistente", {"session_id": sid})
        sess.touched_at = time.time()
        return sess

    def drop(self, sid: str) -> None:
        if sid not in self._sessions:
            raise EngineError(404, "sesión inexistente", {"session_id": sid})
        del self._sessions[sid]

    def gc(self) -> None:
        now = time.time()
        dead = [s.id for s in self._sessions.values() if now - s.touched_at > self.max_idle_s]
        for sid in dead:
            self._sessions.pop(sid, None)

    def __len__(self) -> int:
        return len(self._sessions)
