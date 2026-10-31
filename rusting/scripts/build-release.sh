#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENGINE="$ROOT/mofixPy"
TAURI="$ROOT/rusting"

cd "$ENGINE"
python scripts/fetch_models.py
pytest -q
pyinstaller morfofix-engine.spec

cd "$TAURI"
if ! command -v cargo-tauri >/dev/null 2>&1; then
  cargo install tauri-cli --locked --version '^2'
fi
cargo tauri build --features desktop -- --features desktop
