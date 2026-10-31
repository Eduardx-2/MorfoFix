"""HSL global. Valores −1…1."""

from __future__ import annotations

import cv2
import numpy as np


def apply_hsl(img: np.ndarray, hue: float, sat: float, light: float) -> np.ndarray:
    if abs(hue) < 1e-8 and abs(sat) < 1e-8 and abs(light) < 1e-8:
        return img
    has_a = img.ndim == 3 and img.shape[2] == 4
    bgr = img[:, :, :3] if has_a else img
    hls = cv2.cvtColor(bgr, cv2.COLOR_BGR2HLS).astype(np.float32)
    # OpenCV HLS: H 0-180, L 0-255, S 0-255
    hls[:, :, 0] = (hls[:, :, 0] + float(hue) * 90.0) % 180.0
    hls[:, :, 2] = np.clip(hls[:, :, 2] * (1.0 + float(sat)), 0, 255)
    hls[:, :, 1] = np.clip(hls[:, :, 1] * (1.0 + float(light)), 0, 255)
    out = cv2.cvtColor(hls.astype(np.uint8), cv2.COLOR_HLS2BGR)
    if has_a:
        return np.dstack([out, img[:, :, 3]])
    return out
