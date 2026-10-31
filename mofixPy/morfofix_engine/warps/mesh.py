"""Liquify con malla regular (antes 126×126 del APK; ahora 201×201 para radios chicos)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

GRID_N = 201
GRID_STEP = 1.0 / (GRID_N - 1)
# k admite hasta 1.0: con k≈1 el centro del pincel arrastra la piel 1:1 con el mouse.
K_MAX = 1.0
K_SOFT = 0.15
K_STRONG = 0.30
R_SOFT = 0.03
R_STRONG = 0.10


@dataclass(frozen=True)
class Stroke:
    p0: tuple[float, float]
    p1: tuple[float, float]
    k: float
    radius: float


def base_grid() -> np.ndarray:
    """Grilla regular en [0, 1], shape (GRID_N, GRID_N, 2) = (x, y)."""
    t = np.linspace(0.0, 1.0, GRID_N, dtype=np.float64)
    gx, gy = np.meshgrid(t, t)
    return np.stack([gx, gy], axis=-1)


def _aspect_offset(dx: np.ndarray, dy: np.ndarray, width: int, height: int) -> np.ndarray:
    """Distancia en fracciones del lado MENOR (círculo real en píxeles).

    Antes era hypot(dx·h/w, dy·w/h): en una foto vertical 1280×1598 eso daba una
    elipse y R no correspondía al cursor de la UI.
    """
    return np.hypot(dx * float(width), dy * float(height)) / float(max(1, min(width, height)))


def apply_stroke(
    mesh: np.ndarray,
    stroke: Stroke,
    width: int,
    height: int,
    frozen: np.ndarray | None = None,
) -> np.ndarray:
    """Empuje suave/fuerte: w = k·(1 − r/R)²; vértices frozen no se mueven."""
    out = mesh.copy()
    p0 = np.array(stroke.p0, dtype=np.float64)
    p1 = np.array(stroke.p1, dtype=np.float64)
    delta = p1 - p0
    R = float(stroke.radius)
    k = float(stroke.k)
    if R <= 0 or k <= 0:
        return out
    # Distancia al p0 en el espacio de la grilla actual (coords [0,1])
    dx = out[..., 0] - p0[0]
    dy = out[..., 1] - p0[1]
    r = _aspect_offset(dx, dy, width, height)
    inside = r < R
    if not np.any(inside):
        return out
    t = 1.0 - r[inside] / R
    w = k * t * t
    if frozen is not None:
        if frozen.shape[:2] != (GRID_N, GRID_N):
            fz = cv2.resize(frozen.astype(np.float32), (GRID_N, GRID_N), interpolation=cv2.INTER_LINEAR)
        else:
            fz = frozen.astype(np.float32)
        # [RE] vértices congelados no se mueven
        w = w * (1.0 - (fz[inside] >= 0.5).astype(np.float64))
    nx = out[..., 0]
    ny = out[..., 1]
    nx[inside] = nx[inside] + delta[0] * w
    ny[inside] = ny[inside] + delta[1] * w
    np.clip(nx, 0.0, 1.0, out=nx)
    np.clip(ny, 0.0, 1.0, out=ny)
    out[..., 0] = nx
    out[..., 1] = ny
    return out


def falloff_weight(r: float, k: float, R: float) -> float:
    """w = k·(1 − r/R)² si r < R, si no 0. Forma expandida del APK."""
    if r >= R or R <= 0:
        return 0.0
    return float(k * (1.0 - r / R) ** 2)


def build_mesh(
    strokes: list[Stroke],
    width: int,
    height: int,
    frozen: np.ndarray | None = None,
) -> np.ndarray:
    mesh = base_grid()
    for st in strokes:
        mesh = apply_stroke(mesh, st, width, height, frozen=frozen)
    return mesh


def sample_mesh(mesh: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """Bilinear sample of mesh at uv in [0,1], uv shape (..., 2)."""
    n = GRID_N
    x = np.clip(uv[..., 0] * (n - 1), 0.0, n - 1 - 1e-6)
    y = np.clip(uv[..., 1] * (n - 1), 0.0, n - 1 - 1e-6)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, n - 1)
    y1 = np.minimum(y0 + 1, n - 1)
    tx = x - x0
    ty = y - y0
    v00 = mesh[y0, x0]
    v10 = mesh[y0, x1]
    v01 = mesh[y1, x0]
    v11 = mesh[y1, x1]
    a = v00 * (1 - tx)[..., None] + v10 * tx[..., None]
    b = v01 * (1 - tx)[..., None] + v11 * tx[..., None]
    return a * (1 - ty)[..., None] + b * ty[..., None]


def inverse_map(mesh: np.ndarray, iterations: int = 40) -> np.ndarray:
    """Punto fijo: src tal que forward(src) ≈ dest, en cada nodo de la grilla."""
    dest = base_grid()
    src = dest.copy()
    for _ in range(iterations):
        fwd = sample_mesh(mesh, src)
        src = src + (dest - fwd)
        np.clip(src[..., 0], 0.0, 1.0, out=src[..., 0])
        np.clip(src[..., 1], 0.0, 1.0, out=src[..., 1])
    return src


def mesh_to_maps(inv: np.ndarray, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """Upsample del mapa inverso a píxeles para cv2.remap."""
    map_xy = cv2.resize(inv.astype(np.float32), (width, height), interpolation=cv2.INTER_LINEAR)
    map_x = map_xy[..., 0] * (width - 1)
    map_y = map_xy[..., 1] * (height - 1)
    return map_x.astype(np.float32), map_y.astype(np.float32)


def apply_warp(
    img: np.ndarray,
    strokes: list[Stroke],
    frozen: np.ndarray | None = None,
    interpolation: int = cv2.INTER_LINEAR,
) -> np.ndarray:
    if not strokes:
        return img
    h, w = img.shape[:2]
    mesh = build_mesh(strokes, w, h, frozen=frozen)
    inv = inverse_map(mesh)
    map_x, map_y = mesh_to_maps(inv, w, h)
    return cv2.remap(img, map_x, map_y, interpolation=interpolation, borderMode=cv2.BORDER_REPLICATE)
