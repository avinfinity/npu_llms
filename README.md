# NPU Ollama

[![Build Installer](https://github.com/avinfinity/npu_llms/actions/workflows/main.yml/badge.svg)](https://github.com/avinfinity/npu_llms/actions/workflows/main.yml)

NPU Ollama packages the existing OpenVINO GenAI NPU loader behind an Ollama-compatible API, CLI, and minimal local chat UI.

## Developer install

```powershell
python -m pip install -e .[dev]
npu-ollama pull llama-3.2-1b-instruct-npu-ov
npu-ollama start
npu-ollama run llama-3.2-1b-instruct-npu-ov
```

The API listens on `http://127.0.0.1:11435` by default and exposes `/api/generate`, `/api/chat`, `/api/tags`, and `/api/version`.

## CLI

```powershell
npu-ollama list
npu-ollama list --installed
npu-ollama ps
npu-ollama pull llama-3.2-1b-instruct-npu-ov
npu-ollama run llama-3.2-1b-instruct-npu-ov "Say hello"
npu-ollama rm llama-3.2-1b-instruct-npu-ov
```

Models are stored in `%LOCALAPPDATA%\NPUOllama\models` on Windows unless `NPU_OLLAMA_HOME` or `NPU_OLLAMA_MODELS` is set. The model registry is loaded from `NPU_OLLAMA_REGISTRY_URL` when available and falls back to the bundled registry.
By default, `npu-ollama list` reads the public llmware NPU OpenVINO collection at `https://huggingface.co/collections/llmware/npu-openvino`; override it with `NPU_OLLAMA_HF_COLLECTION`.

## Windows startup

```powershell
npu-ollama install-startup
```

This creates a per-user Windows Task Scheduler entry named `NPU Ollama` that starts the API server at logon. The installer scripts in `packaging/` use the same command after installation.

## Build a single Windows installer

```powershell
python -m pip install .[windows-installer]
powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
```

The build uses PyInstaller to collect Python, OpenVINO GenAI, the API, CLI, and UI into `dist\npu-ollama`, then compiles an Inno Setup installer when `ISCC.exe` is available.

The Windows installer checks for an enabled Intel NPU device before setup proceeds. If the NPU driver is missing, setup opens Intel's NPU Driver for Windows download page and exits; install the driver, reboot if requested, then run setup again.
