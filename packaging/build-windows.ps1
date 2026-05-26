$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip build pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m PyInstaller packaging\npu-ollama.spec --clean --noconfirm
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
  & $isccPath packaging\npu-ollama.iss
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Write-Host "PyInstaller bundle created at dist\npu-ollama. Install Inno Setup to produce a single .exe installer."
}
