"""Adaptador de parámetros legacy para llamadas Python; la API usa EditState."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from morfofix_engine.body.catalog import BODY_ALIAS, BODY_PARAMS
from morfofix_engine.face.catalog import FACE_PARAMS, is_face_param, split_lr
from morfofix_engine.retouch.catalog import RETOUCH_PARAMS

INTENSITY_READY = {
    name
    for name, spec in FACE_PARAMS.items()
    if spec.status == "ready"
}


@dataclass
class PhotoGeom:
    crop: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    rotate_deg: float = 0.0
    flip_h: bool = False
    hue: float = 0.0
    saturation: float = 0.0
    lightness: float = 0.0


@dataclass
class LiquifyStroke:
    p0: tuple[float, float]
    p1: tuple[float, float]
    k: float
    r: float


@dataclass
class BrushStroke:
    pts: list[tuple[float, float]]
    radius: float
    erase: bool = False


@dataclass
class SessionParams:
    """Conjunto de edición de una sesión."""

    face: dict[int, dict[str, float]] = field(default_factory=dict)
    liquify: list[LiquifyStroke] = field(default_factory=list)
    freeze: list[BrushStroke] = field(default_factory=list)
    retouch: dict[str, float] = field(default_factory=dict)
    remove: list[BrushStroke] = field(default_factory=list)
    remove_method: str = "telea"
    photo: PhotoGeom = field(default_factory=PhotoGeom)

    def set_param(self, name: str, value: float, face: int = 0) -> None:
        canon = BODY_ALIAS.get(name, name)
        base, _side = split_lr(canon)
        if is_face_param(canon):
            spec = FACE_PARAMS.get(base)
            if spec is None:
                raise ValueError(f"param desconocido: {name}")
            if spec.kind == "intensity" and not (-1.0 <= value <= 1.0):
                raise ValueError(f"{name} fuera de rango [-1, 1]")
            if spec.status != "ready" and abs(value) > 0:
                raise ValueError(f"{name} no está implementado (planned)")
            if abs(value) < 1e-12:
                bucket = self.face.setdefault(face, {})
                bucket.pop(canon, None)
                return
            self.face.setdefault(face, {})[canon] = float(value)
            return
        if canon in BODY_PARAMS:
            raise ValueError(f"{name} requiere EditState.body; no está disponible en el adaptador legacy")
        if canon in RETOUCH_PARAMS:
            spec = RETOUCH_PARAMS[canon]
            if spec.kind == "degree" and not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} fuera de rango [0, 1]")
            if spec.status != "ready" and abs(value) > 0:
                raise ValueError(f"{name} no está implementado (planned)")
            if abs(value) < 1e-12:
                self.retouch.pop(canon, None)
            else:
                self.retouch[canon] = float(value)
            return
        raise ValueError(f"param desconocido: {name}")

    def is_identity(self) -> bool:
        if any(self.face.values()):
            return False
        if self.liquify or self.freeze or self.remove:
            return False
        if self.retouch:
            return False
        p = self.photo
        if p.crop != (0.0, 0.0, 1.0, 1.0):
            return False
        if p.rotate_deg or p.flip_h:
            return False
        if p.hue or p.saturation or p.lightness:
            return False
        return True


def strokes_from_json(items: list[dict[str, Any]] | None) -> list[LiquifyStroke]:
    out: list[LiquifyStroke] = []
    if not items:
        return out
    for item in items:
        pts = item.get("pts") or []
        k = float(item.get("k", 0.15))
        r = float(item.get("r", 0.03))
        if not (0.0 < k <= 0.6):
            raise ValueError("k debe estar en (0, 0.6]")
        if not (0.0 < r <= 0.5):
            raise ValueError("r debe estar en (0, 0.5]")
        for a, b in zip(pts, pts[1:]):
            out.append(
                LiquifyStroke(
                    p0=(float(a[0]), float(a[1])),
                    p1=(float(b[0]), float(b[1])),
                    k=k,
                    r=r,
                )
            )
    return out


def brush_from_json(items: list[dict[str, Any]] | None) -> list[BrushStroke]:
    out: list[BrushStroke] = []
    if not items:
        return out
    for item in items:
        pts = [(float(p[0]), float(p[1])) for p in (item.get("pts") or [])]
        if not pts:
            continue
        out.append(
            BrushStroke(
                pts=pts,
                radius=float(item.get("radius", 0.02)),
                erase=bool(item.get("erase", False)),
            )
        )
    return out
