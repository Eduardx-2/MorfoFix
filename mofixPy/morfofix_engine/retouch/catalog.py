"""Params degree_* del .so [RE]. Efectos propios y extensiones explícitas para imperfecciones/arrugas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label_es: str
    status: str
    kind: str = "degree"
    phase: int = 3
    range: tuple[float, float] = (0.0, 1.0)
    lr: bool = False


RETOUCH_PARAMS: dict[str, ParamSpec] = {
    p.name: p
    for p in (
        ParamSpec("degree_skin_smooth", "Suavizado de piel", "ready"),
        ParamSpec("degree_sharpen", "Nitidez", "ready"),
        ParamSpec("degree_whiten_skin", "Blanquear piel", "planned"),
        ParamSpec("degree_skin_details", "Detalle de piel", "planned"),
        ParamSpec("degree_skin_texture", "Textura", "planned"),
        ParamSpec("degree_skin_matte", "Mate", "planned"),
        ParamSpec("degree_whiten_teeth", "Blanquear dientes", "planned"),
        ParamSpec("degree_brighten_eyes", "Iluminar ojos", "planned"),
        ParamSpec("degree_whiten_eyes", "Blanquear ojos", "planned"),
        ParamSpec("degree_remove_eye_redness", "Rojez ocular", "planned"),
        ParamSpec("degree_dark_circles", "Ojeras", "planned"),
    )
}


def catalog_entries() -> list[dict]:
    return [
        {
            "name": p.name,
            "label_es": p.label_es,
            "tab": "Retouch",
            "kind": p.kind,
            "range": list(p.range),
            "lr": p.lr,
            "status": p.status,
            "phase": p.phase,
        }
        for p in RETOUCH_PARAMS.values()
    ]

from dataclasses import replace
RETOUCH_PARAMS = {k: replace(v, status="ready") for k,v in RETOUCH_PARAMS.items()}

RETOUCH_PARAMS.update({
    "degree_remove_blemishes": ParamSpec("degree_remove_blemishes", "Imperfecciones", "ready"),
    "degree_wrinkles": ParamSpec("degree_wrinkles", "Arrugas", "ready"),
})
