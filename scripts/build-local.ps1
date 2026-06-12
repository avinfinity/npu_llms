param(
  [switch]$Clean,
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$VenvDir = ".build-venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"

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
  Remove-IfExists $VenvDir
  Get-ChildItem -Directory -Filter "*.egg-info" | ForEach-Object {
    Remove-IfExists $_.FullName
  }
}

if (-not (Test-Path -LiteralPath $Python)) {
  Run-Step "Create build virtual environment" {
    python -m venv $VenvDir
  }
}

Run-Step "Install build dependencies" {
  & $Python -m pip install --upgrade pip build
}

Run-Step "Install project dependencies" {
  & $Python -m pip install ".[windows-installer]"
}

Run-Step "Verify Hugging Face dependency" {
  & $Python -c "from huggingface_hub import snapshot_download"
}

Run-Step "Build Python package" {
  & $Python -m build
}

Run-Step "Build PyInstaller bundle" {
  & $Python -m PyInstaller packaging\npu.spec --clean --noconfirm
}

if (-not (Test-Path -LiteralPath "dist\npu\npu.exe")) {
  throw "PyInstaller bundle was not created at dist\npu\npu.exe"
}

if ($SkipInstaller) {
  Write-Host ""
  Write-Host "Build complete: dist\npu\npu.exe"
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
  Write-Host "Build complete: dist\npu\npu.exe"
  Write-Host "Installer skipped because Inno Setup was not found. Install Inno Setup 6 or run with -SkipInstaller."
  exit 0
}

Run-Step "Build installer" {
  & $isccPath packaging\npu.iss
}

if (-not (Test-Path -LiteralPath "dist\npu-setup.exe")) {
  throw "Installer was not created at dist\npu-setup.exe"
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "  Bundle:    dist\npu\npu.exe"
Write-Host "  Installer: dist\npu-setup.exe"
