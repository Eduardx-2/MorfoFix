"""F1 muscle engine: relief primitives, pose checks, render contract."""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from morfofix_engine.body.muscle import (
    apply_muscle,
    body_frame,
    check_pose,
    height_map,
    muscle_mask,
)
from morfofix_engine.body.muscle_catalog import MUSCLE_ALIAS, MUSCLE_MODE_NAMES, MUSCLE_MODES
from morfofix_engine.body.relief import dome, groove, softlight
from morfofix_engine.core.edit_state import EditState, Mask, Muscle
from morfofix_engine.inference.pose import Body
from morfofix_engine.render.pipeline import render


H, W = 500, 400


def _kp(*, profile=False, z_split=0.0):
    kp = np.zeros((33, 4), np.float32)
    kp[:, 3] = 1
    kp[:11, :2] = (.5, .15)
    if profile:
        kp[11, :2] = (.52, .35)
        kp[12, :2] = (.48, .35)
    else:
        kp[11, :2] = (.62, .35)
        kp[12, :2] = (.38, .35)
    kp[13, :2] = (.70, .50)
    kp[14, :2] = (.30, .50)
    kp[15, :2] = (.74, .64)
    kp[16, :2] = (.26, .64)
    kp[23, :2] = (.58, .75)
    kp[24, :2] = (.42, .75)
    kp[25, :2] = (.58, .88)
    kp[26, :2] = (.42, .88)
    kp[27, :2] = (.58, .98)
    kp[28, :2] = (.42, .98)
    kp[11, 2] = z_split / 2
    kp[12, 2] = -z_split / 2
    return kp


def _skin_bgr(h=H, w=W):
    yy = np.linspace(-24, 24, h, dtype=np.float32)[:, None]
    base = np.array([150, 170, 200], np.float32)
    return np.clip(base + yy[..., None], 0, 255).astype(np.uint8) * np.ones((1, w, 1), np.uint8)


def _body(kp=None):
    return Body(0, (.3, .1, .7, .9), 1.0, _kp() if kp is None else kp, np.ones((H, W), np.float32))


def _masks(*, skin_rect=None):
    body_skin = np.zeros((H, W), np.float32)
    if skin_rect is None:
        body_skin[int(.28 * H):int(.98 * H), int(.28 * W):int(.72 * W)] = 1
    else:
        y0, y1, x0, x1 = skin_rect
        body_skin[y0:y1, x0:x1] = 1
    person = np.clip(body_skin + 0.2, 0, 1)
    return {
        "person": person,
        "body_skin": body_skin,
        "face_skin": np.zeros((H, W), np.float32),
        "hair": np.zeros((H, W), np.float32),
        "clothes": np.zeros((H, W), np.float32),
    }


def _session(client, app, tmp_path, kp=None, masks=None, img=None):
    image = img if img is not None else _skin_bgr()
    path = tmp_path / "skin.png"
    Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(path)
    sid = client.post("/session", json={"path": str(path)}).json()["session_id"]
    sess = app.state.store.get(sid)
    sess.bodies = [_body(kp)]
    sess.masks = masks if masks is not None else _masks()
    return sid, sess


def test_dome_peak_and_support():
    Hm = dome(80, 80, (40, 40), 20, 10, 0.0, 1.0)
    assert abs(float(Hm[40, 40]) - 1.0) < 1e-5
    assert float(Hm[40, 70]) == 0.0
    assert float(Hm[40, 50]) > 0.0
    assert float(Hm[40, 50]) < 1.0


def test_groove_negative():
    G = groove(50, 50, (10, 25), (40, 25), 5, 1.0)
    assert float(G.max()) <= 0.0
    assert float(G[25, 25]) < -0.5


def test_softlight_identity_at_half():
    base = np.linspace(0, 1, 32, dtype=np.float32)
    np.testing.assert_allclose(softlight(base, 0.5), base, atol=1e-6)


def test_check_pose_frontal_ok():
    ok, missing, frontal = check_pose(_kp(), ("abs",), h=H, w=W)
    assert ok == ["abs"] and missing == [] and frontal is True


def test_check_pose_profile_fails():
    ok, missing, frontal = check_pose(_kp(profile=True), ("abs",), h=H, w=W)
    assert ok == ["abs"] and frontal is False


def test_height_map_modes_nonzero():
    kp = _kp()
    for name in MUSCLE_MODE_NAMES:
        layer, support = height_map(kp, H, W, name, 0.5)
        assert layer.shape == (H, W)
        assert float(np.abs(layer).max()) > 0.01, name
        assert float(support.max()) > 0.01, name


def test_strength_zero_identity(client, app, tmp_path):
    sid, sess = _session(client, app, tmp_path)
    empty = render(sess, state=EditState()).image
    zero = render(sess, state=EditState.model_validate({
        "muscle": {"0": {"mode": "man_abs", "strength": 0, "warp": 0}},
    })).image
    assert np.array_equal(empty, zero)
    r0 = client.post(f"/session/{sid}/render", json={"state": {}})
    r1 = client.post(f"/session/{sid}/render", json={"state": {
        "muscle": {"0": {"mode": "man_abs", "strength": 0, "warp": 0}},
    }})
    assert r0.status_code == 200 and r1.status_code == 200
    assert r0.content == r1.content


