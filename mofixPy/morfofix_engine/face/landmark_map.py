"""Grupos MediaPipe Face Mesh 478 y SliderSpec de los 9 sliders [proto]."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Óvalo canónico Face Mesh (sentido horario, frente→derecha→mentón→izquierda).
FACE_OVAL: tuple[int, ...] = (
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365,
    379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93,
    234, 127, 162, 21, 54, 103, 67, 109,
)
# JAW = FACE_OVAL[8:29]  (mejilla der. → mentón → mejilla izq.)
JAW: tuple[int, ...] = FACE_OVAL[8:29]
JAWLINE: tuple[int, ...] = FACE_OVAL[10:27]

CHEEKS: tuple[int, ...] = (
    205, 50, 187, 207, 216, 212, 202, 204, 194, 211,
    425, 280, 411, 427, 436, 432, 422, 424, 418, 431,
    116, 123, 147, 213, 192, 345, 352, 376, 433, 416,
)

EYES_R: tuple[int, ...] = (  # ojo derecho del sujeto
    33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
)
EYES_L: tuple[int, ...] = (
    263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466,
)
IRIS_R: tuple[int, ...] = (468, 469, 470, 471, 472)
IRIS_L: tuple[int, ...] = (473, 474, 475, 476, 477)

LIPS_OUTER: tuple[int, ...] = (
    61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146,
)
LIPS_INNER: tuple[int, ...] = (
    78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
)
LIPS: tuple[int, ...] = LIPS_OUTER + LIPS_INNER

NOSE: tuple[int, ...] = (
    1, 2, 4, 5, 6, 19, 94, 168, 197, 195, 98, 97, 99, 327, 326, 328, 48, 64, 98, 240, 278, 294, 327, 460,
)

BROWS_R: tuple[int, ...] = (70, 63, 105, 66, 107, 55, 65, 52, 53, 46)
BROWS_L: tuple[int, ...] = (300, 293, 334, 296, 336, 285, 295, 282, 283, 276)

FOREHEAD: tuple[int, ...] = (10, 338, 297, 332, 284, 251, 109, 67, 103, 54, 21, 162, 151, 337, 299, 333, 298, 301)

GROUPS: dict[str, tuple[int, ...]] = {
    "FACE_OVAL": FACE_OVAL,
    "JAW": JAW,
    "JAWLINE": JAWLINE,
    "CHEEKS": CHEEKS,
    "EYES_L": EYES_L,
    "EYES_R": EYES_R,
    "IRIS_L": IRIS_L,
    "IRIS_R": IRIS_R,
    "LIPS": LIPS,
    "LIPS_OUTER": LIPS_OUTER,
    "LIPS_INNER": LIPS_INNER,
    "NOSE": NOSE,
    "BROWS_L": BROWS_L,
    "BROWS_R": BROWS_R,
    "FOREHEAD": FOREHEAD,
}

SKELETON_GROUPS: tuple[str, ...] = (
    "FACE_OVAL",
    "EYES_L",
    "EYES_R",
    "LIPS_OUTER",
    "NOSE",
    "BROWS_L",
    "BROWS_R",
)


@dataclass(frozen=True)
class SliderSpec:
    groups: tuple[str, ...]
    mode: str
    strength: float
    profile: str = "flat"
    ring: float = 1.0
    lr: bool = False


SLIDER_TO_GROUP: dict[str, SliderSpec] = {
    "intensity_jaw": SliderSpec(("JAW",), "axis", 0.24, "lower", 1.35, True),
    "intensity_jawline_1": SliderSpec(("JAWLINE",), "axis", 0.16, "lower2", 1.20, False),
    "intensity_facev": SliderSpec(("JAW",), "vshape", 0.26, "lower2", 1.35, True),
    "intensity_facewidth": SliderSpec(("CHEEKS",), "axis", 0.14, "flat", 1.20, True),
    "intensity_facelength": SliderSpec(("JAW",), "length", 0.07, "lower2", 1.20, False),
    "intensity_eyesize": SliderSpec(("EYES_L", "EYES_R"), "scale", 0.28, "flat", 2.2, True),
    "intensity_eyedistance": SliderSpec(("EYES_L", "EYES_R"), "distance", 0.06, "flat", 1.4, True),
    "intensity_mouthsize": SliderSpec(("LIPS",), "scale", 0.22, "flat", 1.9, False),
    "intensity_nosesize": SliderSpec(("NOSE",), "scale", 0.20, "flat", 1.8, False),
}


# Own deformations. Anatomically uncertain temple/cheekbone/bridge remain planned.
SLIDER_TO_GROUP.update({
    "intensity_facesmall": SliderSpec(("FACE_OVAL",), "scale", -.12, ring=1.4),
    "intensity_headsmall": SliderSpec(("FACE_OVAL","FOREHEAD"), "chin_scale", -.15, ring=1.6),
    "intensity_faceresize": SliderSpec(("FACE_OVAL",), "scale", .12, ring=1.4, lr=True),
    "intensity_hairline": SliderSpec(("FOREHEAD",), "translate", .05, "upper", 1.4),
    "intensity_eyewidth": SliderSpec(("EYES_L","EYES_R"), "aniso", .25, ring=2.2, lr=True),
    "intensity_eyeheight": SliderSpec(("EYES_L","EYES_R"), "aniso_y", .25, ring=2.2, lr=True),
    "intensity_eyetilt": SliderSpec(("EYES_L","EYES_R"), "rotate", 1, ring=2.2, lr=True),
    "intensity_eyepupil": SliderSpec(("IRIS_L","IRIS_R"), "scale", .2, ring=1.5, lr=True),
    "intensity_eyeposition": SliderSpec(("EYES_L","EYES_R"), "translate", .04, ring=1.5, lr=True),
    "intensity_mouthwidth": SliderSpec(("LIPS",), "aniso", .2, ring=1.9, lr=True),
    "intensity_mouthheight": SliderSpec(("LIPS",), "translate", .04, ring=1.9),
    "intensity_mouththickness": SliderSpec(("LIPS",), "aniso_y", .3, ring=1.9),
    "intensity_mouthslant": SliderSpec(("LIPS",), "rotate", 1, ring=1.9),
    "intensity_nosewidth": SliderSpec(("NOSE",), "aniso", -.2, ring=1.8, lr=True),
    "intensity_noselift": SliderSpec(("NOSE",), "translate", -.025, ring=1.8),
    "intensity_brownsize": SliderSpec(("BROWS_L","BROWS_R"), "scale", .2, ring=1.5, lr=True),
    "intensity_browndistance": SliderSpec(("BROWS_L","BROWS_R"), "distance", .06, ring=1.5, lr=True),
    "intensity_brownposition": SliderSpec(("BROWS_L","BROWS_R"), "translate", -.04, ring=1.5, lr=True),
    "intensity_browntilt": SliderSpec(("BROWS_L","BROWS_R"), "rotate", 1, ring=1.5, lr=True),
    "intensity_brownlength": SliderSpec(("BROWS_L","BROWS_R"), "aniso", .2, ring=1.5, lr=True),
    "intensity_forehead": SliderSpec(("FOREHEAD",), "length", .05, "upper", 1.4),
    "intensity_middlecourt": SliderSpec(("NOSE",), "aniso_y", .12, ring=1.5),
    "intensity_lowercourt": SliderSpec(("JAW",), "length", .06, "lower", 1.4),
    "intensity_faceshort": SliderSpec(("FACE_OVAL",), "aniso_y", -.1, ring=1.4),
})


GROUPS.update({
    "EYE_OUTER_R":(33,7,163,246), "EYE_OUTER_L":(263,249,390,466),
    "EYE_INNER_R":(133,155,173), "EYE_INNER_L":(362,382,398),
    "EYE_UNDER_R":(145,153,154), "EYE_UNDER_L":(374,380,381),
    "LIP_UP":(37,0,267,39,269), "LIP_DOWN":(84,17,314,181,405),
    "LIP_CORNERS":(61,291), "CUPID":(37,267),
    "NOSE_TIP":(4,1,19,94,2), "NOSE_ROOT":(168,6),
})
SLIDER_TO_GROUP.update({
    "intensity_eyetail":SliderSpec(("EYE_OUTER_L","EYE_OUTER_R"),"corner",.04,ring=1.8,lr=True),
    "intensity_eyeunder":SliderSpec(("EYE_UNDER_L","EYE_UNDER_R"),"translate",.025,ring=1.8,lr=True),
    "intensity_eyeinner":SliderSpec(("EYE_INNER_L","EYE_INNER_R"),"lateral",-.025,ring=1.8,lr=True),
    "intensity_eyeouter":SliderSpec(("EYE_OUTER_L","EYE_OUTER_R"),"lateral",.025,ring=1.8,lr=True),
    "intensity_eyesmiley":SliderSpec(("EYE_UNDER_L","EYE_UNDER_R"),"curve",-.025,ring=1.8,lr=True),
    "up_intensity_mouththickness":SliderSpec(("LIP_UP",),"translate",-.025,ring=1.8),
    "down_intensity_mouththickness":SliderSpec(("LIP_DOWN",),"translate",.025,ring=1.8),
    "intensity_mouthsmile":SliderSpec(("LIP_CORNERS",),"corner",.035,ring=1.8),
    "intensity_mouthmshape":SliderSpec(("CUPID",),"translate",-.02,ring=1.8),
    "intensity_nosetip":SliderSpec(("NOSE_TIP",),"scale",.15,ring=1.8),
    "intensity_noseroot":SliderSpec(("NOSE_ROOT",),"aniso",-.12,ring=1.8),
    "intensity_philtrum":SliderSpec(("LIPS",),"translate",.04,ring=1.8),
    "intensity_brownshape":SliderSpec(("BROWS_L","BROWS_R"),"curve",-.035,ring=1.8,lr=True),
})

def synthetic_landmarks(width: int = 400, height: int = 500) -> np.ndarray:
    """Cara sintética frontal para tests sin MediaPipe. Ancho de mandíbula ≈ 266 px."""
    lm = np.zeros((478, 3), dtype=np.float64)
    cx, cy = width * 0.5, height * 0.42
    # Elipses: óvalo, ojos, boca, nariz
    oval_rx, oval_ry = 133.0, 180.0
    n_oval = len(FACE_OVAL)
    for i, idx in enumerate(FACE_OVAL):
        ang = -np.pi / 2 + 2 * np.pi * i / n_oval
        lm[idx, 0] = cx + oval_rx * np.cos(ang)
        lm[idx, 1] = cy + oval_ry * np.sin(ang)
    # frente 10, mentón 152 forzados en el eje
    lm[10, 0], lm[10, 1] = cx, cy - oval_ry
    lm[152, 0], lm[152, 1] = cx, cy + oval_ry

    def _ring(indices: tuple[int, ...], ox: float, oy: float, rx: float, ry: float) -> None:
        n = len(indices)
        for i, idx in enumerate(indices):
            ang = 2 * np.pi * i / n
            lm[idx, 0] = ox + rx * np.cos(ang)
            lm[idx, 1] = oy + ry * np.sin(ang)

    _ring(EYES_R, cx - 45, cy - 20, 22, 12)
    _ring(EYES_L, cx + 45, cy - 20, 22, 12)
    for i, idx in enumerate(IRIS_R):
        lm[idx, 0] = cx - 45 + (i - 2) * 3
        lm[idx, 1] = cy - 20
    for i, idx in enumerate(IRIS_L):
        lm[idx, 0] = cx + 45 + (i - 2) * 3
        lm[idx, 1] = cy - 20
    _ring(LIPS_OUTER, cx, cy + 70, 40, 18)
    _ring(LIPS_INNER, cx, cy + 70, 28, 10)
    _ring(NOSE, cx, cy + 20, 16, 28)
    lm[1, 0], lm[1, 1] = cx, cy + 28
    _ring(BROWS_R, cx - 45, cy - 48, 24, 6)
    _ring(BROWS_L, cx + 45, cy - 48, 24, 6)
    _ring(FOREHEAD, cx, cy - 140, 90, 30)
    _ring(CHEEKS, cx, cy + 10, 110, 50)
    # relleno: el resto hacia el centro de cara (esqueleto estable)
    unset = np.where(np.all(lm[:, :2] == 0, axis=1))[0]
    rng = np.random.default_rng(0)
    for idx in unset:
        lm[idx, 0] = cx + rng.normal(0, 40)
        lm[idx, 1] = cy + rng.normal(0, 50)
        lm[idx, 2] = 0.0
    # normalizar a [0,1]
    lm[:, 0] /= width
    lm[:, 1] /= height
    np.clip(lm[:, 0], 0.0, 1.0, out=lm[:, 0])
    np.clip(lm[:, 1], 0.0, 1.0, out=lm[:, 1])
    return lm.astype(np.float32)
