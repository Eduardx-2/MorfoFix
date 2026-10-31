from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = {
    "requests",
    "httpx",
    "urllib",
    "urllib.request",
    "aiohttp",
}

ROOT = Path(__file__).resolve().parent.parent / "morfofix_engine"


def test_engine_ast_no_network_imports() -> None:
    hits: list[str] = []
    for py in ROOT.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in {"requests", "httpx", "aiohttp"}:
                        hits.append(f"{py}: import {alias.name}")
                    if alias.name == "urllib" or alias.name.startswith("urllib."):
                        hits.append(f"{py}: import {alias.name}")
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top = mod.split(".")[0]
                if top in {"requests", "httpx", "aiohttp", "urllib"}:
                    hits.append(f"{py}: from {mod} import ...")
    assert hits == []
