import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from . import __version__
from .paths import ensure_dirs, state_dir
from .registry import load_registry
from .store import installed_models, pull_model, remove_model


DEFAULT_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("NPU_PORT") or os.getenv("npu_port") or os.getenv("OLLAMA_PORT") or "11435")
FALLBACK_PORT = 11436


def base_url(port: int | None = None) -> str:
    return f"http://{DEFAULT_HOST}:{port or DEFAULT_PORT}"


def candidate_base_urls() -> list[str]:
    if os.getenv("NPU_PORT") or os.getenv("npu_port") or os.getenv("OLLAMA_PORT"):
        return [base_url()]
    return [base_url(11435), base_url(FALLBACK_PORT)]


def pid_file() -> Path:
    return state_dir() / "server.pid"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="npu-ollama", description="Run NPU optimized LLMs behind an Ollama-compatible API.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List NPU OpenVINO models from the llmware Hugging Face collection.")
    list_parser.add_argument("--remote", action="store_true", help="Deprecated alias; list already uses the remote collection.")
    list_parser.add_argument("--installed", action="store_true", help="Show only locally installed models.")

    sub.add_parser("ps", help="Show the local API daemon status.")

    rm_parser = sub.add_parser("rm", help="Remove an installed model.")
    rm_parser.add_argument("model")

    pull_parser = sub.add_parser("pull", help="Pull an NPU optimized model from the registry.")
    pull_parser.add_argument("model")

    run_parser = sub.add_parser("run", help="Start the API if needed and chat with a model.")
    run_parser.add_argument("model", nargs="?", default=os.getenv("NPU_MODEL", "llama-3.2-1b-instruct-npu-ov"))
    run_parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt.")

    serve_parser = sub.add_parser("serve", help="Run the Ollama-compatible API server in the foreground.")
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
    serve_parser.add_argument("--port", type=int, default=None)

    start_parser = sub.add_parser("start", help="Start the API server in the background.")
    start_parser.add_argument("--wait", type=float, default=30.0)

    sub.add_parser("install-startup", help="Install a Windows logon task that starts the API server.")
    sub.add_parser("uninstall-startup", help="Remove the Windows logon startup task.")

    args = parser.parse_args(argv)

    if args.command == "list":
        return cmd_list(installed=args.installed)
    if args.command == "ps":
        return cmd_ps()
    if args.command == "rm":
        return cmd_rm(args.model)
    if args.command == "pull":
        return cmd_pull(args.model)
    if args.command == "run":
        return cmd_run(args.model, " ".join(args.prompt).strip())
    if args.command == "serve":
        from .server import serve

        serve(host=args.host, port=args.port)
        return 0
    if args.command == "start":
        return cmd_start(wait_seconds=args.wait)
    if args.command == "install-startup":
        return cmd_install_startup()
    if args.command == "uninstall-startup":
        return cmd_uninstall_startup()
    return 2


def cmd_list(installed: bool = False) -> int:
    if not installed:
        installed_names = {str(row["name"]) for row in _safe_installed_models()}
        rows = []
        for model in load_registry():
            row = model.__dict__.copy()
            row["installed"] = "yes" if model.name in installed_names else ""
            rows.append(row)
        _print_table(rows, ["name", "installed", "npu", "family", "size", "repo"])
        return 0
    try:
        rows = installed_models()
    except OSError as exc:
        print(f"Could not read the model store: {exc}")
        return 1
    if not rows:
        print("No models installed. Try: npu-ollama pull llama-3.2-1b-instruct-npu-ov")
        return 0
    _print_table(rows, ["name", "format", "family", "size", "path"])
    return 0


def _safe_installed_models() -> list[dict]:
    try:
        return installed_models()
    except OSError:
        return []


def cmd_ps() -> int:
    url, health = _find_running_server()
    pid = _read_pid()
    if health:
        print(f"NAME        PID       HOST                  MODEL       DEVICE")
        print(f"npu-ollama  {pid or '-':<8} {url:<21} {health.get('model') or '-':<11} {health.get('device') or '-'}")
        return 0
    print("No npu-ollama server is responding.")
    if pid:
        print(f"Last recorded PID: {pid}")
    return 1


def cmd_rm(model: str) -> int:
    path = remove_model(model)
    print(f"removed {model} from {path}")
    return 0


def cmd_pull(model: str) -> int:
    ensure_dirs()
    print(f"pulling {model}...")
    path = pull_model(model)
    print(f"success: {path}")
    return 0


