$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $PSScriptRoot "../../mofixPy"))) {
  $Root = Resolve-Path (Join-Path $PSScriptRoot "../..")
}
$Engine = Join-Path $Root "mofixPy"
$Tauri = Join-Path $Root "rusting"

Set-Location $Engine
python scripts/fetch_models.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pyinstaller morfofix-engine.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location $Tauri
cargo tauri build
