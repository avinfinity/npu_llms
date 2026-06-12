# networking.py

import os
import socket

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11435
FALLBACK_PORT = 11436


def env_port() -> int | None:

    value = (
        os.getenv("NPU_PORT")
        or os.getenv("npu_port")
    )

    if not value:
        return None

    try:
        return int(value)

    except ValueError:
        return None


def is_port_available(
    host: str,
    port: int
) -> bool:

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    ) as sock:

        sock.settimeout(.5)

        return (
            sock.connect_ex(
                (host, port)
            )
            != 0
        )


def resolve_port(
    host: str = DEFAULT_HOST,
    port: int | None = None
) -> int:

    # explicit parameter wins
    if port is not None:
        return port

    # env variable next
    env = env_port()

    if env is not None:
        return env

    # preferred ports
    for p in (
        DEFAULT_PORT,
        FALLBACK_PORT
    ):

        if is_port_available(
            host,
            p
        ):

            return p

    # dynamic search
    for p in range(
        FALLBACK_PORT + 1,
        65535
    ):

        if is_port_available(
            host,
            p
        ):

            return p

    raise RuntimeError(
        "No available port found"
    )


def base_url(
    host: str = DEFAULT_HOST,
    port: int | None = None
):

    return (
        f"http://{host}:{resolve_port(host,port)}"
    )
