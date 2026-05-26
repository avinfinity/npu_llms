import os
import sys
from pathlib import Path


APP_NAME = "NPUOllama"


def app_home() -> Path:
    override = os.getenv("NPU_OLLAMA_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
        return Path(base) / APP_NAME
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "npu-ollama"


def models_dir() -> Path:
    return Path(os.getenv("NPU_OLLAMA_MODELS", app_home() / "models")).expanduser()


def logs_dir() -> Path:
    return Path(os.getenv("NPU_OLLAMA_LOGS", app_home() / "logs")).expanduser()


def state_dir() -> Path:
    return Path(os.getenv("NPU_OLLAMA_STATE", app_home() / "state")).expanduser()


def ensure_dirs() -> None:
    for path in (models_dir(), logs_dir(), state_dir()):
        path.mkdir(parents=True, exist_ok=True)

