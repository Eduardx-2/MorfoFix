"""Catálogo de params de cara. Nombres EffectSDK [RE]; ready indica implementación, no calibración visual."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label_es: str
    tab: str
    kind: str
    lr: bool
    status: str
    phase: int
    range: tuple[float, float] = (-1.0, 1.0)


def _p(
    name: str,
    label: str,
    tab: str,
    *,
    lr: bool,
    status: str,
    phase: int,
) -> ParamSpec:
    return ParamSpec(
        name=name,
        label_es=label,
        tab=tab,
        kind="intensity",
        lr=lr,
        status=status,
        phase=phase,
    )


FACE_PARAMS: dict[str, ParamSpec] = {
    p.name: p
    for p in (
        _p("intensity_jaw", "Mandíbula", "Face", lr=True, status="ready", phase=1),
        _p("intensity_jawline_1", "Línea de mandíbula", "Face", lr=False, status="ready", phase=2),
        _p("intensity_facev", "Forma en V", "Face", lr=True, status="ready", phase=2),
        _p("intensity_facewidth", "Ancho de cara", "Face", lr=True, status="ready", phase=2),
        _p("intensity_facelength", "Largo de cara", "Face", lr=False, status="ready", phase=2),
        _p("intensity_facesmall", "Cara pequeña", "Face", lr=False, status="planned", phase=2),
        _p("intensity_headsmall", "Cabeza", "Face", lr=False, status="planned", phase=2),
        _p("intensity_cheekbone", "Pómulos", "Face", lr=True, status="planned", phase=2),
        _p("intensity_temple", "Sienes", "Face", lr=True, status="planned", phase=2),
        _p("intensity_hairline", "Línea del pelo", "Face", lr=False, status="planned", phase=2),
        _p("intensity_faceresize", "Tamaño hemicara", "Face", lr=True, status="planned", phase=3),
        _p("intensity_facedoublechin", "Papada", "Face", lr=False, status="planned", phase=4),
        _p("intensity_eyesize", "Tamaño de ojos", "Eyes", lr=True, status="ready", phase=1),
        _p("intensity_eyedistance", "Distancia entre ojos", "Eyes", lr=True, status="ready", phase=2),
        _p("intensity_eyewidth", "Ancho de ojos", "Eyes", lr=True, status="planned", phase=2),
        _p("intensity_eyeheight", "Alto de ojos", "Eyes", lr=True, status="planned", phase=2),
        _p("intensity_eyetilt", "Inclinación", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyetail", "Rabillo", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyeunder", "Párpado inferior", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyepupil", "Pupila", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyeinner", "Lagrimal", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyeouter", "Esquina externa", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyeposition", "Posición de ojos", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_eyesmiley", "Ojos sonrientes", "Eyes", lr=True, status="planned", phase=3),
        _p("intensity_mouthsize", "Tamaño de labios", "Lips", lr=False, status="ready", phase=1),
        _p("intensity_mouthwidth", "Ancho de boca", "Lips", lr=True, status="planned", phase=2),
        _p("intensity_mouthheight", "Posición de boca", "Lips", lr=False, status="planned", phase=3),
        _p("intensity_mouththickness", "Grosor", "Lips", lr=False, status="planned", phase=2),
        _p("up_intensity_mouththickness", "Labio superior", "Lips", lr=False, status="planned", phase=3),
        _p("down_intensity_mouththickness", "Labio inferior", "Lips", lr=False, status="planned", phase=3),
        _p("intensity_mouthsmile", "Sonrisa", "Lips", lr=False, status="planned", phase=3),
        _p("intensity_mouthmshape", "Arco de Cupido", "Lips", lr=False, status="planned", phase=3),
        _p("intensity_mouthslant", "Inclinación", "Lips", lr=False, status="planned", phase=3),
        _p("intensity_nosesize", "Tamaño de nariz", "Nose", lr=False, status="ready", phase=2),
        _p("intensity_nosewidth", "Ancho de nariz", "Nose", lr=True, status="planned", phase=2),
        _p("intensity_nosetip", "Punta", "Nose", lr=False, status="planned", phase=3),
        _p("intensity_noselift", "Elevar punta", "Nose", lr=False, status="planned", phase=3),
        _p("intensity_nosebridge", "Tabique", "Nose", lr=False, status="planned", phase=3),
        _p("intensity_noseroot", "Raíz", "Nose", lr=False, status="planned", phase=3),
        _p("intensity_philtrum", "Surco nasolabial", "Nose", lr=False, status="planned", phase=3),
        _p("intensity_brownsize", "Tamaño de cejas", "Brows", lr=True, status="planned", phase=2),
        _p("intensity_browndistance", "Distancia", "Brows", lr=True, status="planned", phase=2),
        _p("intensity_brownposition", "Altura", "Brows", lr=True, status="planned", phase=2),
        _p("intensity_browntilt", "Inclinación", "Brows", lr=True, status="planned", phase=3),
        _p("intensity_brownlength", "Largo", "Brows", lr=True, status="planned", phase=3),
        _p("intensity_brownshape", "Arco", "Brows", lr=True, status="planned", phase=3),
        _p("intensity_forehead", "Frente", "Ratio", lr=False, status="planned", phase=3),
        _p("intensity_middlecourt", "Tercio medio", "Ratio", lr=False, status="planned", phase=3),
        _p("intensity_lowercourt", "Tercio inferior", "Ratio", lr=False, status="planned", phase=3),
        _p("intensity_faceshort", "Acortar", "Ratio", lr=False, status="planned", phase=3),
        _p("intensity_facelift_eye_area", "Bolsas", "Facelift", lr=False, status="planned", phase=4),
        _p("intensity_facelift_brow_peak", "Cejas (lift)", "Facelift", lr=False, status="planned", phase=4),
        _p("intensity_facelift_face_mid", "Mejillas", "Facelift", lr=False, status="planned", phase=4),
        _p("intensity_facelift_contour", "Contorno", "Facelift", lr=False, status="planned", phase=4),
        _p("intensity_facelift_forehead", "Frente (lift)", "Facelift", lr=False, status="planned", phase=4),
        _p("intensity_facelift_mouth_area", "Surcos labiales", "Facelift", lr=False, status="planned", phase=4),
    )
}


def split_lr(name: str) -> tuple[str, str | None]:
    if name.startswith("left_"):
        return name[5:], "left"
    if name.startswith("right_"):
        return name[6:], "right"
    return name, None


def is_face_param(name: str) -> bool:
    base, _ = split_lr(name)
    return base in FACE_PARAMS


def catalog_entries() -> list[dict]:
    rows = []
    for p in FACE_PARAMS.values():
        rows.append(
            {
                "name": p.name,
                "label_es": p.label_es,
                "tab": p.tab,
                "kind": p.kind,
                "range": list(p.range),
                "lr": p.lr,
                "status": p.status,
                "phase": p.phase,
            }
        )
    return rows


from dataclasses import replace
from morfofix_engine.face.landmark_map import SLIDER_TO_GROUP
FACE_PARAMS = {k: replace(v, status="ready") if k in SLIDER_TO_GROUP or "facelift_" in k else v for k,v in FACE_PARAMS.items()}

FACE_PARAMS["intensity_facedoublechin"] = replace(FACE_PARAMS["intensity_facedoublechin"], status="ready")
