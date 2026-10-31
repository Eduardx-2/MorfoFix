"""Pose-anchored muscle relief: height map, skin mask, shading and light warp."""
from __future__ import annotations

import cv2
import numpy as np

from morfofix_engine.body.freeze import rasterize_strokes
from morfofix_engine.body.muscle_catalog import MUSCLE_ALIAS, MUSCLE_MODES, REQUIRED_KP
from morfofix_engine.body.relief import apply_gloss, apply_relief, dome, estimate_light, groove, ridge, shade
from morfofix_engine.core.state import BrushStroke
from morfofix_engine.warps.field import attenuate, compose, identity, local_scale

# Design proportions in the torso frame (a across, b along O→S).
ABS_DOME_A = 0.18
ABS_DOME_B = (0.10, 0.28, 0.46)
ABS_DOME_RX = 0.15
ABS_DOME_RY = 0.08
ABS_GROOVE_B = (0.05, 0.62)
ABS_HGROOVE_B = (0.19, 0.37)
ABS_HGROOVE_A = 0.33
ABS_RIDGE_FROM = (0.45, 0.05)
ABS_RIDGE_TO = (0.25, 0.50)
ABLINE_DEPTH = 0.5
CHEST_DOME_A = 0.25
CHEST_DOME_B = 0.80
CHEST_DOME_RX = 0.26
CHEST_DOME_RY = 0.13
CHEST_DOME_THETA = np.deg2rad(8.0)
CHEST_STERNUM_B = (0.68, 0.95)
CHEST_UNDER_B = 0.68
BUST_UNDER_B = 0.62
BUST_UNDER_A = 0.32
BUST_DEPTH = 0.4
BUST_WARP_A = 0.22
BUST_WARP_B = 0.72
ARM_THICK = 0.28
LEG_THIGH_THICK = 0.45
LEG_CALF_THICK = 0.32
DELTOID_T = (0.05, 0.25)
BICEPS_T = (0.35, 0.80)
FOREARM_T = (0.10, 0.40)
VASTUS_T = (0.55, 0.90)
CALF_T = (0.10, 0.45)
BODY_WEIGHTS = {"chest": 0.7, "abs": 0.8, "arm": 0.6, "leg": 0.6}
WARP_AMOUNT = 0.04
BUST_WARP_AMOUNT = 0.06
GAIN = 0.35
OCCL = 0.25
GLOSS_GAIN = 0.08
# Doc 23: "definición" real = realce de banda media (contornos musculares que ya están en la foto),
# no de alta frecuencia (poros/vello). Sigmas en fracción del tamaño del torso T.
CLARITY_GAIN = 1.6
CLARITY_S = (0.006, 0.03)
NORMAL_K = 4.0
MAX_SIDE = 768
SHADE_R = 0.01
VIS_MIN = 0.5
FRONTAL_RATIO = 0.35
# z de MediaPipe Pose es ruidoso: con 0.25 una foto casi frontal (|dz|/ancho ≈ 1.3)
# quedaba "no frontal" y Músculo no hacía nada. El perfil real lo corta FRONTAL_RATIO (2D).
FRONTAL_Z = 1.5
COVER_MIN = 0.35
CLOTHES_GAIN = 0.2
GROOVE_W_FRAC = 0.04
RIDGE_W_FRAC = 0.05

LIGHT_DIRS = {
    "top": np.array([0.0, -0.6, 0.8], np.float32),
    "left": np.array([-0.6, -0.3, 0.74], np.float32),
    "right": np.array([0.6, -0.3, 0.74], np.float32),
}

_WOMAN = set()


def _kp_xy(kp, h, w):
    scale = np.array([max(w - 1, 1), max(h - 1, 1)], np.float32)
    return np.asarray(kp[:, :2], np.float32) * scale


def _unit(vec):
    v = np.asarray(vec, np.float32)
    n = float(np.linalg.norm(v))
    return v / max(n, 1e-6)


