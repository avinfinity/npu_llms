# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []

for package in ["openvino", "openvino_genai", "uvicorn", "fastapi", "huggingface_hub"]:
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

hiddenimports += [
    "npu_ollama.api",
    "npu_ollama.cli",
    "npu_ollama.llm",
    "npu_ollama.registry",
    "npu_ollama.server",
    "npu_ollama.store",
]

a = Analysis(
    [str(ROOT / "packaging" / "pyinstaller-entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas + [
        (str(ROOT / "npu_ollama" / "static" / "chat.html"), "npu_ollama\\static"),
        (str(ROOT / "npu_ollama" / "data" / "registry.json"), "npu_ollama\\data"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="npu-ollama",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="npu-ollama",
)
