import os
import socket

import uvicorn

from .api import app
from .paths import ensure_dirs
from .networking import (
    DEFAULT_HOST,
    resolve_port
)


def serve(host: str | None = None, port: int | None = None) -> None:
    ensure_dirs()
    host = host or DEFAULT_HOST
    port = resolve_port(host, port)
    uvicorn.run(
        app,
        host=host,
        port=port,
    )


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
