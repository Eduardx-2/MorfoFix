"""F2a: brazo manual sin pose y params de cuerpo sin 422."""
from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from morfofix_engine.body.arm import arm_manual_field
from morfofix_engine.core.edit_state import ArmManual, EditState
from morfofix_engine.render.pipeline import _render


def _sess(img):
    return SimpleNamespace(
        preview=img, original=img, faces=[], bodies=[], masks={},
        meta=SimpleNamespace(warnings=[], image_sha1="x"), params=None, registry=None,
    )


def _tex(h=400, w=320):
    rng = np.random.default_rng(0)
    small = rng.integers(0, 255, (40, 32, 3), dtype=np.uint8)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def _manual(**kw):
    base = dict(cx=0.5, cy=0.5, rx=0.08, ry=0.2, angle=15, value=0.6)
    base.update(kw)
    return {"arm": {"manual": base}}


def test_no_person_arm_manual_200_roi_changes():
    img = _tex()
    sess = _sess(img)
    base = _render(sess, state=EditState()).image
    warped = _render(sess, state=EditState.model_validate(_manual())).image
    h, w = img.shape[:2]
    s = min(h, w)
    cy, cx = int(0.5 * (h - 1)), int(0.5 * (w - 1))
    rx, ry = 0.08 * s, 0.2 * s
    yy, xx = np.ogrid[:h, :w]
    inside = ((xx - cx) / max(rx, 1)) ** 2 + ((yy - cy) / max(ry, 1)) ** 2 <= 1
    outside = ((xx - cx) / max(rx * 2, 1)) ** 2 + ((yy - cy) / max(ry * 2, 1)) ** 2 >= 1
    dif = np.abs(warped.astype(np.int16) - base.astype(np.int16)).mean(axis=2)
    assert dif[inside].mean() > 2
    assert dif[outside].max() <= 1


def test_no_person_body_param_is_warning_not_422(client, tmp_path):
    from PIL import Image
    p = tmp_path / "t.png"
    Image.fromarray(_tex()).save(p)
    sid = client.post("/session", json={"path": str(p)}).json()["session_id"]
    empty = client.post(f"/session/{sid}/render", json={"state": {}})
    r = client.post(f"/session/{sid}/render", json={"state": {
        "body": {"0": {"intensity_bodyslim_armthin": 0.5}},
    }})
    assert r.status_code == 200, r.text
    assert "POSE_UNAVAILABLE" in r.headers.get("X-Warnings", "")
    assert r.headers.get("X-Pose-Available") == "false"
    assert empty.content == r.content


def test_arm_manual_value_zero_identity():
    img = _tex()
    sess = _sess(img)
    a = _render(sess, state=EditState()).image
    b = _render(sess, state=EditState.model_validate(_manual(value=0))).image
    assert np.array_equal(a, b)


def test_arm_manual_sign():
    h, w = 200, 160
    img = np.zeros((h, w, 3), np.uint8)
    img[:, 70:90] = 255
    sess = _sess(img)
    thin = _render(sess, state=EditState.model_validate(
        _manual(cx=0.5, cy=0.5, rx=0.12, ry=0.4, angle=0, value=0.6)
    )).image
    fat = _render(sess, state=EditState.model_validate(
        _manual(cx=0.5, cy=0.5, rx=0.12, ry=0.4, angle=0, value=-0.6)
    )).image
    row = h // 2
    def width(im):
        return int((im[row, :, 0] > 40).sum())
    assert width(thin) < width(img)
    assert width(fat) > width(img)


def test_arm_manual_rotation():
    h, w = 200, 160
    img = np.zeros((h, w, 3), np.uint8)
    img[90:110, :] = 255
    sess = _sess(img)
    out = _render(sess, state=EditState.model_validate(
        _manual(cx=0.5, cy=0.5, rx=0.12, ry=0.4, angle=90, value=0.8)
    )).image
    col = w // 2
    def height(im):
        return int((im[:, col, 0] > 40).sum())
    assert height(out) < height(img)


def test_arm_manual_no_foldover():
    for value in (1.0, -1.0):
        f = arm_manual_field(200, 160, ArmManual(cx=0.5, cy=0.5, rx=0.1, ry=0.2, angle=0, value=value))
        jxx = 1 + np.gradient(f.dx, axis=1)
        jxy = np.gradient(f.dx, axis=0)
        jyx = np.gradient(f.dy, axis=1)
        jyy = 1 + np.gradient(f.dy, axis=0)
        det = jxx * jyy - jxy * jyx
        assert float(det.min()) > 0.2, value


def test_arm_manual_protect_bg_without_mask():
    img = _tex()
    sess = _sess(img)
    res = _render(sess, state=EditState.model_validate(_manual(protect_bg=True)))
    assert "NO_BODY_MASK" in res.warnings


def test_arm_manual_validation(client, tmp_path):
    from PIL import Image
    p = tmp_path / "t.png"
    Image.fromarray(_tex()).save(p)
    sid = client.post("/session", json={"path": str(p)}).json()["session_id"]
    bad = [
        {"rx": 0},
        {"ry": 0.6},
        {"angle": 200},
        {"cx": 1.2},
        {"extra": 1},
    ]
    for patch in bad:
        body = _manual()
        body["arm"]["manual"].update(patch)
        r = client.post(f"/session/{sid}/render", json={"state": body})
        assert r.status_code == 400, patch
        assert r.json()["error"]["code"] == "BAD_PARAM"
    with pytest.raises(ValidationError):
        ArmManual.model_validate({"cx": 0.5, "cy": 0.5, "rx": 0, "ry": 0.1, "value": 0.2})


def test_freeze_blocks_arm_manual():
    img = _tex()
    sess = _sess(img)
    base = _render(sess, state=EditState()).image
    frozen = _render(sess, state=EditState.model_validate({
        **_manual(),
        "freeze": {"rects": [{"x": 0, "y": 0, "w": 1, "h": 1}]},
    })).image
    assert np.abs(frozen.astype(int) - base.astype(int)).max() == 0
