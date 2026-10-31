"""Validated, complete API v0 state. No history or incremental render patches."""
import logging
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from morfofix_engine.face.catalog import FACE_PARAMS, split_lr
from morfofix_engine.body.catalog import BODY_PARAMS, BODY_ALIAS
from morfofix_engine.body.muscle_catalog import MUSCLE_ALIAS, MUSCLE_MODE_NAMES
from morfofix_engine.retouch.catalog import RETOUCH_PARAMS
from morfofix_engine.body.manual import SHAPES

Unit = Annotated[float, Field(ge=0, le=1)]
Intensity = Annotated[float, Field(ge=-1, le=1)]
Point = tuple[Unit, Unit]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, populate_by_name=True)


class Brush(Strict):
    pts: list[Point] = Field(min_length=1)
    radius: float = Field(gt=0, le=.5)
    erase: bool = False


class Mask(Strict):
    strokes: list[Brush] = Field(default_factory=list)


class Liquify(Strict):
    pts: list[Point] = Field(min_length=2)
    # k ≤ 1: con 0.6 y la caída t² el empuje máximo no pasaba de ~2 px (ver 19-correcciones-cuerpo.md).
    k: float = Field(gt=0, le=1.0)
    r: float = Field(gt=0, le=.5)


class Height(Strict):
    """Estiramiento vertical.

    `y_start`/`y_end` (0..1, coordenadas de la imagen antes del estiramiento) son las
    líneas que el usuario arrastra en el overlay. Si vienen, mandan sobre `band`
    (que queda por compatibilidad con estados viejos). Solo debajo de una línea:
    y_start=línea, y_end=1. Solo encima: y_start=0, y_end=línea.
    """
    band: tuple[Unit, Unit] = (.48, .92)
    value: Intensity
    keep_canvas: bool = False
    y_start: Unit | None = None
    y_end: Unit | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.y_start is not None or self.y_end is not None:
            a = self.band[0] if self.y_start is None else self.y_start
            b = self.band[1] if self.y_end is None else self.y_end
            if a >= b or b - a < .02 - 1e-9:
                raise ValueError("height.y_start..y_end debe estar ordenada y medir al menos 0.02")
            self.band = (a, b)
        elif self.band[1] - self.band[0] < .02 - 1e-9:
            raise ValueError("height.band / y_start..y_end debe estar ordenada y medir al menos 0.02")
        return self


class Rect(Strict):
    x: Unit
    y: Unit
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    erase: bool = False


class ArmManual(Strict):
    cx: Unit
    cy: Unit
    rx: float = Field(ge=.01, le=.5)
    ry: float = Field(ge=.01, le=.5)
    angle: float = Field(default=0, ge=-180, le=180)
    value: Intensity = 0
    protect_bg: bool = False


ARM_MAX_STROKES = 32


class Arm(Strict):
    # `manual` = trazo activo (lo que mueve el editor); `manual_strokes` = trazos ya fijados,
    # se aplican en orden antes del activo. Más de 32 → 400 (Rust recorta antes, ver doc 23).
    manual: ArmManual | None = None
    manual_strokes: list[ArmManual] = Field(default_factory=list, max_length=ARM_MAX_STROKES)


class Freeze(Mask):
    """Máscara de congelado: trazos de pincel + rectángulos, en orden de dibujo
    (primero trazos, después rects; `erase` resta). `radius` y `feather` son
    fracciones del lado MENOR de la imagen."""
    rects: list[Rect] = Field(default_factory=list)
    invert: bool = False
    feather: float = Field(default=0, ge=0, le=.25)


class Shape(Strict):
    type: str
    cx: Unit
    cy: Unit
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    angle: float = 0
    value: Intensity
    feather: Unit = .5
    symmetric: bool = True

    @model_validator(mode="after")
    def known(self):
        if self.type not in SHAPES:
            raise ValueError("manual shape desconocida")
        return self


class Remove(Mask):
    method: Literal["telea", "ns", "exemplar"] = "telea"


class HSL(Strict):
    hue: Intensity = 0
    saturation: Intensity = 0
    lightness: Intensity = 0


class Photo(Strict):
    crop: tuple[Unit, Unit, Unit, Unit] = (0, 0, 1, 1)
    rotate_deg: float = Field(default=0, ge=-180, le=180)
    flip_h: bool = False
    hsl: HSL = Field(default_factory=HSL)

    @model_validator(mode="after")
    def ordered(self):
        x0, y0, x1, y1 = self.crop
        if x1 <= x0 or y1 <= y0:
            raise ValueError("crop debe tener área positiva")
        return self


