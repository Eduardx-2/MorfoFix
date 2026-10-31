"""MLS similarity (Schaefer, McPhail, Warren 2006) [proto]."""

from __future__ import annotations

import numpy as np
import cv2


def border_anchors(h: int, w: int, per_side: int = 8) -> np.ndarray:
    xs = np.linspace(0, w - 1, per_side, dtype=np.float64)
    ys = np.linspace(0, h - 1, per_side, dtype=np.float64)
    top = np.stack([xs, np.zeros(per_side)], axis=1)
    bot = np.stack([xs, np.full(per_side, h - 1)], axis=1)
    lef = np.stack([np.zeros(per_side), ys], axis=1)
    rig = np.stack([np.full(per_side, w - 1), ys], axis=1)
    return np.concatenate([top, bot, lef, rig], axis=0)


def _as_complex(pts: np.ndarray) -> np.ndarray:
    p = np.asarray(pts, dtype=np.float64)
    return p[..., 0] + 1j * p[..., 1]


def mls_points(
    query: np.ndarray,
    src: np.ndarray,
    dst: np.ndarray,
    alpha: float = 1.0,
    mode: str = "similarity",
) -> np.ndarray:
    """Evalúa f(v) en `query` (N,2) dados controles src/dst (K,2)."""
    v = _as_complex(query)[:, None]  # (N,1)
    p = _as_complex(src)[None, :]  # (1,K)
    q = _as_complex(dst)[None, :]
    diff = p - v
    dist2 = diff.real**2 + diff.imag**2
    # coincidencia exacta: el control se mapea a su dst
    exact = dist2 < 1e-12
    dist2 = np.where(exact, 1.0, dist2)
    w = 1.0 / np.power(dist2, alpha)
    w = np.where(exact, 0.0, w)
    sw = np.sum(w, axis=1, keepdims=True)
    sw = np.where(sw == 0, 1.0, sw)
    pstar = np.sum(w * p, axis=1, keepdims=True) / sw
    qstar = np.sum(w * q, axis=1, keepdims=True) / sw
    phat = p - pstar
    qhat = q - qstar
    phat_abs2 = phat.real**2 + phat.imag**2
    denom = np.sum(w * phat_abs2, axis=1, keepdims=True)
    denom = np.where(denom == 0, 1.0, denom)
    a = np.sum(w * np.conj(phat) * qhat, axis=1, keepdims=True) / denom
    if mode == "rigid":
        mag = np.abs(a)
        mag = np.where(mag == 0, 1.0, mag)
        a = a / mag
    fv = a * (v - pstar) + qstar
    out = np.column_stack([fv[:, 0].real, fv[:, 0].imag])
    # puntos exactamente sobre un control
    if np.any(exact):
        # exact[n,k]
        hits = np.argmax(exact, axis=1)
        any_hit = np.any(exact, axis=1)
        dst_pts = np.asarray(dst, dtype=np.float64)
        out[any_hit] = dst_pts[hits[any_hit]]
    return out


def build_maps(
    h: int,
    w: int,
    src: np.ndarray,
    dst: np.ndarray,
    grid_step: int = 8,
    alpha: float = 1.0,
    mode: str = "similarity",
) -> tuple[np.ndarray, np.ndarray]:
    """Mapas dst→src (backward) en grilla gruesa + upsample bilinear."""
    ny = max(2, int(np.ceil((h - 1) / grid_step)) + 1)
    nx = max(2, int(np.ceil((w - 1) / grid_step)) + 1)
    ys = np.linspace(0, h - 1, ny, dtype=np.float64)
    xs = np.linspace(0, w - 1, nx, dtype=np.float64)
    gx, gy = np.meshgrid(xs, ys)
    query = np.stack([gx.ravel(), gy.ravel()], axis=1)
    # backward: roles invertidos (queremos src dado dest=query)
    sampled = np.concatenate([mls_points(chunk, dst, src, alpha=alpha, mode=mode) for chunk in np.array_split(query, max(1, int(np.ceil(len(query)/2048))))])
    gh, gw = gy.shape
    coarse = sampled.reshape(gh, gw, 2).astype(np.float64)
    maps = _upsample_field(coarse, xs, ys, w, h)
    return maps[..., 0].astype(np.float32), maps[..., 1].astype(np.float32)


def _upsample_field(coarse: np.ndarray, xs: np.ndarray, ys: np.ndarray, w: int, h: int) -> np.ndarray:
    """Bilinear usando las coords reales de la grilla gruesa (no cv2.resize)."""
    # Separable bilinear interpolation avoids four full-resolution float64
    # corner arrays. Grid positions still use actual endpoints, not resize.
    coarse=np.asarray(coarse,dtype=np.float32)
    ix=np.interp(np.arange(w),xs,np.arange(len(xs)))
    iy=np.interp(np.arange(h),ys,np.arange(len(ys)))
    x0=np.floor(ix).astype(np.int32); x1=np.minimum(x0+1,len(xs)-1)
    y0=np.floor(iy).astype(np.int32); y1=np.minimum(y0+1,len(ys)-1)
    tx=(ix-x0).astype(np.float32)[None,:,None]
    ty=(iy-y0).astype(np.float32)[:,None,None]
    horizontal=coarse[:,x0]*(1-tx)+coarse[:,x1]*tx
    return horizontal[y0]*(1-ty)+horizontal[y1]*ty


def mls_remap(
    img: np.ndarray,
    src: np.ndarray,
    dst: np.ndarray,
    grid_step: int = 8,
    interpolation: int = cv2.INTER_LINEAR,
) -> np.ndarray:
    if len(src) < 2:
        return img
    h, w = img.shape[:2]
    map_x, map_y = build_maps(h, w, src, dst, grid_step=grid_step)
    return cv2.remap(img, map_x, map_y, interpolation=interpolation, borderMode=cv2.BORDER_REPLICATE)
