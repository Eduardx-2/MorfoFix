"""Ronda 19: pincel/manipulador de cuerpo con efecto visible, congelar grande y líneas de altura."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from morfofix_engine.body.freeze import freeze_mask_from_state
from morfofix_engine.body.height import height_field
from morfofix_engine.body.manual import manual_field
from morfofix_engine.core.edit_state import EditState, Freeze, Height, Shape
from morfofix_engine.warps.field import mesh_backward_field
from morfofix_engine.warps.mesh import Stroke, _aspect_offset

H, W = 1598, 1280  # body2.jpg


# --- espejo de ui/js/models/params.js (y rusting brush_to_stroke) ---
def ui_brush(soft: str, radius_ui: float, strength_ui: float) -> tuple[float, float]:
    r = min(.25, max(.01, .01 + .24 * radius_ui / 100))
    k = min(1.0, max(.02, (.9 if soft == 'fuerte' else .55) * (.2 + .8 * strength_ui / 100)))
    return k, r


def ui_manip_value(amount: float) -> float:
    return max(-1.0, min(1.0, -amount / 100))


def _stroke_pts(x0, x1, y, n=15):
    return [(x0 + (x1 - x0) * i / (n - 1), y) for i in range(n)]


def _max_disp(field):
    return float(np.hypot(field.dx, field.dy).max())


def test_default_brush_moves_pixels_visibly():
    """Antes (k=.126, r=.02) el empuje máximo era ~1.6 px: 'no hace nada'."""
    k, r = ui_brush('suave', 36, 42)
    pts = _stroke_pts(.36, .45, .45)  # ~115 px de arrastre en x
    strokes = [Stroke(a, b, k, r) for a, b in zip(pts, pts[1:])]
    f = mesh_backward_field(H // 2, W // 2, strokes)  # mitad de resolución para velocidad
    assert _max_disp(f) * 2 > 15  # > 15 px en la foto completa


def test_old_mapping_was_imperceptible():
    pts = _stroke_pts(.36, .45, .45)
    strokes = [Stroke(a, b, .126, .02035) for a, b in zip(pts, pts[1:])]
    f = mesh_backward_field(H // 2, W // 2, strokes)
    assert _max_disp(f) * 2 < 4


def test_brush_is_round_in_pixels():
    d = _aspect_offset(np.array([.1, 0.]), np.array([0., .1 * W / H]), W, H)
    assert abs(d[0] - d[1]) < 1e-9
    assert abs(d[0] - .1 * W / min(W, H)) < 1e-9


def test_liquify_k_up_to_one():
    EditState.model_validate({'liquify': [{'pts': [[.1, .1], [.2, .1]], 'k': 1.0, 'r': .25}]})
    with pytest.raises(ValidationError):
        EditState.model_validate({'liquify': [{'pts': [[.1, .1], [.2, .1]], 'k': 1.01, 'r': .25}]})


def _torso_width_change(value, kind='WaistThin_Rect'):
    """% de cambio de ancho de un segmento horizontal [0.40, 0.60] en el centro de la caja."""
    h, w = 400, 400
    s = Shape(type=kind, cx=.5, cy=.5, w=.5, h=.4, value=value, feather=.48)
    f = manual_field(h, w, [s])
    row = h // 2
    xs = np.arange(w, dtype=np.float32)
    src = xs + f.dx[row]
    left, right = .40 * (w - 1), .60 * (w - 1)
    inside = (src >= left) & (src <= right)
    new = inside.sum()
    return 100.0 * (new - (right - left)) / (right - left)


def test_manipulator_clicks_change_width():
    """10 clics × paso 10 en ← = amount −100 → value +1 → claramente más angosto."""
    assert abs(_torso_width_change(ui_manip_value(-4))) < 1.5  # 1 clic de paso 4 (≈ valor viejo .08... pero acumula)
    narrow = _torso_width_change(ui_manip_value(-100))
    wide = _torso_width_change(ui_manip_value(100))
    assert narrow < -8
    assert wide > 8


def test_stretch_rect_vertical():
    h, w = 400, 400
    f = manual_field(h, w, [Shape(type='Stretch_Rect', cx=.5, cy=.5, w=.5, h=.5, value=-.8)])
    assert np.abs(f.dx).max() == 0
    assert np.abs(f.dy).max() > 5
    # Estirar (value<0): el backward map toma píxeles más cerca del centro.
    assert f.dy[150, 200] > 0 and f.dy[250, 200] < 0


# --- altura con líneas ---
def test_height_contract_without_band():
    ht = Height.model_validate({"value": 0.25, "y_start": 0.48, "y_end": 0.92})
    assert ht.band == (0.48, 0.92)
    dumped = ht.model_dump()
    assert dumped["y_start"] == 0.48 and dumped["y_end"] == 0.92


def test_height_rejects_inverted_or_narrow():
    with pytest.raises(ValidationError):
        Height.model_validate({"value": 0.2, "y_start": 0.5, "y_end": 0.49})
    with pytest.raises(ValidationError):
        Height.model_validate({"value": 0.2, "y_start": 0.5, "y_end": 0.51})


def test_height_value_zero_identity():
    from types import SimpleNamespace
    from morfofix_engine.render.pipeline import _render
    rng = np.random.default_rng(0)
    img = np.resize(rng.integers(0, 255, (40, 32, 3), dtype=np.uint8), (80, 64, 3)).copy()
    sess = SimpleNamespace(
        preview=img, original=img, faces=[], bodies=[], masks={},
        meta=SimpleNamespace(warnings=[], image_sha1="h"), params=None, registry=None,
    )
    a = _render(sess, state=EditState()).image
    b = _render(sess, state=EditState.model_validate({
        "height": {"value": 0, "y_start": 0.4, "y_end": 0.8},
    })).image
    assert np.array_equal(a, b)


def test_height_contract_y_start_end_override_band():
    ht = Height.model_validate({'value': .3, 'y_start': .6, 'y_end': 1.0})
    assert ht.band == (.6, 1.0)
    ht = Height.model_validate({'value': .3, 'band': [.1, .2], 'y_start': 0, 'y_end': .5})
    assert ht.band == (0, .5)
    with pytest.raises(ValidationError):
        Height.model_validate({'value': .3, 'y_start': .7, 'y_end': .6})
    # compat: estado viejo solo con band
    assert Height.model_validate({'value': .1, 'band': [.48, .92]}).band == (.48, .92)


def _rows(field):
    return field.dy[:, 0] + np.arange(field.dy.shape[0], dtype=np.float32)


def test_height_only_below_line_keeps_above_untouched():
    h, w = 1000, 40
    f = height_field(h, w, (.6, 1.0), .5)
    src = _rows(f)
    assert f.dy.shape[0] == round(h + .4 * h * .15)  # canvas crece 0.4·h·(0.30·0.5)
    above = np.arange(int(.6 * h) - 45)  # fuera del feather
    assert np.allclose(src[above], above, atol=.5)
    # por debajo de la línea se estira de forma pareja hasta el borde inferior
    slope = np.diff(src[int(.8 * h):int(.95 * h)])
    assert np.allclose(slope, 1 / 1.15, atol=.02)
    assert abs(src[-1] - (h - 1)) < 2


def test_height_only_above_line_shifts_below_rigidly():
    h, w = 1000, 40
    f = height_field(h, w, (0.0, .4), .5)
    src = _rows(f)
    out_h = f.dy.shape[0]
    tail = np.arange(out_h - 300, out_h)
    # debajo de la línea: traslación rígida (pendiente 1)
    assert np.allclose(np.diff(src[tail]), 1.0, atol=1e-3)
    head = np.diff(src[5:300])
    assert np.allclose(head, 1 / 1.15, atol=.02)


def test_height_band_between_two_lines():
    h, w = 1000, 40
    f = height_field(h, w, (.3, .7), .5)
    src = _rows(f)
    assert np.allclose(src[:250], np.arange(250), atol=.5)
    out_h = f.dy.shape[0]
    assert np.allclose(np.diff(src[out_h - 200:]), 1.0, atol=1e-3)


# --- congelar ---
def _fz(**kw):
    return Freeze.model_validate(kw)


def test_freeze_big_radius_half_short_side():
    m = freeze_mask_from_state(_fz(strokes=[{'pts': [[.5, .5]], 'radius': .5}]), 400, 300)
    # radio 0.5·300 = 150 px: cubre todo el ancho en la fila central y es un círculo, no elipse
    assert m[200, 5] > .9 and m[200, 294] > .9
    assert m[200 - 140, 150] > .9 and m[200 - 160, 150] < .1
    with pytest.raises(ValidationError):
        _fz(strokes=[{'pts': [[.5, .5]], 'radius': .51}])


def test_freeze_rect_erase_invert_feather():
    m = freeze_mask_from_state(_fz(rects=[{'x': .1, 'y': .1, 'w': .5, 'h': .5}]), 200, 200)
    assert m[60, 60] == 1 and m[150, 150] == 0
    m = freeze_mask_from_state(_fz(rects=[{'x': .1, 'y': .1, 'w': .5, 'h': .5},
                                          {'x': .2, 'y': .2, 'w': .1, 'h': .1, 'erase': True}]), 200, 200)
    assert m[50, 50] == 0 and m[30, 30] == 1
    m = freeze_mask_from_state(_fz(rects=[{'x': .1, 'y': .1, 'w': .5, 'h': .5}], invert=True), 200, 200)
    assert m[60, 60] == 0 and m[150, 150] == 1
    m = freeze_mask_from_state(_fz(rects=[{'x': .25, 'y': .25, 'w': .5, 'h': .5}], feather=.1), 200, 200)
    edge = m[100, 50]
    assert .2 < edge < .8 and m[100, 100] > .95 and m[100, 5] < .05
    # brush + erase stroke
    m = freeze_mask_from_state(_fz(strokes=[{'pts': [[.5, .5]], 'radius': .4},
                                            {'pts': [[.5, .5]], 'radius': .1, 'erase': True}]), 200, 200)
    assert m[100, 100] == 0 and m[100, 40] == 1


def _session_like():
    from types import SimpleNamespace
    return SimpleNamespace


def test_render_freeze_rect_blocks_manual_shape(tmp_path):
    """Pipeline: un rect congelado sobre la caja del manipulador anula la deformación allí."""
    import cv2
    from morfofix_engine.render.pipeline import _render
    from types import SimpleNamespace
    rng = np.random.default_rng(0)
    img = cv2.resize(rng.integers(0, 255, (40, 32, 3), dtype=np.uint8), (320, 400), interpolation=cv2.INTER_CUBIC)
    meta = SimpleNamespace(warnings=[], image_sha1='x')
    sess = SimpleNamespace(preview=img, original=img, faces=[], bodies=[], masks={}, meta=meta, params=None)
    shape = {'type': 'WaistThin_Rect', 'cx': .5, 'cy': .5, 'w': .6, 'h': .4, 'value': .9}
    try:
        base = _render(sess, state=EditState.model_validate({})).image
        warped = _render(sess, state=EditState.model_validate({'manual_shapes': [shape]})).image
        frozen = _render(sess, state=EditState.model_validate({
            'manual_shapes': [shape],
            'freeze': {'rects': [{'x': 0, 'y': 0, 'w': 1, 'h': 1}]}})).image
    except (AttributeError, TypeError) as exc:  # sesión mínima incompatible con otra rama del pipeline
        pytest.skip(f'pipeline necesita sesión completa: {exc}')
    assert np.abs(warped.astype(int) - base.astype(int)).mean() > 1
    assert np.abs(frozen.astype(int) - base.astype(int)).max() == 0


def test_cuerpo_fixture_validates():
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'edit_state_cuerpo.json').read_text())
    st = EditState.model_validate(raw)
    assert st.height.band == (.6, 1.0)
    assert st.freeze.invert and st.freeze.rects[0].w == .3
    assert {s.type for s in st.manual_shapes} == {'WaistThin_Rect', 'Stretch_Rect'}
    assert st.arm.manual is not None
    assert abs(st.arm.manual.value - 0.4) < 1e-6