def test_monotonic_strength(client, app, tmp_path):
    _, sess = _session(client, app, tmp_path)
    base = render(sess, state=EditState()).image.astype(np.float32)
    mads = []
    for strength in (.2, .6, 1.0):
        img = render(sess, state=EditState.model_validate({
            "muscle": {"0": {"mode": "man_abs", "strength": strength, "warp": 0, "gloss": 0}},
        })).image.astype(np.float32)
        torso = img[int(.35 * H):int(.75 * H), int(.35 * W):int(.65 * W)]
        ref = base[int(.35 * H):int(.75 * H), int(.35 * W):int(.65 * W)]
        mads.append(float(np.mean(np.abs(torso - ref))))
    assert mads[0] < mads[1] < mads[2]
    assert mads[0] > 0


def test_outside_mask_untouched(client, app, tmp_path):
    rect = (int(.40 * H), int(.70 * H), int(.40 * W), int(.60 * W))
    masks = _masks(skin_rect=rect)
    _, sess = _session(client, app, tmp_path, masks=masks)
    orig = render(sess, state=EditState()).image
    out = render(sess, state=EditState.model_validate({
        "muscle": {"0": {"mode": "man_abs", "strength": 0.8, "warp": 0}},
    })).image
    outside = np.ones((H, W), bool)
    outside[rect[0]:rect[1], rect[2]:rect[3]] = False
    # keep a margin around the rect so feather/dilation is not compared
    yy, xx = np.ogrid[:H, :W]
    cy, cx = (rect[0] + rect[1]) / 2, (rect[2] + rect[3]) / 2
    far = (yy - cy) ** 2 + (xx - cx) ** 2 > (0.28 * max(H, W)) ** 2
    delta = np.abs(out.astype(np.int16) - orig.astype(np.int16)).max(axis=2)
    assert int(delta[far].max()) <= 1