def check_pose(kp, parts, *, vis=VIS_MIN, h=1, w=1):
    """Return (ok_parts, missing_kp, frontal) for the requested muscle parts."""
    kp = np.asarray(kp, np.float32)
    ok, missing = [], []
    for part in parts:
        req = REQUIRED_KP[part]
        bad = [i for i in req if float(kp[i, 3]) < vis]
        if bad:
            missing.extend(bad)
        else:
            ok.append(part)
    missing = sorted(set(missing))
    have = all(float(kp[i, 3]) >= vis for i in (11, 12, 23, 24))
    frontal = False
    if have:
        xy = _kp_xy(kp, h, w)
        shoulder = float(np.hypot(*(xy[11] - xy[12])))
        torso = float(np.hypot(*((xy[11] + xy[12]) / 2 - (xy[23] + xy[24]) / 2)))
        width_n = float(np.hypot(kp[11, 0] - kp[12, 0], kp[11, 1] - kp[12, 1]))
        z_ok = abs(float(kp[11, 2] - kp[12, 2])) <= FRONTAL_Z * max(width_n, 1e-6)
        frontal = torso > 1e-6 and shoulder / torso >= FRONTAL_RATIO and z_ok
    return ok, missing, frontal


def body_frame(kp, h, w):
    """Torso frame in pixels: origin at hips, v toward shoulders, u across."""
    xy = _kp_xy(kp, h, w)
    O = (xy[23] + xy[24]) * 0.5
    S = (xy[11] + xy[12]) * 0.5
    u = _unit(xy[11] - xy[12])
    v = _unit(S - O)
    T = float(np.linalg.norm(S - O))
    W = float(np.linalg.norm(xy[11] - xy[12]))
    return {"O": O, "S": S, "u": u, "v": v, "T": max(T, 1.0), "W": max(W, 1.0)}


def _at(frame, a, b):
    return frame["O"] + np.float32(a) * frame["W"] * frame["u"] + np.float32(b) * frame["T"] * frame["v"]


def _fit(mask, h, w, default=None):
    if mask is None:
        return None if default is None else np.asarray(default, np.float32)
    m = np.asarray(mask, np.float32)
    if m.ndim == 3:
        m = m[:, :, 0]
    if m.shape != (h, w):
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(m, 0.0, 1.0)


def _inward_perp(p0, p1, target):
    t = _unit(np.asarray(p1, np.float32) - np.asarray(p0, np.float32))
    perp = np.array([-t[1], t[0]], np.float32)
    mid = 0.5 * (np.asarray(p0, np.float32) + np.asarray(p1, np.float32))
    if float(np.dot(perp, np.asarray(target, np.float32) - mid)) < 0:
        perp = -perp
    return t, perp


def _seg_dome(h, w, p0, p1, t0, t1, s, thick, height, inward):
    p0 = np.asarray(p0, np.float32)
    p1 = np.asarray(p1, np.float32)
    d = p1 - p0
    length = float(np.linalg.norm(d))
    _, perp = _inward_perp(p0, p1, inward)
    t_hat = _unit(d)
    t_mid = 0.5 * (t0 + t1)
    center = p0 + t_mid * d + np.float32(s) * np.float32(thick) * perp
    rx = max(0.5 * abs(t1 - t0) * length, 1.0)
    ry = max(0.42 * float(thick), 1.0)
    theta = float(np.arctan2(t_hat[1], t_hat[0]))
    return dome(h, w, center, rx, ry, theta, height)


def _seg_groove(h, w, p0, p1, t0, t1, width, depth, s, thick, inward):
    p0 = np.asarray(p0, np.float32)
    p1 = np.asarray(p1, np.float32)
    d = p1 - p0
    _, perp = _inward_perp(p0, p1, inward)
    off = np.float32(s) * np.float32(thick) * perp
    a = p0 + t0 * d + off
    b = p0 + t1 * d + off
    return groove(h, w, a, b, width, depth)


