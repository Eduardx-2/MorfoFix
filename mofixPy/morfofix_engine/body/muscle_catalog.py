"""Muscle modes, required keypoints and catalog entries for GET /catalog."""
from __future__ import annotations

from dataclasses import dataclass

MUSCLE_ALIAS = {
    "body_muscle": "full_body",
    "man_abs": "abs",
    "woman_abs": "ab_line",
    "man_chest": "chest",
    "woman_chest": "bust",
    "man_arm": "arm",
    "woman_arm": "arm",
    "man_leg": "leg",
    "woman_leg": "leg",
}

MUSCLE_MODE_NAMES = (
    "full_body",
    "abs",
    "ab_line",
    "chest",
    "bust",
    "arm",
    "leg",
)

REQUIRED_KP = {
    "abs": (11, 12, 23, 24),
    "abline": (11, 12, 23, 24),
    "chest": (11, 12, 23, 24),
    "bust": (11, 12, 23, 24),
    "arm": (11, 12, 13, 14, 15, 16),
    "leg": (23, 24, 25, 26, 27, 28),
}


@dataclass(frozen=True)
class MuscleMode:
    name: str
    label_es: str
    parts: tuple[str, ...]
    status: str = "ready"
    order: int = 0


MUSCLE_MODES: dict[str, MuscleMode] = {
    p.name: p
    for p in (
        MuscleMode("full_body", "Cuerpo completo", ("chest", "abs", "arm", "leg"), order=0),
        MuscleMode("abs", "Abdominales", ("abs",), order=1),
        MuscleMode("ab_line", "Línea abdominal", ("abline",), order=2),
        MuscleMode("chest", "Pectorales", ("chest",), order=3),
        MuscleMode("bust", "Busto", ("bust",), order=4),
        MuscleMode("arm", "Brazos", ("arm",), order=5),
        MuscleMode("leg", "Piernas", ("leg",), order=6),
    )
}


def catalog_entries():
    """Entries with tab Muscle for the public catalog. Canonical ids only."""
    return [
        {
            "name": m.name,
            "label_es": m.label_es,
            "tab": "Muscle",
            "kind": "mode",
            "status": m.status,
            "order": m.order,
        }
        for m in sorted(MUSCLE_MODES.values(), key=lambda m: m.order)
    ]