def cmd_start(wait_seconds: float = 30.0) -> int:
    ensure_dirs()
    url, health = _find_running_server()
    if health:
        print(f"npu-ollama is already running at {url}")
        return 0
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    log_path = state_dir() / "server-start.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            _server_command(),
            stdout=log,
            stderr=log,
            creationflags=creationflags,
            close_fds=not sys.platform.startswith("win"),
        )
    pid_file().write_text(str(process.pid), encoding="utf-8")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            print(f"npu-ollama server exited while starting. See {log_path}")
            _print_startup_log_tail()
            return 1
        url, health = _find_running_server()
        if health:
            print(f"npu-ollama started at {url} (pid {process.pid})")
            return 0
        time.sleep(0.5)
    print(f"started pid {process.pid}; server is still warming up at {base_url()}")
    return 0


def cmd_run(model: str, prompt: str = "") -> int:
    if not _is_installed(model):
        cmd_pull(model)
    os.environ["NPU_MODEL"] = model
    if not _ensure_server_ready(wait_seconds=60.0):
        return 1
    if prompt:
        try:
            response = _post_json(
                "/api/chat",
                {"model": model, "stream": False, "messages": [{"role": "user", "content": prompt}]},
            )
        except RuntimeError as exc:
            print(exc)
            _print_startup_log_tail()
            return 1
        print(response.get("message", {}).get("content", ""))
        return 0
    print("Enter /bye to exit.")
    messages = []
    while True:
        try:
            text = input(">>> ").strip()
        except EOFError:
            print()
            return 0
        if text in {"/bye", "/exit", "/quit"}:
            return 0
        if not text:
            continue
        messages.append({"role": "user", "content": text})
        try:
            response = _post_json("/api/chat", {"model": model, "stream": False, "messages": messages})
        except RuntimeError as exc:
            print(exc)
            _print_startup_log_tail()
            return 1
        reply = response.get("message", {}).get("content", "")
        print(reply)
        messages.append({"role": "assistant", "content": reply})


def cmd_install_startup() -> int:
    if not sys.platform.startswith("win"):
        print("install-startup is currently implemented for Windows Task Scheduler.")
        return 1
    task = " ".join(f'"{part}"' if " " in part else part for part in _server_command())
    subprocess.run(
        ["schtasks", "/Create", "/TN", "NPU Ollama", "/SC", "ONLOGON", "/RL", "LIMITED", "/F", "/TR", task],
        check=True,
    )
    print("installed Windows logon task: NPU Ollama")
    return 0


def cmd_uninstall_startup() -> int:
    if not sys.platform.startswith("win"):
        print("uninstall-startup is currently implemented for Windows Task Scheduler.")
        return 1
    subprocess.run(["schtasks", "/Delete", "/TN", "NPU Ollama", "/F"], check=True)
    print("removed Windows logon task: NPU Ollama")
    return 0


def _is_installed(model: str) -> bool:
    return any(row["name"] == model for row in installed_models())


def _read_pid() -> Optional[str]:
    path = pid_file()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def _server_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "serve"]
    return [sys.executable, "-m", "npu_ollama.server"]


def _ensure_server_ready(wait_seconds: float) -> bool:
    ensure_dirs()
    url, health = _find_running_server()
    if health:
        return True

    if cmd_start(wait_seconds=wait_seconds) != 0:
        return False
    url, health = _find_running_server()
    if health:
        return True

    print(f"npu-ollama server did not become ready at {url}.")
    _print_startup_log_tail()
    return False


def _print_startup_log_tail(lines: int = 25) -> None:
    log_path = state_dir() / "server-start.log"
    if not log_path.exists():
        return

    try:
        log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return

    if not log_lines:
        return

    print(f"Last {min(lines, len(log_lines))} lines from {log_path}:")
    for line in log_lines[-lines:]:
        print(line)


def _get_json(path: str) -> Optional[Dict[str, Any]]:
    for url in candidate_base_urls():
        try:
            with urlopen(url + path, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            continue
    return None


def _find_running_server() -> tuple[str, Optional[Dict[str, Any]]]:
    for url in candidate_base_urls():
        try:
            with urlopen(url + "/health", timeout=2) as response:
                return url, json.loads(response.read().decode("utf-8"))
        except Exception:
            continue
    return base_url(), None


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    url, _ = _find_running_server()
    request = Request(url + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Could not reach npu-ollama at {url}: {exc}") from exc


def _print_table(rows: Iterable[Dict[str, Any]], columns: list[str]) -> None:
    rows = list(rows)
    widths = {column: len(column.upper()) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row.get(column, ""))))
    print("  ".join(column.upper().ljust(widths[column]) for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


if __name__ == "__main__":
    raise SystemExit(main())
