# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []

for package in ["openvino", "openvino_genai", "openvino_tokenizers", "uvicorn", "fastapi", "huggingface_hub"]:
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

tokenizers_spec = importlib.util.find_spec("openvino_tokenizers")
if tokenizers_spec and tokenizers_spec.submodule_search_locations:
    tokenizers_root = Path(next(iter(tokenizers_spec.submodule_search_locations)))
    tokenizers_dll = tokenizers_root / "lib" / "openvino_tokenizers.dll"
    if tokenizers_dll.exists():
        binaries += [(str(tokenizers_dll), ".")]

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
