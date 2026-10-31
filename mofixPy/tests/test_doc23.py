"""Doc 23: trazos de brazo fijados, pincel de retoque sin cara, extremidades, rescate de cara."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from morfofix_engine.core.edit_state import EditState
from morfofix_engine.render.pipeline import _render
from morfofix_engine.inference.face import head_boxes_from_bodies
from morfofix_engine.retouch.effects import apply_retouch
from tests.test_arm_manual import _sess, _tex


def _st(cx, value, **kw):
    return dict(cx=cx, cy=0.5, rx=0.08, ry=0.2, angle=0, value=value, **kw)


def test_fixed_arm_stroke_stays_when_editor_moves():
    img = _tex(400, 400)
    sess = _sess(img)
    only_a = _render(sess, state=EditState.model_validate({"arm": {"manual": _st(.3, .7)}})).image
    # Trazo A fijado y editor movido a otra zona con valor 0: A sigue aplicado igual.
    fixed = _render(sess, state=EditState.model_validate({"arm": {"manual_strokes": [_st(.3, .7)], "manual": _st(.7, 0)}})).image
    assert np.array_equal(only_a, fixed)


def test_strokes_compose_in_order_deterministic():
    img = _tex(400, 400)
    sess = _sess(img)
    st = {"arm": {"manual_strokes": [_st(.3, .7), _st(.7, -.5)], "manual": _st(.5, .3)}}
    a = _render(sess, state=EditState.model_validate(st)).image
    b = _render(sess, state=EditState.model_validate(st)).image
    base = _render(sess, state=EditState()).image
    assert np.array_equal(a, b)
    d = np.abs(a.astype(int) - base.astype(int)).mean(2)
    assert d[:, 90:150].mean() > 1 and d[:, 250:310].mean() > 1


def test_arm_strokes_limit_400():
    with pytest.raises(ValidationError):
        EditState.model_validate({"arm": {"manual_strokes": [_st(.5, .1)] * 33}})
    EditState.model_validate({"arm": {"manual_strokes": [_st(.5, .1)] * 32}})


def test_arm_strokes_limit_http_400(client, tmp_path):
    from PIL import Image
    p = tmp_path / "t.png"
    Image.fromarray(_tex()).save(p)
    sid = client.post("/session", json={"path": str(p)}).json()["session_id"]
    r = client.post(f"/session/{sid}/render", json={"state": {"arm": {"manual_strokes": [_st(.5, .1)] * 33}}})
    assert r.status_code == 400


def test_retouch_brush_works_without_face():
    img = _tex(300, 300)
    stroke = {"strokes": [{"pts": [[.4, .5], [.6, .5]], "radius": .08, "erase": False}]}
    st = EditState.model_validate({"retouch": {"degree_skin_smooth": 1, "brush": {"degree_skin_smooth": stroke}}})
    out = apply_retouch(img, [], st.retouch)
    d = np.abs(out.astype(int) - img.astype(int)).mean(2)
    assert d[140:160, 130:170].mean() > .5
    assert d[:60].max() == 0


def test_no_face_warning_only_for_face_tools():
    sess = _sess(_tex())
    stroke = {"strokes": [{"pts": [[.4, .5], [.6, .5]], "radius": .08, "erase": False}]}
    r = _render(sess, state=EditState.model_validate({"retouch": {"degree_skin_smooth": 1, "brush": {"degree_skin_smooth": stroke}}}))
    assert "NO_FACE_RETOUCH" not in r.warnings
    r = _render(sess, state=EditState.model_validate({"retouch": {"degree_whiten_teeth": 1}}))
    assert "NO_FACE_RETOUCH" in r.warnings


def test_head_boxes_from_pose():
    kp = np.zeros((33, 4), np.float32)
    kp[:, 3] = 1
    kp[0, :2] = (.5, .1); kp[7, :2] = (.53, .1); kp[8, :2] = (.47, .1)
    kp[11, :2] = (.6, .2); kp[12, :2] = (.4, .2)
    boxes = head_boxes_from_bodies([SimpleNamespace(keypoints=kp)], 1600, 1200)
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    assert x0 < 600 < x1 and y0 < 160 < y1
    kp[[0, 7, 8], 3] = 0
    assert head_boxes_from_bodies([SimpleNamespace(keypoints=kp)], 1600, 1200) == []


def test_muscle_clarity_skips_clothes_and_outside():
    from morfofix_engine.body.muscle import _clarity, CLOTHES_GAIN
    img = _tex(200, 200)
    M = np.zeros((200, 200), np.float32)
    M[:, :100] = CLOTHES_GAIN      # ropa
    M[50:150, 120:180] = 1.0       # piel
    out = _clarity(img, M, 120.0, 1.5)
    assert np.array_equal(out[:, :100], img[:, :100])
    assert np.abs(out[60:140, 130:170].astype(int) - img[60:140, 130:170].astype(int)).mean() > .5
