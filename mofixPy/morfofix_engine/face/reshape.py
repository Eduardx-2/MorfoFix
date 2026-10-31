"""Face reshape: todos los sliders [proto] en una pasada MLS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from morfofix_engine.face.catalog import split_lr
from morfofix_engine.face.landmark_map import (
    FACE_OVAL,
    GROUPS,
    SKELETON_GROUPS,
    SLIDER_TO_GROUP,
    SliderSpec,
)
from morfofix_engine.warps import mesh as meshmod
from morfofix_engine.warps.mesh import Stroke
from morfofix_engine.warps.mls import border_anchors, mls_remap


@dataclass
class FaceFrame:
    center: np.ndarray
    u: np.ndarray
    perp: np.ndarray  # hacia la izquierda del sujeto (derecha de la imagen)
    half_len: float
    half_w: float


def face_frame(lm_xy: np.ndarray) -> FaceFrame:
    oval = lm_xy[list(FACE_OVAL)]
    center = oval.mean(axis=0)
    axis = lm_xy[152] - lm_xy[10]
    nrm = float(np.linalg.norm(axis))
    u = axis / nrm if nrm > 1e-6 else np.array([0.0, 1.0])
    # u ≈ (0, +y); izquierda del sujeto = +x → perp = (u_y, -u_x)
    perp = np.array([u[1], -u[0]], dtype=np.float64)
    rel = oval - center
    half_len = max(float(np.max(np.abs(rel @ u))), 1.0)
    half_w = max(float(np.max(np.abs(rel @ perp))), 1.0)
    return FaceFrame(center=center, u=u, perp=perp, half_len=half_len, half_w=half_w)


def _profile(t: np.ndarray, name: str) -> np.ndarray:
    if name == "upper":
        return np.clip(-t, 0.0, 1.0)
    if name == "lower":
        return np.clip(t, 0.0, 1.0)
    if name == "lower2":
        x = np.clip(t, 0.0, 1.0)
        return x * x
    if name == "mid":
        return np.clip(1.0 - np.abs(t), 0.0, 1.0)
    return np.ones_like(t)


def slider_displacements(
    lm_xy: np.ndarray,
    spec: SliderSpec,
    value: float,
    side: str | None,
) -> np.ndarray:
    """Desplazamientos (N,2) en píxeles para un slider."""
    d = np.zeros_like(lm_xy, dtype=np.float64)
    if abs(value) < 1e-8:
        return d
    fr = face_frame(lm_xy)
    v = float(value)
    s = spec.strength
    idxs: list[int] = []
    for g in spec.groups:
        if side == "left" and g.endswith("_R"):
            continue
        if side == "right" and g.endswith("_L"):
            continue
        idxs.extend(GROUPS[g])
    if not idxs:
        return d
    uniq = np.unique(np.array(idxs, dtype=np.int32))
    pts = lm_xy[uniq]
    rel = pts - fr.center
    t = (rel @ fr.u) / fr.half_len
    prof = _profile(t, spec.profile)
    lat = rel @ fr.perp  # >0 = izquierda del sujeto
    if side == "left":
        keep = lat >= -1e-6
        uniq, pts, rel, t, prof, lat = uniq[keep], pts[keep], rel[keep], t[keep], prof[keep], lat[keep]
    elif side == "right":
        keep = lat <= 1e-6
        uniq, pts, rel, t, prof, lat = uniq[keep], pts[keep], rel[keep], t[keep], prof[keep], lat[keep]
    if len(uniq) == 0:
        return d

    if spec.mode in {"corner", "lateral"}:
        outward=np.sign(lat)[:,None]*fr.perp
        d[uniq]=v*s*fr.half_w*outward
        if spec.mode=="corner":
            d[uniq]-=v*s*fr.half_len*fr.u
    elif spec.mode=="curve":
        local=pts-pts.mean(axis=0)
        lateral=local@fr.perp
        t=lateral/max(np.max(np.abs(lateral)),1)
        d[uniq]=v*s*fr.half_len*(1-t*t)[:,None]*fr.u
    elif spec.mode=="chin_scale":
        d[uniq]=v*s*(pts-lm_xy[152])
    elif spec.mode == "translate":
        d[uniq] = v*s*fr.half_len*prof[:,None]*fr.u
    elif spec.mode in {"aniso", "aniso_y", "rotate"}:
        c = pts.mean(axis=0)
        local = pts-c
        if spec.mode == "rotate":
            angle = np.deg2rad(8*v)
            rot = np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
            d[uniq] = local@rot.T-local
        else:
            axis = fr.perp if spec.mode == "aniso" else fr.u
            d[uniq] = v*s*np.outer(local@axis,axis)
    elif spec.mode == "axis":
        lateral = np.outer(lat, fr.perp)
        d[uniq] = -v * s * lateral * prof[:, None]
    elif spec.mode == "vshape":
        lateral = np.outer(lat, fr.perp)
        d[uniq] = -v * s * lateral * prof[:, None]
        d[152] = d[152] + v * (0.125 if side else 0.25) * s * fr.half_len * fr.u
    elif spec.mode == "length":
        d[uniq] = v * s * fr.half_len * prof[:, None] * fr.u[None, :]
    elif spec.mode == "scale":
        c = pts.mean(axis=0)
        d[uniq] = v * s * (pts - c)
    elif spec.mode == "distance":
        c = pts.mean(axis=0)
        direction = c - fr.center
        n = float(np.linalg.norm(direction))
        unit = direction / n if n > 1e-6 else fr.perp
        d[uniq] = v * s * fr.half_w * unit
    return d


def build_controls(
    lm_xy: np.ndarray,
    disp: np.ndarray,
    img_wh: tuple[int, int],
    moved_groups: set[str],
) -> tuple[np.ndarray, np.ndarray]:
    w, h = img_wh
    mag = np.linalg.norm(disp, axis=1)
    moved = mag > 0.05
    src_list: list[np.ndarray] = []
    dst_list: list[np.ndarray] = []
    if np.any(moved):
        src_list.append(lm_xy[moved])
        dst_list.append(lm_xy[moved] + disp[moved])

    # esqueleto fijo: grupos no movidos
    used = set()
    for g in SKELETON_GROUPS:
        if g in moved_groups:
            continue
        for idx in GROUPS[g]:
            if idx in used or moved[idx]:
                continue
            used.add(idx)
            src_list.append(lm_xy[idx : idx + 1])
            dst_list.append(lm_xy[idx : idx + 1])

    # anillos de anclas alrededor de grupos movidos
    for g in moved_groups:
        spec_ring = 1.35
        for spec in SLIDER_TO_GROUP.values():
            if g in spec.groups:
                spec_ring = spec.ring
                break
        pts = lm_xy[list(GROUPS[g])]
        c = pts.mean(axis=0)
        ring = c + spec_ring * (pts - c)
        src_list.append(ring)
        dst_list.append(ring)

    border = border_anchors(h, w, per_side=8)
    src_list.append(border)
    dst_list.append(border)

    src = np.concatenate(src_list, axis=0)
    dst = np.concatenate(dst_list, axis=0)

    if np.any(moved):
        moved_pts = lm_xy[moved]
        moved_d = mag[moved]
        thresh = np.maximum(3.0, 1.5 * moved_d)
        keep = np.ones(len(src), dtype=bool)
        n_moved = int(np.count_nonzero(moved))
        # no tirar los propios puntos movidos (están al inicio)
        for i in range(n_moved, len(src)):
            delta = src[i] - moved_pts
            dist = np.linalg.norm(delta, axis=1)
            if np.any(dist < thresh):
                keep[i] = False
        src, dst = src[keep], dst[keep]
    return src, dst


def controls_from_params(
    lm_norm: np.ndarray,
    params: Mapping[str, float],
    img_wh: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, int]:
    w, h = img_wh
    xy = np.stack([lm_norm[:, 0] * (w - 1), lm_norm[:, 1] * (h - 1)], axis=1).astype(np.float64)
    disp = np.zeros_like(xy)
    moved_groups: set[str] = set()
    # Evaluate each anatomical side once, after adding and clamping base + L/R.
    bases = sorted({split_lr(name)[0] for name in params})
    for base in bases:
        spec = SLIDER_TO_GROUP.get(base)
        if spec is None:
            continue
        sides = ("left", "right") if spec.lr else (None,)
        for side in sides:
            value = np.clip(params.get(base,0) + (params.get(side+"_"+base,0) if side else 0), -1,1)
            if not value:
                continue
            # Eye/brow groups must scale around their own center, not between eyes.
            groups = [g for g in spec.groups if not (side=="left" and g.endswith("_R")) and not (side=="right" and g.endswith("_L"))]
            from dataclasses import replace
            for group in groups:
                disp += slider_displacements(xy, replace(spec,groups=(group,)),float(value),side)
                moved_groups.add(group)
    src, dst = build_controls(xy, disp, img_wh, moved_groups)
    n_moved = int(np.count_nonzero(np.linalg.norm(disp, axis=1) > 0.05))
    return src, dst, n_moved


def apply_face_params(
    img: np.ndarray,
    lm_norm: np.ndarray,
    params: Mapping[str, float],
    interpolation: int = 1,
) -> np.ndarray:
    h, w = img.shape[:2]
    src, dst, n_moved = controls_from_params(lm_norm, params, (w, h))
    if n_moved >= 4:
        return mls_remap(img, src, dst, interpolation=interpolation)
    # fallback liquify radial
    strokes: list[Stroke] = []
    mag = np.linalg.norm(dst[: max(n_moved, 1)] - src[: max(n_moved, 1)], axis=1) if n_moved else []
    if n_moved:
        xy_src = src[:n_moved]
        xy_dst = dst[:n_moved]
        for p0, p1 in zip(xy_src, xy_dst):
            strokes.append(
                Stroke(
                    p0=(float(p0[0] / max(w - 1, 1)), float(p0[1] / max(h - 1, 1))),
                    p1=(float(p1[0] / max(w - 1, 1)), float(p1[1] / max(h - 1, 1))),
                    k=0.15,
                    radius=0.03,
                )
            )
        return meshmod.apply_warp(img, strokes, interpolation=interpolation)
    return img


def jaw_width_px(lm_norm: np.ndarray, width: int, height: int) -> float:
    from morfofix_engine.face.landmark_map import JAW

    xy = np.stack([lm_norm[:, 0] * (width - 1), lm_norm[:, 1] * (height - 1)], axis=1)
    jaw = xy[list(JAW)]
    return float(jaw[:, 0].max() - jaw[:, 0].min())


def warped_landmarks(lm_norm: np.ndarray, params: Mapping[str, float], img_wh: tuple[int, int]) -> np.ndarray:
    w, h = img_wh
    xy = np.stack([lm_norm[:, 0] * (w - 1), lm_norm[:, 1] * (h - 1)], axis=1).astype(np.float64)
    disp = np.zeros_like(xy)
    for raw_name, val in params.items():
        base, side = split_lr(raw_name)
        spec = SLIDER_TO_GROUP.get(base)
        if spec is None:
            continue
        disp += slider_displacements(xy, spec, float(val), side)
    out = lm_norm.copy()
    out[:, 0] = (xy[:, 0] + disp[:, 0]) / max(w - 1, 1)
    out[:, 1] = (xy[:, 1] + disp[:, 1]) / max(h - 1, 1)
    return out
