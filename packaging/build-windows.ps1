$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pip install ".[windows-installer]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -c "from huggingface_hub import snapshot_download"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m PyInstaller packaging\npu.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

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

if ($isccPath) {
  & $isccPath packaging\npu.iss
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Write-Host "PyInstaller bundle created at dist\npu. Install Inno Setup to produce a single .exe installer."
}
