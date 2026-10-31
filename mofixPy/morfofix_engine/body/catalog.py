"""Params de cuerpo: nombres EffectSDK [RE], algoritmos propios; fuerzas pendientes de calibración."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label_es: str
    lr: bool
    status: str = "planned"
    kind: str = "intensity"
    phase: int = 2
    range: tuple[float, float] = (-1.0, 1.0)


BODY_PARAMS: dict[str, ParamSpec] = {
    p.name: p
    for p in (
        ParamSpec("intensity_bodyslim_waistthin", "Cintura", True),
        ParamSpec("intensity_bodyslim_bellythin", "Abdomen", False),
        ParamSpec("intensity_bodyslim_hipplump", "Cadera (volumen)", True),
        ParamSpec("intensity_bodyslim_hiplift", "Elevar glúteos", True),
        ParamSpec("intensity_bodyslim_legthin", "Piernas", True),
        ParamSpec("intensity_bodyslim_legthin_leftthigh", "Muslo izquierdo", False),
        ParamSpec("intensity_bodyslim_legthin_rightthigh", "Muslo derecho", False),
        ParamSpec("intensity_bodyslim_legthin_leftcalf", "Pantorrilla izquierda", False),
        ParamSpec("intensity_bodyslim_legthin_rightcalf", "Pantorrilla derecha", False),
        ParamSpec("intensity_bodyslim_leglong", "Piernas largas", False),
        ParamSpec("intensity_bodyslim_armthin", "Brazos", True),
        ParamSpec("intensity_bodyslim_armthin_leftupper", "Brazo izquierdo", False),
        ParamSpec("intensity_bodyslim_armthin_rightupper", "Brazo derecho", False),
        ParamSpec("intensity_bodyslim_armthin_leftforearm", "Antebrazo izquierdo", False),
        ParamSpec("intensity_bodyslim_armthin_rightforearm", "Antebrazo derecho", False),
        ParamSpec("intensity_bodyslim_shoulderbroad", "Hombros anchos", True),
        ParamSpec("intensity_bodyslim_shoulderrightangle", "Hombros rectos", True),
        ParamSpec("intensity_bodyslim_neckwidth", "Ancho de cuello", True),
        ParamSpec("intensity_bodyslim_neckswan", "Cuello largo", True),
        ParamSpec("intensity_bodyslim_breastenlarge", "Busto", True),
        ParamSpec("intensity_bodyslim_headsmall", "Cabeza", False),
        ParamSpec("intensity_bodyslim", "Cuerpo (global)", False),
    )
}

# Alias legacy del .so → nombre Java `intensity_bodyslim_*`
BODY_ALIAS: dict[str, str] = {
    "intensity_waistthin": "intensity_bodyslim_waistthin",
    "intensity_hiplift": "intensity_bodyslim_hiplift",
    "intensity_hiplift_left": "intensity_bodyslim_hiplift",
    "intensity_bellythin": "intensity_bodyslim_bellythin",
    "intensity_hipplump": "intensity_bodyslim_hipplump",
    "intensity_legthin": "intensity_bodyslim_legthin",
    "intensity_leglong": "intensity_bodyslim_leglong",
    "intensity_armthin": "intensity_bodyslim_armthin",
    "intensity_shoulderbroad": "intensity_bodyslim_shoulderbroad",
    "intensity_neckwidth": "intensity_bodyslim_neckwidth",
    "intensity_breastenlarge": "intensity_bodyslim_breastenlarge",
}


def catalog_entries() -> list[dict]:
    return [
        {
            "name": p.name,
            "label_es": p.label_es,
            "tab": "Body",
            "kind": p.kind,
            "range": list(p.range),
            "lr": p.lr,
            "status": p.status,
            "phase": p.phase,
        }
        for p in BODY_PARAMS.values()
    ]

from dataclasses import replace
_IMPLEMENTED = {"intensity_bodyslim", "intensity_bodyslim_waistthin", "intensity_bodyslim_bellythin",
                "intensity_bodyslim_hipplump", "intensity_bodyslim_shoulderbroad", "intensity_bodyslim_neckwidth"}
_IMPLEMENTED.update(k for k in BODY_PARAMS if "legthin" in k or "armthin" in k)
BODY_PARAMS = {k: replace(v, status="ready") if k in _IMPLEMENTED else v for k,v in BODY_PARAMS.items()}

BODY_PARAMS = {k: replace(v, status="ready") for k,v in BODY_PARAMS.items()}
