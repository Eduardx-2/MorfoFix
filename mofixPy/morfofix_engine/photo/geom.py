"""Crop, rotación y flip. Affine para transformar puntos."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Affine:
    m: np.ndarray  # 2x3

    def apply_points(self, pts: np.ndarray) -> np.ndarray:
        p = np.asarray(pts, dtype=np.float64)
        xy = p[:, :2]
        ones = np.ones((len(xy), 1), dtype=np.float64)
        hom = np.hstack([xy, ones])
        out = hom @ self.m.T
        if p.shape[1] > 2:
            rest = p[:, 2:]
            return np.hstack([out, rest])
        return out


def apply_geom(
    img: np.ndarray,
    crop: tuple[float, float, float, float],
    rotate_deg: float,
    flip_h: bool,
) -> tuple[np.ndarray, Affine]:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = crop
    x0, x1 = sorted((float(np.clip(x0, 0, 1)), float(np.clip(x1, 0, 1))))
    y0, y1 = sorted((float(np.clip(y0, 0, 1)), float(np.clip(y1, 0, 1))))
    px0, px1 = int(round(x0 * w)), int(round(x1 * w))
    py0, py1 = int(round(y0 * h)), int(round(y1 * h))
    px0 = min(px0,w-1)
    py0 = min(py0,h-1)
    px1 = min(w,max(px1, px0 + 1))
    py1 = min(h,max(py1, py0 + 1))
    cropped = img[py0:py1, px0:px1]
    ch, cw = cropped.shape[:2]
    m = np.array([[1.0, 0.0, -px0], [0.0, 1.0, -py0]], dtype=np.float64)
    if flip_h:
        cropped = cv2.flip(cropped, 1)
        flip_m = np.array([[-1.0, 0.0, cw - 1], [0.0, 1.0, 0.0]], dtype=np.float64)
        m = _compose(flip_m, m)
    if abs(rotate_deg)>1e-6 and abs(rotate_deg/90-round(rotate_deg/90))<1e-8:
        k=round(rotate_deg/90)%4
        rotations={0:np.array([[1.,0.,0.],[0.,1.,0.]]),
                   1:np.array([[0.,1.,0.],[-1.,0.,cw-1]]),
                   2:np.array([[-1.,0.,cw-1],[0.,-1.,ch-1]]),
                   3:np.array([[0.,-1.,ch-1],[1.,0.,0.]])}
        cropped=np.rot90(cropped,k).copy()
        return cropped,Affine(m=_compose(rotations[k],m))
    if abs(rotate_deg) > 1e-6:
        center = (cw / 2.0, ch / 2.0)
        rot = cv2.getRotationMatrix2D(center, rotate_deg, 1.0)
        # bbox nuevo
        cos, sin = abs(rot[0, 0]), abs(rot[0, 1])
        nw = max(1,int(np.ceil(ch * sin + cw * cos)))
        nh = max(1,int(np.ceil(ch * cos + cw * sin)))
        rot[0, 2] += (nw / 2) - center[0]
        rot[1, 2] += (nh / 2) - center[1]
        cropped = cv2.warpAffine(cropped, rot, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        m = _compose(rot, m)
    return cropped, Affine(m=m)


def _compose(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a3 = np.vstack([a, [0, 0, 1]])
    b3 = np.vstack([b, [0, 0, 1]])
    c = a3 @ b3
    return c[:2]