def test_chroma_preserved(client, app, tmp_path):
    _, sess = _session(client, app, tmp_path)
    orig = render(sess, state=EditState()).image
    out, _, _, M = apply_muscle(
        orig.copy(), sess.bodies, sess.masks,
        {"0": Muscle(mode="man_abs", strength=0.8, warp=0, gloss=0)},
    )
    lab0 = cv2.cvtColor(orig, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab1 = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
    inside = M > 0.5
    assert inside.any()
    da = np.abs(lab1[:, :, 1] - lab0[:, :, 1])[inside].mean()
    db = np.abs(lab1[:, :, 2] - lab0[:, :, 2])[inside].mean()
    assert da <= 2 and db <= 2


def test_brush_erase_all(client, app, tmp_path):
    _, sess = _session(client, app, tmp_path)
    orig = render(sess, state=EditState()).image
    erased = render(sess, state=EditState.model_validate({
        "muscle": {"0": {
            "mode": "man_abs", "strength": 0.8, "warp": 0,
            "brush": {"strokes": [{"pts": [[.5, .5]], "radius": .5, "erase": True}]},
        }},
    })).image
    assert np.mean(np.abs(erased.astype(np.int16) - orig.astype(np.int16))) < 0.5


def test_render_no_frontal_is_warning(client, app, tmp_path):
    sid, _ = _session(client, app, tmp_path, kp=_kp(profile=True))
    r = client.post(f"/session/{sid}/render", json={"state": {
        "muscle": {"0": {"mode": "abs", "strength": 0.6}},
    }})
    assert r.status_code == 200, r.text
    assert "MUSCLE_SKIPPED:NO_FRONTAL_BODY" in r.headers.get("X-Warnings", "")


def test_render_missing_person_is_warning(client, app, tmp_path):
    sid, _ = _session(client, app, tmp_path)
    r = client.post(f"/session/{sid}/render", json={"state": {
        "muscle": {"3": {"mode": "abs", "strength": 0.6}},
    }})
    assert r.status_code == 200, r.text
    assert "MUSCLE_SKIPPED:NO_BODY" in r.headers.get("X-Warnings", "")


def test_catalog_muscle_has_7_modes_no_group(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    items = [p for p in r.json()["params"] if p.get("tab") == "Muscle"]
    names = [p["name"] for p in items]
    assert names == list(MUSCLE_MODE_NAMES)
    assert "group" not in items[0]
    assert all(p["kind"] == "mode" for p in items)
    assert set(MUSCLE_MODES) == set(MUSCLE_MODE_NAMES)


def test_legacy_modes_alias():
    for old, new in MUSCLE_ALIAS.items():
        st = EditState.model_validate({"muscle": {"0": {"mode": old, "strength": 0.2}}})
        assert st.muscle["0"].mode == new
        assert st.model_dump()["muscle"]["0"]["mode"] == new


def test_legacy_gender_field_ignored_and_logged(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="morfofix.muscle"):
        st = EditState.model_validate({
            "muscle": {"0": {"mode": "woman_arm", "gender": "her", "strength": 0.2}},
        })
    assert st.muscle["0"].mode == "arm"
    assert "deprecado" in caplog.text


def test_woman_arm_equals_arm_pipeline(client, app, tmp_path):
    _, sess = _session(client, app, tmp_path)
    a = render(sess, state=EditState.model_validate({
        "muscle": {"0": {"mode": "woman_arm", "strength": 0.6, "warp": 0.3}},
    })).image
    b = render(sess, state=EditState.model_validate({
        "muscle": {"0": {"mode": "arm", "strength": 0.6, "warp": 0.3}},
    })).image
    assert np.array_equal(a, b)


def test_presets_validate_after_rename():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    files = list(root.glob("**/presets/**/*.json")) + list(root.glob("**/*preset*.json"))
    for path in files:
        raw = path.read_text(encoding="utf-8")
        if "muscle" not in raw and "body_muscle" not in raw:
            continue
        import json
        EditState.model_validate(json.loads(raw) if raw.strip().startswith("{") else {"muscle": {}})


def test_state_rejects_bad_mode():
    with pytest.raises(ValidationError):
        EditState.model_validate({"muscle": {"0": {"mode": "nope"}}})
    with pytest.raises(ValidationError):
        EditState.model_validate({"muscle": {"-1": {"mode": "man_abs"}}})
    EditState.model_validate({"muscle": {"0": {"mode": "woman_chest", "strength": 0.4}}})


def test_old_state_without_muscle_still_validates():
    state = EditState.model_validate({"body": {"0": {"intensity_bodyslim_waistthin": 0.2}}})
    assert state.muscle == {}


def test_body_frame_axes():
    frame = body_frame(_kp(), H, W)
    assert frame["T"] > frame["W"] * 0.5
    assert abs(float(np.linalg.norm(frame["u"])) - 1) < 1e-5
    assert abs(float(np.linalg.norm(frame["v"])) - 1) < 1e-5


def test_muscle_mask_clothes_warning():
    masks = _masks()
    masks["body_skin"][:] = 0
    masks["clothes"][:] = 1
    masks["person"][:] = 1
    _, support = height_map(_kp(), H, W, "man_abs", 0.5)
    M, warnings = muscle_mask(masks, support, H, W, Mask(), body_frame(_kp(), H, W)["T"])
    assert "NO_BODY_SKIN_MASK" in warnings
    assert "MUSCLE_OVER_CLOTHES" in warnings
    assert M.shape == (H, W)


def test_brush_add_limits_to_painted_area(client, app, tmp_path):
    """Pintar (add) limita el relieve a lo pintado; antes no cambiaba nada (máscara arrancaba en 1)."""
    _, sess = _session(client, app, tmp_path)
    orig = render(sess, state=EditState()).image.astype(np.int16)
    full = render(sess, state=EditState.model_validate({
        "muscle": {"0": {"mode": "man_abs", "strength": 0.8, "warp": 0}},
    })).image.astype(np.int16)
    painted = render(sess, state=EditState.model_validate({
        "muscle": {"0": {
            "mode": "man_abs", "strength": 0.8, "warp": 0,
            "brush": {"strokes": [{"pts": [[.40, .62], [.44, .62]], "radius": .04, "erase": False}]},
        }},
    })).image.astype(np.int16)
    d_full = np.abs(full - orig).max(axis=2)
    d_paint = np.abs(painted - orig).max(axis=2)
    assert (d_paint > 2).sum() > 0, "el trazo pintado no hace nada"
    assert (d_paint > 2).sum() < 0.6 * (d_full > 2).sum(), "Pintar no limita el área"
    assert not np.array_equal(painted, full)


def test_brush_weight_semantics():
    from morfofix_engine.body.muscle import brush_weight
    add = Mask.model_validate({"strokes": [{"pts": [[.5, .5]], "radius": .1, "erase": False}]})
    era = Mask.model_validate({"strokes": [{"pts": [[.5, .5]], "radius": .1, "erase": True}]})
    wa, we, wn = brush_weight(add, 100, 200), brush_weight(era, 100, 200), brush_weight(Mask(), 100, 200)
    assert wa[50, 100] == 1 and wa[5, 5] == 0
    assert we[50, 100] == 0 and we[5, 5] == 1
    assert wn.min() == 1
    # radio relativo al lado menor (100 px): r=10 px
    assert wa[50, 100 + 12] == 0 and wa[50, 100 + 8] == 1


def test_check_pose_tolerates_mediapipe_z_noise():
    # foto casi frontal con z ruidoso (|dz|/ancho ≈ 1.3, medido en una foto real)
    ok, _, frontal = check_pose(_kp(z_split=0.31), ("abs",), h=H, w=W)
    assert ok == ["abs"] and frontal is True
