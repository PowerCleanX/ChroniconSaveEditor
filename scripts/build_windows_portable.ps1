Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Expected virtual environment interpreter at $python"
}

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --name ChroniconSaveEditor `
  --windowed `
  --onefile `
  --collect-all PySide6 `
  --collect-data chronicon_save_editor `
  src\chronicon_save_editor\__main__.py

Write-Host "Portable build created at dist\\ChroniconSaveEditor.exe"
