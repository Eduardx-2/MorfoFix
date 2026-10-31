"""Oriented-ellipse arm warp without pose landmarks."""
from __future__ import annotations

import numpy as np
from morfofix_engine.warps.field import Field, identity


def arm_manual_field(h, w, m):
    """Dense analytic warp. value > 0 thins, < 0 fattens. Axes: fraction of min(h, w)."""
    if m is None or not m.value:
        return identity(h, w)
    s = min(h, w)
    cx, cy = m.cx * (w - 1), m.cy * (h - 1)
    rx, ry = max(m.rx * s, 2.0), max(m.ry * s, 2.0)
    theta = np.deg2rad(m.angle)
    c, sn = float(np.cos(theta)), float(np.sin(theta))
    gy, gx = np.indices((h, w), dtype=np.float32)
    x, y = gx - cx, gy - cy
    u = c * x + sn * y
    v = -sn * x + c * y
    nu, nv = u / rx, v / ry
    q = (nu / 1.6) ** 2 + nv * nv
    fall = np.clip(1 - q, 0, 1) ** 2
    axial = 0.5 * (1 + np.cos(np.pi * np.clip(nv, -1, 1)))
    a = 0.30 * float(m.value)
    du = a * u * fall * axial
    dv = np.zeros_like(du)
    dx = c * du - sn * dv
    dy = sn * du + c * dv
    return Field(dx.astype(np.float32), dy.astype(np.float32))


def arm_manual_roi(h, w, m, *, rx_scale=1.9, ry_scale=1.15):
    """Soft ellipse mask around the arm (for bg protect limited to the ROI)."""
    if m is None:
        return np.zeros((h, w), np.float32)
    s = min(h, w)
    cx, cy = m.cx * (w - 1), m.cy * (h - 1)
    rx, ry = max(m.rx * s * rx_scale, 2.0), max(m.ry * s * ry_scale, 2.0)
    theta = np.deg2rad(m.angle)
    c, sn = float(np.cos(theta)), float(np.sin(theta))
    gy, gx = np.indices((h, w), dtype=np.float32)
    x, y = gx - cx, gy - cy
    u = c * x + sn * y
    v = -sn * x + c * y
    q = (u / rx) ** 2 + (v / ry) ** 2
    roi = np.clip(1 - q, 0, 1).astype(np.float32)
    sigma = max(0.15 * (m.rx * s), 1.0)
    k = int(max(3, round(sigma * 6))) | 1
    import cv2
    return cv2.GaussianBlur(roi, (k, k), sigmaX=sigma)
