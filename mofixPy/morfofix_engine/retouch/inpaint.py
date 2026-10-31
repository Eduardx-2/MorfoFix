"""Remove local: cv2.inpaint Telea / Navier-Stokes [RE]."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np


def inpaint(
    img: np.ndarray,
    mask: np.ndarray,
    *,
    method: Literal["telea", "ns"] = "telea",
    radius: int = 5,
) -> np.ndarray:
    if method == "exemplar":
        from morfofix_engine.retouch.exemplar import exemplar_inpaint
        return exemplar_inpaint(img, mask)
    if method not in {"telea", "ns"}:
        raise ValueError("método de inpaint desconocido")
    bin_mask = (mask > 0.5).astype(np.uint8)
    if not np.any(bin_mask):
        return img
    ys, xs = np.where(bin_mask > 0)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    pad = 3 * radius
    y0 = max(0, y0 - pad)
    x0 = max(0, x0 - pad)
    y1 = min(img.shape[0], y1 + pad)
    x1 = min(img.shape[1], x1 + pad)
    roi = img[y0:y1, x0:x1]
    m = bin_mask[y0:y1, x0:x1]
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    # inpaint exige 1 o 3 canales
    if roi.ndim == 3 and roi.shape[2] == 4:
        bgr = roi[:, :, :3]
        a = roi[:, :, 3]
        filled = cv2.inpaint(bgr, m, radius, flag)
        out = img.copy()
        out[y0:y1, x0:x1] = np.dstack([filled, a])
        return out
    filled = cv2.inpaint(roi, m, radius, flag)
    out = img.copy()
    out[y0:y1, x0:x1] = filled
    return out
