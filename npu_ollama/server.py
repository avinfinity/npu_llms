import os
import socket

import uvicorn

from .api import app
from .paths import ensure_dirs

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11435
FALLBACK_PORT = 11436


def _env_port() -> int | None:
    port = os.getenv("NPU_PORT") or os.getenv("npu_port") or os.getenv("OLLAMA_PORT")
    return int(port) if port else None


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def resolve_port(host: str, port: int | None = None) -> int:
    if port is not None:
        return port
    env_port = _env_port()
    if env_port is not None:
        return env_port
    if _is_port_available(host, DEFAULT_PORT):
        return DEFAULT_PORT
    return FALLBACK_PORT


def serve(host: str | None = None, port: int | None = None) -> None:
    ensure_dirs()
    host = host or os.getenv("OLLAMA_HOST", DEFAULT_HOST)
    uvicorn.run(
        app,
        host=host,
        port=resolve_port(host, port),
    )


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
