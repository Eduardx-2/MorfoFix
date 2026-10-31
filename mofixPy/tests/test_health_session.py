from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["api"] == "v0"
    assert "face_landmarker" in body["models"]


def test_session_plain_png(client: TestClient, rgb_png: Path) -> None:
    r = client.post("/session", json={"path": str(rgb_png)})
    assert r.status_code == 200
    data = r.json()
    assert data["width"] == 80
    assert data["height"] == 60
    sid = data["session_id"]
    assert sid.startswith("s_")
    r2 = client.delete(f"/session/{sid}")
    assert r2.status_code == 204


def test_session_exif_orientation_6(client: TestClient, tmp_path: Path) -> None:
    im = Image.new("RGB", (40, 80), (200, 30, 30))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 10, 10), fill=(0, 255, 0))
    exif = im.getexif()
    exif[0x0112] = 6
    path = tmp_path / "rot.jpg"
    im.save(path, format="JPEG", quality=95, exif=exif)
    r = client.post("/session", json={"path": str(path)})
    assert r.status_code == 200
    data = r.json()
    # Orientation 6: 90° CW → 80×40
    assert data["width"] == 80
    assert data["height"] == 40
    assert data["orientation_applied"] == 6


def test_catalog(client: TestClient) -> None:
    r = client.get("/catalog")
    names = {p["name"] for p in r.json()["params"]}
    assert "intensity_jaw" in names
    assert "intensity_bodyslim_waistthin" in names
    jaw = next(p for p in r.json()["params"] if p["name"] == "intensity_jaw")
    assert jaw["status"] == "ready"


def test_bad_param(client: TestClient, rgb_png: Path) -> None:
    sid = client.post("/session", json={"path": str(rgb_png)}).json()["session_id"]
    r = client.post(f"/session/{sid}/params", json={"name": "no_existe", "value": 0.2})
    assert r.status_code == 400


def test_body_without_detection_is_warning(client: TestClient, rgb_png: Path) -> None:
    sid = client.post("/session", json={"path": str(rgb_png)}).json()["session_id"]
    r = client.post(
        f"/session/{sid}/params",
        json={"name": "intensity_bodyslim_waistthin", "value": 0.4},
    )
    assert r.status_code == 200, r.text
    assert "POSE_UNAVAILABLE" in r.headers.get("X-Warnings", "")


def test_unknown_session(client: TestClient) -> None:
    r = client.post("/session/s_deadbeef/render", json={})
    assert r.status_code == 404
