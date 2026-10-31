from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image


def test_export_png(client: TestClient, rgb_png: Path, tmp_path: Path) -> None:
    sid = client.post("/session", json={"path": str(rgb_png)}).json()["session_id"]
    dest = tmp_path / "out.png"
    r = client.post(
        f"/session/{sid}/export",
        json={"path": str(dest), "format": "png"},
    )
    assert r.status_code == 200
    assert dest.is_file()
    src = np.array(Image.open(rgb_png))
    got = np.array(Image.open(dest))
    assert src.shape == got.shape
    assert int(np.abs(src.astype(np.int16) - got.astype(np.int16)).max()) <= 1


def test_export_relative_rejected(client: TestClient, rgb_png: Path) -> None:
    sid = client.post("/session", json={"path": str(rgb_png)}).json()["session_id"]
    r = client.post(
        f"/session/{sid}/export",
        json={"path": "relativo.png", "format": "png"},
    )
    assert r.status_code == 400