def _support_of(H, eps=0.02):
    return (np.abs(H) > eps).astype(np.float32)


def _abs_map(h, w, frame, height=1.0, depth=1.0):
    W, T = frame["W"], frame["T"]
    H = np.zeros((h, w), np.float32)
    support = np.zeros((h, w), np.float32)
    rx, ry = ABS_DOME_RX * W, ABS_DOME_RY * T
    for a in (-ABS_DOME_A, ABS_DOME_A):
        for b in ABS_DOME_B:
            layer = dome(h, w, _at(frame, a, b), rx, ry, 0.0, height)
            H += layer
            support = np.maximum(support, _support_of(layer, 0.02 * abs(height)))
    gv = groove(h, w, _at(frame, 0.0, ABS_GROOVE_B[0]), _at(frame, 0.0, ABS_GROOVE_B[1]), GROOVE_W_FRAC * W, depth)
    H += gv
    support = np.maximum(support, _support_of(gv, 0.02 * abs(depth)))
    for b in ABS_HGROOVE_B:
        gh = groove(h, w, _at(frame, -ABS_HGROOVE_A, b), _at(frame, ABS_HGROOVE_A, b), GROOVE_W_FRAC * T, depth * 0.7)
        H += gh
        support = np.maximum(support, _support_of(gh, 0.02 * abs(depth)))
    for sign in (-1.0, 1.0):
        rr = ridge(
            h, w,
            _at(frame, sign * ABS_RIDGE_FROM[0], ABS_RIDGE_FROM[1]),
            _at(frame, sign * ABS_RIDGE_TO[0], ABS_RIDGE_TO[1]),
            RIDGE_W_FRAC * W, height * 0.6,
        )
        H += rr
        support = np.maximum(support, _support_of(rr, 0.02 * abs(height)))
    return H, support


def _abline_map(h, w, frame, height=1.0):
    W, T = frame["W"], frame["T"]
    H = groove(
        h, w, _at(frame, 0.0, ABS_GROOVE_B[0]), _at(frame, 0.0, ABS_GROOVE_B[1]),
        GROOVE_W_FRAC * W, ABLINE_DEPTH * height,
    )
    support = _support_of(H, 0.01)
    for sign in (-1.0, 1.0):
        rr = ridge(
            h, w,
            _at(frame, sign * ABS_RIDGE_FROM[0], ABS_RIDGE_FROM[1]),
            _at(frame, sign * ABS_RIDGE_TO[0], ABS_RIDGE_TO[1]),
            RIDGE_W_FRAC * W, 0.5 * height,
        )
        H += rr
        support = np.maximum(support, _support_of(rr, 0.01))
    return H, support


def _chest_map(h, w, frame, height=1.0):
    W, T = frame["W"], frame["T"]
    H = np.zeros((h, w), np.float32)
    support = np.zeros((h, w), np.float32)
    rx, ry = CHEST_DOME_RX * W, CHEST_DOME_RY * T
    for sign, theta in ((-1.0, -CHEST_DOME_THETA), (1.0, CHEST_DOME_THETA)):
        layer = dome(h, w, _at(frame, sign * CHEST_DOME_A, CHEST_DOME_B), rx, ry, theta, height)
        H += layer
        support = np.maximum(support, _support_of(layer, 0.02 * abs(height)))
    gs = groove(
        h, w, _at(frame, 0.0, CHEST_STERNUM_B[0]), _at(frame, 0.0, CHEST_STERNUM_B[1]),
        GROOVE_W_FRAC * W, height,
    )
    H += gs
    support = np.maximum(support, _support_of(gs, 0.02))
    for sign in (-1.0, 1.0):
        gu = groove(
            h, w, _at(frame, 0.0, CHEST_UNDER_B), _at(frame, sign * 0.40, CHEST_UNDER_B - 0.04),
            GROOVE_W_FRAC * T * 1.2, height * 0.7,
        )
        H += gu
        support = np.maximum(support, _support_of(gu, 0.02))
    return H, support


