"""Backward displacement fields in pixels; compose images with a single remap.

compose(outer, inner) applies inner first, then outer to the image. Backward
maps consequently sample inner at coordinates supplied by outer.
"""
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass(frozen=True)
class Field:
    dx: np.ndarray
    dy: np.ndarray

    def __post_init__(self):
        object.__setattr__(self,"dx",np.asarray(self.dx,dtype=np.float32))
        object.__setattr__(self,"dy",np.asarray(self.dy,dtype=np.float32))
        if self.dx.shape != self.dy.shape or self.dx.ndim != 2:
            raise ValueError("field components must have identical H×W shape")


def identity(h, w):
    return Field(np.zeros((h, w), np.float32), np.zeros((h, w), np.float32))


def to_maps(f):
    y, x = np.indices(f.dx.shape, dtype=np.float32)
    return x + f.dx, y + f.dy


def from_maps(x, y):
    gy, gx = np.indices(x.shape, dtype=np.float32)
    return Field((x - gx).astype(np.float32), (y - gy).astype(np.float32))


def compose(outer, inner):
    x, y = to_maps(outer)
    return Field(
        outer.dx + cv2.remap(inner.dx, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
        outer.dy + cv2.remap(inner.dy, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE),
    )


def attenuate(f, mask):
    weight = 1 - np.clip(mask, 0, 1)
    return Field(f.dx * weight, f.dy * weight)


def radial_push(h, w, center, delta, radius):
    y, x = np.indices((h, w), dtype=np.float32)
    t = np.maximum(0, 1 - np.hypot(x-center[0], y-center[1]) / max(radius, 1e-6)) ** 2
    return Field((-delta[0]*t).astype(np.float32), (-delta[1]*t).astype(np.float32))


def local_scale(h, w, center, radius, amount):
    y, x = np.indices((h, w), dtype=np.float32)
    x, y = x-center[0], y-center[1]
    t = np.maximum(0, 1 - (x*x+y*y)/max(radius*radius, 1e-6))**2
    return Field((-amount*x*t).astype(np.float32), (-amount*y*t).astype(np.float32))


def mls_backward_field(h, w, src, dst, grid_step=8):
    from morfofix_engine.warps.mls import build_maps
    if len(src) < 2 or np.allclose(src, dst):
        return identity(h, w)
    return from_maps(*build_maps(h, w, src, dst, grid_step))


def mesh_backward_field(h, w, strokes):
    from morfofix_engine.warps.mesh import build_mesh, inverse_map, sample_mesh
    if not strokes:
        return identity(h, w)
    inv = inverse_map(build_mesh(strokes, w, h)).astype(np.float32)
    y, x = np.indices((h, w), dtype=np.float32)
    # Sample grid coordinates explicitly; cv2.resize's half-pixel convention
    # distorts even an identity mesh near the image boundary.
    gx=x*((inv.shape[1]-1)/max(w-1,1))
    gy=y*((inv.shape[0]-1)/max(h-1,1))
    grid_y,grid_x=np.indices(inv.shape[:2],dtype=np.float32)
    inv[...,0]-=grid_x/(inv.shape[1]-1)
    inv[...,1]-=grid_y/(inv.shape[0]-1)
    sample=cv2.remap(inv,gx,gy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    return Field(sample[...,0]*(w-1),sample[...,1]*(h-1))
