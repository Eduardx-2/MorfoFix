"""Parametric height maps and Lab luminance shading (procedural relief)."""
from __future__ import annotations

import cv2
import numpy as np

from morfofix_engine.retouch.guided import guided_filter

FALLBACK_LIGHT = np.array([-0.3, -0.6, 0.74], np.float32)
OCC_SCALE = 0.25
DARK_L = 0.35


def dome(h, w, center, rx, ry, theta=0., height=1.):
    """Superellipse (1-r²)² inside a rotated ellipse, 0 outside."""
    y, x = np.indices((h, w), dtype=np.float32)
    dx = x - np.float32(center[0])
    dy = y - np.float32(center[1])
    c, s = np.cos(np.float32(theta)), np.sin(np.float32(theta))
    xr = c * dx + s * dy
    yr = -s * dx + c * dy
    r2 = (xr / max(float(rx), 1e-6)) ** 2 + (yr / max(float(ry), 1e-6)) ** 2
    t = np.maximum(0.0, 1.0 - r2)
    return (t * t * np.float32(height)).astype(np.float32)


def groove(h, w, p0, p1, width, depth=1.):
    """Gaussian trough along a segment, peaking at -depth on the line."""
    y, x = np.indices((h, w), dtype=np.float32)
    x0, y0 = np.float32(p0[0]), np.float32(p0[1])
    x1, y1 = np.float32(p1[0]), np.float32(p1[1])
    vx, vy = x1 - x0, y1 - y0
    length2 = vx * vx + vy * vy
    t = np.clip(((x - x0) * vx + (y - y0) * vy) / max(float(length2), 1e-6), 0.0, 1.0)
    dist = np.hypot(x - (x0 + t * vx), y - (y0 + t * vy))
    sigma = max(float(width), 1e-6)
    return (-np.float32(depth) * np.exp(-(dist / sigma) ** 2)).astype(np.float32)


def ridge(h, w, p0, p1, width, height=1.):
    """Gaussian ridge along a segment."""
    return -groove(h, w, p0, p1, width, depth=height)


def normals(H, k):
    """Unit normals from a height map: normalize(-k·dHx, -k·dHy, 1)."""
    H = np.asarray(H, np.float32)
    dHx = cv2.Sobel(H, cv2.CV_32F, 1, 0, ksize=3)
    dHy = cv2.Sobel(H, cv2.CV_32F, 0, 1, ksize=3)
    nx = -np.float32(k) * dHx
    ny = -np.float32(k) * dHy
    nz = np.ones_like(H, dtype=np.float32)
    n = np.stack((nx, ny, nz), axis=-1)
    norm = np.linalg.norm(n, axis=-1, keepdims=True)
    return (n / np.maximum(norm, 1e-8)).astype(np.float32)


def _normalize_light(vec):
    v = np.asarray(vec, np.float32).reshape(3)
    n = float(np.linalg.norm(v))
    return (v / max(n, 1e-8)).astype(np.float32)


def estimate_light(lum, mask):
    """Mean luminance gradient in mask; fallback if the scene is flat."""
    lum = np.asarray(lum, np.float32)
    m = np.clip(np.asarray(mask, np.float32), 0.0, 1.0)
    sigma = max(3.0, 0.02 * max(lum.shape))
    blurred = cv2.GaussianBlur(lum, (0, 0), sigmaX=sigma)
    gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
    weight = float(m.sum())
    if weight < 1e-6:
        return _normalize_light(FALLBACK_LIGHT)
    mx = float((gx * m).sum() / weight)
    my = float((gy * m).sum() / weight)
    g = np.hypot(mx, my)
    if g < 1e-3:
        return _normalize_light(FALLBACK_LIGHT)
    return _normalize_light((mx, my, 0.7))


def shade(H, light, k):
    """Relative shade S in [-1,1] and groove occlusion A in [0,1]."""
    N = normals(H, k)
    L = _normalize_light(light)
    S = np.clip(N @ L - L[2], -1.0, 1.0).astype(np.float32)
    lap = cv2.Laplacian(np.asarray(H, np.float32), cv2.CV_32F)
    A = np.clip(-lap * OCC_SCALE, 0.0, 1.0).astype(np.float32)
    return S, A


def softlight(base, blend):
    """Pegtop soft-light: identity when blend is 0.5."""
    a = np.clip(np.asarray(base, np.float32), 0.0, 1.0)
    b = np.clip(np.asarray(blend, np.float32), 0.0, 1.0)
    return ((1.0 - 2.0 * b) * a * a + 2.0 * b * a).astype(np.float32)


def apply_relief(img_bgr, S, A, mask, gain, occl, radius):
    """Modulate Lab L with shaded base; keep a/b and high-frequency detail."""
    bgr = img_bgr[:, :, :3]
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L01 = lab[:, :, 0] / 255.0
    m = np.clip(np.asarray(mask, np.float32), 0.0, 1.0)
    mean_L = float((L01 * m).sum() / max(float(m.sum()), 1e-6))
    adapt = 1.0 + 0.5 * max(0.0, DARK_L - mean_L) / DARK_L
    r = max(1, int(round(radius)))
    base = guided_filter(L01, L01, radius=r)
    detail = L01 - base
    blend = np.clip(0.5 + float(gain) * adapt * np.asarray(S, np.float32), 0.0, 1.0)
    base2 = softlight(base, blend) * (1.0 - float(occl) * np.asarray(A, np.float32))
    lab[:, :, 0] = np.clip((base2 + detail) * 255.0, 0.0, 255.0)
    shaded = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    mixed = bgr.astype(np.float32) * (1.0 - m[..., None]) + shaded * m[..., None]
    out = np.clip(mixed, 0, 255).astype(np.uint8)
    if img_bgr.shape[2] == 4:
        return np.dstack((out, img_bgr[:, :, 3]))
    return out


def apply_gloss(img_bgr, H, light, mask, amount):
    """Specular highlight on height crests, luminance only."""
    if amount <= 0:
        return img_bgr
    N = normals(H, 4.0)
    L = _normalize_light(light)
    R = 2.0 * (N @ L)[..., None] * N - L
    spec = np.maximum(R[:, :, 2], 0.0) ** 24
    crests = np.clip(np.asarray(H, np.float32), 0.0, None)
    crests = crests / max(float(crests.max()), 1e-6)
    m = np.clip(np.asarray(mask, np.float32), 0.0, 1.0) * crests
    add = (spec * float(amount) * m).astype(np.float32)
    bgr = img_bgr[:, :, :3]
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[:, :, 0] = np.clip(lab[:, :, 0] + add * 255.0, 0.0, 255.0)
    out = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    if img_bgr.shape[2] == 4:
        return np.dstack((out, img_bgr[:, :, 3]))
    return out