def _bust_map(h, w, frame, height=1.0):
    layer = groove(
        h, w,
        _at(frame, -BUST_UNDER_A, BUST_UNDER_B),
        _at(frame, BUST_UNDER_A, BUST_UNDER_B),
        GROOVE_W_FRAC * frame["T"] * 1.4,
        BUST_DEPTH * height,
    )
    return layer, _support_of(layer, 0.01)


def _arm_map(h, w, kp_xy, frame, height=1.0):
    thick = ARM_THICK * frame["W"]
    inward = frame["O"]
    H = np.zeros((h, w), np.float32)
    support = np.zeros((h, w), np.float32)
    pairs = ((11, 13, 15), (12, 14, 16))
    for sh, el, wr in pairs:
        p0, p1, p2 = kp_xy[sh], kp_xy[el], kp_xy[wr]
        for t0, t1, s, ht in (
            (*DELTOID_T, 0.05, height),
            (*BICEPS_T, 0.28, height * 0.9),
        ):
            layer = _seg_dome(h, w, p0, p1, t0, t1, s, thick, ht, inward)
            H += layer
            support = np.maximum(support, _support_of(layer, 0.02 * abs(ht)))
        gv = _seg_groove(h, w, p0, p1, DELTOID_T[1], BICEPS_T[0], GROOVE_W_FRAC * frame["W"], height * 0.6, 0.12, thick, inward)
        H += gv
        support = np.maximum(support, _support_of(gv, 0.01))
        layer = _seg_dome(h, w, p1, p2, FOREARM_T[0], FOREARM_T[1], 0.1, thick * 0.75, height * 0.55, inward)
        H += layer
        support = np.maximum(support, _support_of(layer, 0.02))
    return H, support


def _leg_map(h, w, kp_xy, frame, height=1.0):
    thigh = LEG_THIGH_THICK * frame["W"]
    calf = LEG_CALF_THICK * frame["W"]
    inward = frame["O"]
    H = np.zeros((h, w), np.float32)
    support = np.zeros((h, w), np.float32)
    pairs = ((23, 25, 27), (24, 26, 28))
    for hip, knee, ankle in pairs:
        p0, p1, p2 = kp_xy[hip], kp_xy[knee], kp_xy[ankle]
        lat = _seg_dome(h, w, p0, p1, VASTUS_T[0], VASTUS_T[1], -0.32, thigh, height, inward)
        med = _seg_dome(h, w, p0, p1, 0.70, 0.95, 0.28, thigh * 0.85, height * 0.85, inward)
        H += lat + med
        support = np.maximum(support, _support_of(lat + med, 0.02 * abs(height)))
        gv = _seg_groove(h, w, p0, p1, 0.12, 0.88, GROOVE_W_FRAC * frame["W"], height * 0.45, 0.05, thigh, inward)
        H += gv
        support = np.maximum(support, _support_of(gv, 0.01))
        gem = _seg_dome(h, w, p1, p2, CALF_T[0], CALF_T[1], 0.05, calf, height * 0.8, inward)
        H += gem
        support = np.maximum(support, _support_of(gem, 0.02))
    return H, support


def _canon_mode(mode):
    return MUSCLE_ALIAS.get(mode, mode)


def _parts_for_mode(mode, ok_parts):
    spec = MUSCLE_MODES[_canon_mode(mode)]
    wanted = set(ok_parts)
    return [p for p in spec.parts if p in wanted]