class Options(Strict):
    bg_protect: bool = False
    head_protect: bool = True


class Muscle(Strict):
    mode: Literal[*MUSCLE_MODE_NAMES]
    strength: Unit = 0.6
    definition: Unit = 0.5
    warp: Unit = 0.3
    light: Literal["auto", "top", "left", "right"] = "auto"
    gloss: Unit = 0
    brush: Mask = Field(default_factory=Mask)

    @model_validator(mode="before")
    @classmethod
    def _compat(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            log = logging.getLogger("morfofix.muscle")
            for k in ("gender", "sex", "variant", "group"):
                if k in data:
                    log.warning("muscle.%s está deprecado y se ignora", k)
                    data.pop(k)
            m = data.get("mode")
            if m in MUSCLE_ALIAS:
                log.warning("muscle.mode '%s' deprecado → '%s'", m, MUSCLE_ALIAS[m])
                data["mode"] = MUSCLE_ALIAS[m]
        return data


class Retouch(Strict):
    degree_skin_smooth: Unit = 0
    degree_sharpen: Unit = 0
    degree_whiten_skin: Unit = 0
    degree_skin_details: Unit = 0
    degree_skin_texture: Unit = 0
    degree_skin_matte: Unit = 0
    degree_whiten_teeth: Unit = 0
    degree_brighten_eyes: Unit = 0
    degree_whiten_eyes: Unit = 0
    degree_remove_eye_redness: Unit = 0
    degree_dark_circles: Unit = 0
    degree_remove_blemishes: Unit = 0
    degree_wrinkles: Unit = 0
    brush: dict[str, Mask] = Field(default_factory=dict)

    @model_validator(mode="after")
    def brush_names(self):
        if any(k not in RETOUCH_PARAMS for k in self.brush):
            raise ValueError("pincel de retoque desconocido")
        return self


class EditState(Strict):
    schema_version: Literal[1] = Field(default=1, alias="schema")
    face: dict[str, dict[str, Intensity]] = Field(default_factory=dict)
    facelift: dict[str, dict[str, Intensity]] = Field(default_factory=dict)
    body: dict[str, dict[str, Intensity]] = Field(default_factory=dict)
    body_options: Options = Field(default_factory=Options)
    height: Height | None = None
    liquify: list[Liquify] = Field(default_factory=list)
    manual_shapes: list[Shape] = Field(default_factory=list, max_length=64)
    freeze: Freeze = Field(default_factory=Freeze)
    retouch: Retouch = Field(default_factory=Retouch)
    remove: list[Remove] = Field(default_factory=list)
    photo: Photo = Field(default_factory=Photo)
    arm: Arm = Field(default_factory=Arm)
    muscle: dict[str, Muscle] = Field(default_factory=dict)

    @model_validator(mode="after")
    def catalog(self):
        for index in self.muscle:
            if not index.isdigit() or str(int(index)) != index:
                raise ValueError("índice debe ser entero no negativo")
        for bucket, catalog in ((self.face, FACE_PARAMS), (self.facelift, FACE_PARAMS), (self.body, BODY_PARAMS)):
            for index, params in bucket.items():
                if bucket is self.body:
                    for raw in list(params):
                        base,side=split_lr(raw)
                        canon=BODY_ALIAS.get(base,base)
                        canon=(side+"_"+canon) if side else canon
                        if canon!=raw:
                            if canon in params:
                                raise ValueError("alias duplicado")
                            params[canon]=params.pop(raw)
                if not index.isdigit() or str(int(index)) != index:
                    raise ValueError("índice debe ser entero no negativo")
                for raw, value in params.items():
                    name, side = split_lr(BODY_ALIAS.get(raw, raw))
                    spec = catalog.get(name)
                    if bucket is self.facelift and "facelift_" not in name:
                        raise ValueError("facelift solo admite params facelift")
                    if bucket is self.face and "facelift_" in name:
                        raise ValueError("usar el campo facelift para params facelift")
                    if spec is None or (side and not spec.lr):
                        raise ValueError(f"param desconocido: {raw}")
                    if spec.status != "ready" and value:
                        raise ValueError(f"{raw} pendiente de calibración")
        return self
