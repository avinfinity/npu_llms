import os

import uvicorn

from .paths import ensure_dirs


def serve(host: str | None = None, port: int | None = None) -> None:
    ensure_dirs()
    uvicorn.run(
        "npu_ollama.api:app",
        host=host or os.getenv("OLLAMA_HOST", "127.0.0.1"),
        port=port or int(os.getenv("OLLAMA_PORT", "11435")),
    )


def main() -> None:
    serve()


if __name__ == "__main__":
    main()

