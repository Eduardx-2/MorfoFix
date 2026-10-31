"""Freeze: raster de trazos y mix(orig, warped, mask) [RE]."""

from __future__ import annotations

import cv2
import numpy as np

from morfofix_engine.core.state import BrushStroke


def rasterize_strokes(
    strokes: list[BrushStroke],
    h: int,
    w: int,
    mask: np.ndarray | None = None,
    ref: str = "max",
) -> np.ndarray:
    """Máscara float32 [0,1]. erase resta.

    `ref` define a qué lado se refiere `radius`: "max" (retoque/borrar, histórico)
    o "min" (congelar: radio hasta 0.5 = medio lado menor, igual que el cursor).
    """
    mask = np.zeros((h, w), dtype=np.float32) if mask is None else mask
    side = min(h, w) if ref == "min" else max(h, w)
    for st in strokes:
        layer = np.zeros((h, w), dtype=np.uint8)
        r_px = max(1, int(round(st.radius * side)))
        pts = []
        for x, y in st.pts:
            pts.append((int(round(x * (w - 1))), int(round(y * (h - 1)))))
        if len(pts) == 1:
            cv2.circle(layer, pts[0], r_px, 255, thickness=-1, lineType=cv2.LINE_AA)
        else:
            cv2.polylines(layer, [np.array(pts, dtype=np.int32)], False, 255, thickness=max(1, r_px * 2), lineType=cv2.LINE_AA)
            for p in pts:
                cv2.circle(layer, p, r_px, 255, thickness=-1, lineType=cv2.LINE_AA)
        m = layer.astype(np.float32) / 255.0
        if st.erase:
            mask = np.clip(mask - m, 0.0, 1.0)
        else:
            mask = np.clip(mask + m, 0.0, 1.0)
    return mask


def freeze_mask(strokes: list[BrushStroke], h: int, w: int) -> np.ndarray:
    return rasterize_strokes(strokes, h, w)


def freeze_mask_from_state(freeze, h: int, w: int, max_side: int = 1024) -> np.ndarray:
    """Máscara de congelado completa (trazos + rects + feather + invertir).

    Se rasteriza con el aspecto real (no en 1001×1001 como antes, que deformaba
    los círculos en elipses) a ≤ max_side y se reescala a (h, w).
    """
    scale = min(1.0, max_side / float(max(h, w)))
    rh, rw = max(1, round(h * scale)), max(1, round(w * scale))
    strokes = [BrushStroke(s.pts, s.radius, s.erase) for s in getattr(freeze, "strokes", [])]
    mask = rasterize_strokes(strokes, rh, rw, ref="min")
    for r in getattr(freeze, "rects", []) or []:
        x0 = int(round(r.x * (rw - 1)))
        y0 = int(round(r.y * (rh - 1)))
        x1 = int(round(min(1.0, r.x + r.w) * (rw - 1)))
        y1 = int(round(min(1.0, r.y + r.h) * (rh - 1)))
        if r.erase:
            mask[y0:y1 + 1, x0:x1 + 1] = 0.0
        else:
            mask[y0:y1 + 1, x0:x1 + 1] = 1.0
    if getattr(freeze, "invert", False):
        mask = 1.0 - mask
    feather = float(getattr(freeze, "feather", 0) or 0)
    if feather > 0:
        sigma = max(0.5, feather * min(rh, rw) / 2.0)
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REPLICATE)
    if (rh, rw) != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(mask, 0.0, 1.0).astype(np.float32)


def sample_frozen_grid(mask: np.ndarray, n: int = 126) -> np.ndarray:
    return cv2.resize(mask.astype(np.float32), (n, n), interpolation=cv2.INTER_LINEAR)


def mix_orig_warped(orig: np.ndarray, warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """mix(orig, warped, mask) — fórmula de producto [RE] 03 §6."""
    m = mask.astype(np.float32)
    if m.ndim == 2:
        m = m[..., None]
    out = orig.astype(np.float32) * (1.0 - m) + warped.astype(np.float32) * m
    return np.clip(out, 0, 255).astype(np.uint8)
