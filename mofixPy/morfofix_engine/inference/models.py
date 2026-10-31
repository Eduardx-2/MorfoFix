"""Manifest de modelos abiertos. Runtime no descarga nada."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "manifest.json"


@dataclass
class ModelInfo:
    key: str
    file: str
    sha256: str
    path: Path
    status: str  # ok | missing | bad_hash


class ModelRegistry:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = Path(models_dir)
        self.manifest_path = self.models_dir / MANIFEST_NAME
        self.models: dict[str, ModelInfo] = {}
        self._load()

    def _load(self) -> None:
        if not self.manifest_path.is_file():
            return
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        for key, spec in data.items():
            path = self.models_dir / spec["file"]
            status = "missing"
            if path.is_file():
                expected = spec.get("sha256") or ""
                if expected:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    status = "ok" if digest == expected else "bad_hash"
                else:
                    status = "unverified"
            self.models[key] = ModelInfo(
                key=key,
                file=spec["file"],
                sha256=spec.get("sha256") or "",
                path=path,
                status=status,
            )

    def health(self) -> dict[str, str]:
        return {k: m.status for k, m in self.models.items()}

    def require(self, key: str) -> Path:
        info = self.models.get(key)
        if info is None or info.status == "missing":
            raise FileNotFoundError(key)
        if info.status in {"bad_hash", "unverified"}:
            raise ValueError(f"hash inválido: {key}")
        return info.path

    def path_if_ok(self, key: str) -> Path | None:
        info = self.models.get(key)
        if info and info.status == "ok":
            return info.path
        return None
