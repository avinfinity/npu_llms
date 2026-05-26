param(
  [switch]$Clean,
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Remove-IfExists {
  param([string]$Path)

  if (Test-Path -LiteralPath $Path) {
    Write-Host "Removing $Path"
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
}

function Run-Step {
  param(
    [string]$Name,
    [scriptblock]$Command
  )

  Write-Host ""
  Write-Host "==> $Name"
  & $Command
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

if ($Clean) {
  Remove-IfExists "build"
  Remove-IfExists "dist"
  Get-ChildItem -Directory -Filter "*.egg-info" | ForEach-Object {
    Remove-IfExists $_.FullName
  }
}

Run-Step "Install build dependencies" {
  python -m pip install --upgrade pip build
}

Run-Step "Install project dependencies" {
  python -m pip install ".[windows-installer]"
}

Run-Step "Verify Hugging Face dependency" {
  python -c "from huggingface_hub import snapshot_download"
}

Run-Step "Build Python package" {
  python -m build
}

Run-Step "Build PyInstaller bundle" {
  python -m PyInstaller packaging\npu-ollama.spec --clean --noconfirm
}

if (-not (Test-Path -LiteralPath "dist\npu-ollama\npu-ollama.exe")) {
  throw "PyInstaller bundle was not created at dist\npu-ollama\npu-ollama.exe"
}

if ($SkipInstaller) {
  Write-Host ""
  Write-Host "Build complete: dist\npu-ollama\npu-ollama.exe"
  exit 0
}

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
  $candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
  )
  $isccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
} else {
  $isccPath = $iscc.Source
}

if (-not $isccPath) {
  Write-Host ""
  Write-Host "Build complete: dist\npu-ollama\npu-ollama.exe"
  Write-Host "Installer skipped because Inno Setup was not found. Install Inno Setup 6 or run with -SkipInstaller."
  exit 0
}

Run-Step "Build installer" {
  & $isccPath packaging\npu-ollama.iss
}

if (-not (Test-Path -LiteralPath "dist\npu-ollama-setup.exe")) {
  throw "Installer was not created at dist\npu-ollama-setup.exe"
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "  Bundle:    dist\npu-ollama\npu-ollama.exe"
Write-Host "  Installer: dist\npu-ollama-setup.exe"
