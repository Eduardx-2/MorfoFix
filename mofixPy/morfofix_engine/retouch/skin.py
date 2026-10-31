"""Suavizado y sharpen con números del pipeline GPUImage [RE]."""

from __future__ import annotations

import cv2
import numpy as np


def skin_retouch(
    img: np.ndarray,
    *,
    smooth: float = 0.0,
    sharpen: float = 0.0,
) -> np.ndarray:
    """Blur radio 1.5 + mix; unsharp amount = sharpen·0.6 + 0.11 si sharpen>0."""
    out = img
    if smooth > 0:
        blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=1.5, sigmaY=1.5)
        k = float(np.clip(smooth, 0.0, 1.0))
        out = cv2.addWeighted(img, 1.0 - k, blurred, k, 0)
    if sharpen > 0:
        amount = float(sharpen) * 0.6 + 0.11  # p72 [RE]
        blur = cv2.GaussianBlur(out, (0, 0), sigmaX=1.0, sigmaY=1.0)
        out = cv2.addWeighted(out, 1.0 + amount, blur, -amount, 0)
    return out