def height_map(kp, h, w, mode, definition, parts=None):
    """Build a blurred height map and its support, working at ≤768 px."""
    mode = _canon_mode(mode)
    scale = min(1.0, MAX_SIDE / float(max(h, w)))
    hs, ws = max(1, round(h * scale)), max(1, round(w * scale))
    H, support = _height_at(kp, hs, ws, mode, definition, parts)
    if (hs, ws) != (h, w):
        H = cv2.resize(H, (w, h), interpolation=cv2.INTER_LINEAR)
        support = cv2.resize(support, (w, h), interpolation=cv2.INTER_LINEAR)
    return H.astype(np.float32), np.clip(support, 0.0, 1.0).astype(np.float32)


def _height_at(kp, h, w, mode, definition, parts):
    frame = body_frame(kp, h, w)
    xy = _kp_xy(kp, h, w)
    mode = _canon_mode(mode)
    use = _parts_for_mode(mode, parts if parts is not None else MUSCLE_MODES[mode].parts)
    weights = BODY_WEIGHTS if mode == "full_body" else {p: 1.0 for p in use}
    H = np.zeros((h, w), np.float32)
    support = np.zeros((h, w), np.float32)
    builders = {
        "abs": lambda: _abs_map(h, w, frame, weights.get("abs", 1.0)),
        "abline": lambda: _abline_map(h, w, frame, weights.get("abline", 1.0)),
        "chest": lambda: _chest_map(h, w, frame, weights.get("chest", 1.0)),
        "bust": lambda: _bust_map(h, w, frame, weights.get("bust", 1.0)),
        "arm": lambda: _arm_map(h, w, xy, frame, weights.get("arm", 1.0)),
        "leg": lambda: _leg_map(h, w, xy, frame, weights.get("leg", 1.0)),
    }
    for part in use:
        layer, sup = builders[part]()
        H += layer
        support = np.maximum(support, sup)
    sigma = 0.015 * frame["T"] * (1.2 - float(definition))
    if sigma > 0.3:
        k = int(max(3, round(sigma * 6))) | 1
        H = cv2.GaussianBlur(H, (k, k), sigmaX=sigma)
        support = cv2.GaussianBlur(support, (k, k), sigmaX=sigma * 0.6)
    return H, np.clip(support, 0.0, 1.0)


