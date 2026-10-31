from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from morfofix_engine.core.session import SessionStore
from morfofix_engine.render.pipeline import render


def test_render_identity_numpy(rgb_png: Path) -> None:
    store = SessionStore()
    sess = store.create(rgb_png)
    out = render(sess, target="preview").image
    diff = np.abs(out.astype(np.int16) - sess.preview.astype(np.int16))
    assert int(diff.max()) <= 1


def test_render_http_preview(client: TestClient, rgb_png: Path) -> None:
    sid = client.post("/session", json={"path": str(rgb_png)}).json()["session_id"]
    r = client.post(f"/session/{sid}/render", json={})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    arr = np.frombuffer(r.content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert img is not None
    assert img.shape[0] == 60
    assert img.shape[1] == 80