def muscle_mask(masks, support, h, w, brush, T):
    """Skin support minus face/hair, clothes attenuated, then user brush."""
    warnings = []
    raw_skin = _fit(masks.get("body_skin") if masks else None, h, w)
    if raw_skin is None or float(raw_skin.max()) < 1e-6:
        body_skin = _fit((masks or {}).get("person"), h, w, default=np.ones((h, w), np.float32))
        warnings.append("NO_BODY_SKIN_MASK")
        cover_skin = np.zeros((h, w), np.float32)
    else:
        body_skin = raw_skin
        cover_skin = raw_skin
    face_skin = _fit((masks or {}).get("face_skin"), h, w, default=np.zeros((h, w), np.float32))
    hair = _fit((masks or {}).get("hair"), h, w, default=np.zeros((h, w), np.float32))
    clothes = _fit((masks or {}).get("clothes"), h, w, default=np.zeros((h, w), np.float32))
    support = _fit(support, h, w, default=np.zeros((h, w), np.float32))
    k = max(3, int(round(0.15 * float(T))) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    dilated = cv2.dilate((support > 0.05).astype(np.uint8), kernel).astype(np.float32)
    M = body_skin * dilated * (1.0 - face_skin) * (1.0 - hair)
    M = M * (1.0 - (1.0 - CLOTHES_GAIN) * clothes)
    skin_cover = float((cover_skin * support).sum() / max(float(support.sum()), 1e-6))
    if skin_cover < COVER_MIN:
        warnings.append("MUSCLE_OVER_CLOTHES")
    sigma = max(0.4, 0.01 * float(T))
    kblur = int(max(3, round(sigma * 6))) | 1
    M = cv2.GaussianBlur(M, (kblur, kblur), sigmaX=sigma)
    M = np.clip(M * brush_weight(brush, h, w), 0.0, 1.0).astype(np.float32)
    return M, warnings


def brush_weight(brush, h, w):
    """Peso 0..1 del pincel de Músculo.

    Sin trazos: 1 en todo (el modo decide la zona).
    Con algún trazo "Pintar": arranca en 0 y los trazos suman/restan en orden,
    así Pintar LIMITA el efecto a lo pintado (antes arrancaba en 1 y sumar no hacía nada).
    Solo trazos "Borrar": arranca en 1 y restan.
    El radio es fracción del lado MENOR, igual que el cursor de la UI (muscleRadius).
    """
    strokes = list(getattr(brush, "strokes", []) or [])
    if not strokes:
        return np.ones((h, w), np.float32)
    start = np.zeros((h, w), np.float32) if any(not s.erase for s in strokes) else np.ones((h, w), np.float32)
    return rasterize_strokes(
        [BrushStroke(s.pts, s.radius, s.erase) for s in strokes],
        h, w, mask=start, ref="min",
    )


def _warp_centers(kp, h, w, mode, parts):
    frame = body_frame(kp, h, w)
    xy = _kp_xy(kp, h, w)
    centers = []
    use = set(parts)
    if "chest" in use:
        for sign in (-1.0, 1.0):
            centers.append((_at(frame, sign * CHEST_DOME_A, CHEST_DOME_B), WARP_AMOUNT, 0.35 * frame["W"]))
    if "bust" in use:
        for sign in (-1.0, 1.0):
            centers.append((_at(frame, sign * BUST_WARP_A, BUST_WARP_B), BUST_WARP_AMOUNT, 0.32 * frame["W"]))
    if "arm" in use:
        for sh, el in ((11, 13), (12, 14)):
            p0, p1 = xy[sh], xy[el]
            t0, t1 = BICEPS_T
            mid = p0 + 0.5 * (t0 + t1) * (p1 - p0)
            centers.append((mid, WARP_AMOUNT, 0.22 * frame["W"]))
    if "leg" in use:
        for hip, knee in ((23, 25), (24, 26)):
            p0, p1 = xy[hip], xy[knee]
            t0, t1 = VASTUS_T
            mid = p0 + 0.5 * (t0 + t1) * (p1 - p0)
            centers.append((mid, WARP_AMOUNT, 0.38 * frame["W"]))
    return centers


def muscle_field(kp, h, w, mode, strength, warp, parts=None):
    """Light local_scale on pecs/bust/biceps/quads; identity if amount is 0."""
    if float(strength) * float(warp) == 0:
        return identity(h, w)
    mode = _canon_mode(mode)
    parts = parts if parts is not None else list(MUSCLE_MODES[mode].parts)
    f = identity(h, w)
    for center, amount_k, radius in _warp_centers(kp, h, w, mode, parts):
        amount = amount_k * float(strength) * float(warp)
        f = compose(local_scale(h, w, center, radius, amount), f)
    return f


def _torso_mask(kp, h, w):
    frame = body_frame(kp, h, w)
    y, x = np.indices((h, w), dtype=np.float32)
    rel = np.stack((x - frame["O"][0], y - frame["O"][1]), axis=-1)
    a = rel @ frame["u"] / frame["W"]
    b = rel @ frame["v"] / frame["T"]
    return ((np.abs(a) < 0.7) & (b > -0.05) & (b < 1.15)).astype(np.float32)


def _clarity(img, M, T, amount):
    """Realce de banda media en luminancia (DoG), solo dentro de la máscara de músculo."""
    if amount <= 0 or not np.any(M > 0.01):
        return img
    lab = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[:, :, 0]
    s1, s2 = max(1.0, CLARITY_S[0] * T), max(2.0, CLARITY_S[1] * T)
    band = cv2.GaussianBlur(L, (0, 0), s1) - cv2.GaussianBlur(L, (0, 0), s2)
    band = np.clip(band, -40, 40)
    # Sobre ropa M vale ≤ CLOTHES_GAIN: el realce arranca recién por encima, así no "define" la tela.
    wgt = np.clip((M - 1.25 * CLOTHES_GAIN) / 0.5, 0, 1)
    lab[:, :, 0] = np.clip(L + amount * band * wgt, 0, 255)
    bgr = cv2.cvtColor(np.rint(lab).astype(np.uint8), cv2.COLOR_LAB2BGR)
    # Fuera de la máscara se devuelve el píxel original (el viaje a LAB redondea ±2).
    bgr = np.where((wgt > 0)[..., None], bgr, img[:, :, :3])
    return np.dstack((bgr, img[:, :, 3])) if img.shape[2] == 4 else bgr


def apply_muscle(img, bodies, masks, muscle_state):
    """Shade then return a warp field for each person in muscle_state."""
    h, w = img.shape[:2]
    warnings = []
    field = identity(h, w)
    M_all = np.zeros((h, w), np.float32)
    out = img
    for index, cfg in muscle_state.items():
        idx = int(index)
        body = bodies[idx] if 0 <= idx < len(bodies) else None
        kp = None if body is None else getattr(body, "keypoints", None)
        if kp is None or getattr(kp, "shape", None) != (33, 4):
            warnings.append("MUSCLE_SKIPPED:NO_BODY")
            continue
        mode = MUSCLE_ALIAS.get(cfg.mode, cfg.mode)
        spec = MUSCLE_MODES[mode]
        ok_parts, missing, frontal = check_pose(kp, spec.parts, h=h, w=w)
        if not ok_parts or not frontal:
            log = __import__("logging").getLogger("morfofix.muscle")
            log.warning("MUSCLE_SKIPPED:NO_FRONTAL_BODY index=%s missing=%s frontal=%s", idx, missing, frontal)
            warnings.append("MUSCLE_SKIPPED:NO_FRONTAL_BODY")
            continue
        for part in spec.parts:
            if part not in ok_parts:
                warnings.append(f"MUSCLE_PART_SKIPPED:{part}")
        if cfg.strength == 0:
            continue
        frame = body_frame(kp, h, w)
        H, support = height_map(kp, h, w, mode, cfg.definition, parts=ok_parts)
        M, mw = muscle_mask(masks, support, h, w, cfg.brush, frame["T"])
        warnings.extend(mw)
        lab = cv2.cvtColor(out[:, :, :3], cv2.COLOR_BGR2LAB).astype(np.float32)
        L01 = lab[:, :, 0] / 255.0
        if cfg.light == "auto":
            light = estimate_light(L01, M * _torso_mask(kp, h, w))
        else:
            light = LIGHT_DIRS[cfg.light]
        S, A = shade(H, light, NORMAL_K)
        radius = max(1.0, SHADE_R * frame["T"])
        out = apply_relief(out, S, A, M, GAIN * cfg.strength, OCCL * cfg.strength * cfg.definition, radius)
        if cfg.gloss:
            out = apply_gloss(out, H, light, M, GLOSS_GAIN * cfg.strength * cfg.gloss)
        if CLARITY_GAIN:
            out = _clarity(out, M, frame["T"], CLARITY_GAIN * cfg.strength * (0.4 + 0.6 * cfg.definition))
        mf = muscle_field(kp, h, w, mode, cfg.strength, cfg.warp, parts=ok_parts)
        person = _fit((masks or {}).get("person"), h, w)
        if person is not None:
            mf = attenuate(mf, 1.0 - person)
        if getattr(cfg.brush, "strokes", None):
            # El volumen (warp) también respeta la máscara pintada/borrada.
            mf = attenuate(mf, 1.0 - brush_weight(cfg.brush, h, w))
        if np.any(mf.dx) or np.any(mf.dy):
            field = compose(mf, field)
        M_all = np.maximum(M_all, M)
    return out, field, warnings, M_all
