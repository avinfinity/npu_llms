import json
import logging
import time
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .llm import get_llm
from .paths import logs_dir
from .registry import load_registry, model_rows
from .store import installed_models


app = FastAPI(title="NPU Ollama-Compatible API")
ACCESS_LOG_PATH = logs_dir() / "api-server.log"
_access_log_lock = Lock()
logger = logging.getLogger(__name__)


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _write_access_log(request: Request, status_code: int, elapsed_ms: float) -> None:
    http_version = request.scope.get("http_version", "1.1")
    phrase = _status_phrase(status_code)
    status = f"{status_code} {phrase}".strip()
    line = (
        f'{_now()} "{request.method} {request.url.path} HTTP/{http_version}" '
        f"{status} {elapsed_ms:.2f}ms\n"
    )
    with _access_log_lock:
        ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACCESS_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(line)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        logger.exception("Unhandled request error")
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        _write_access_log(request, status_code, elapsed_ms)


class GenerateRequest(BaseModel):
    model: Optional[str] = None
    prompt: str = ""
    stream: bool = False
    options: Dict[str, Any] = Field(default_factory=dict)
    system: Optional[str] = None
    template: Optional[str] = None
    raw: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str = ""


class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    options: Dict[str, Any] = Field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _generation_options(options: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "max_new_tokens",
        "temperature",
        "top_p",
        "top_k",
        "repetition_penalty",
        "num_beams",
        "do_sample",
    }
    mapped = dict(options)
    if "num_predict" in mapped and "max_new_tokens" not in mapped:
        mapped["max_new_tokens"] = mapped.pop("num_predict")
    return {key: value for key, value in mapped.items() if key in allowed}


def _model_name(requested: Optional[str]) -> str:
    return requested or get_llm().model_name


def _json_line(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _format_prompt(messages: Iterable[ChatMessage]) -> str:
    lines = []
    for message in messages:
        role = message.role.strip().lower() or "user"
        lines.append(f"{role}: {message.content}")
    lines.append("assistant:")
    return "\n".join(lines)


def _model_tags() -> List[Dict[str, Any]]:
    try:
        rows = installed_models()
    except OSError:
        rows = []
    if not rows:
        llm = get_llm()
        rows = [
            {
                "name": llm.model_name,
                "path": getattr(llm, "model_path", ""),
                "size": 0,
                "format": "openvino",
            }
        ]
    tags = []
    for row in rows:
        name = str(row["name"])
        tags.append(
            {
                "name": name,
                "model": name,
                "modified_at": row.get("installed_at") or _now(),
                "size": row.get("size", 0),
                "digest": "",
                "details": {
                    "format": row.get("format", "openvino"),
                    "family": row.get("family", "llm"),
                    "families": [row.get("family", "llm")],
                    "parameter_size": row.get("size", "unknown"),
                    "quantization_level": "int4",
                },
            }
        )
    return tags


@app.get("/", response_class=HTMLResponse)
def root():
    return Path(__file__).with_name("static").joinpath("chat.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    try:
        llm = get_llm()
        model = llm.model_name
        device = llm.device
    except Exception:
        model = None
        device = None
    return {"status": "ok", "service": "npu-ollama", "model": model, "device": device}


@app.get("/api/version")
def version():
    return {"version": f"{__version__}-npu"}


@app.get("/api/tags")
def tags():
    return {"models": _model_tags()}


@app.get("/api/registry")
def registry():
    return {"models": model_rows(load_registry())}


@app.post("/api/generate")
@app.post("/generate")
def generate(request: GenerateRequest):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    llm = get_llm(request.model)
    model = _model_name(request.model)
    options = _generation_options(request.options)
    max_new_tokens = int(options.pop("max_new_tokens", 4000))
    started = time.perf_counter_ns()

    if request.stream:
        def event_stream():
            eval_count = 0
            for chunk in llm.stream_generate(request.prompt, max_new_tokens=max_new_tokens, **options):
                eval_count += 1
                yield _json_line({"model": model, "created_at": _now(), "response": chunk, "done": False})
            yield _json_line(
                {
                    "model": model,
                    "created_at": _now(),
                    "response": "",
                    "done": True,
                    "total_duration": time.perf_counter_ns() - started,
                    "load_duration": 0,
                    "eval_count": eval_count,
                    "eval_duration": time.perf_counter_ns() - started,
                }
            )

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    response = llm.generate(request.prompt, max_new_tokens=max_new_tokens, **options)
    return {
        "model": model,
        "created_at": _now(),
        "response": response,
        "done": True,
        "total_duration": time.perf_counter_ns() - started,
        "load_duration": 0,
        "eval_count": len(str(response).split()),
        "eval_duration": time.perf_counter_ns() - started,
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages are required")

    llm = get_llm(request.model)
    model = _model_name(request.model)
    prompt = _format_prompt(request.messages)
    options = _generation_options(request.options)
    max_new_tokens = int(options.pop("max_new_tokens", 4000))
    started = time.perf_counter_ns()

    if request.stream:
        def event_stream():
            eval_count = 0
            for chunk in llm.stream_generate(prompt, max_new_tokens=max_new_tokens, **options):
                eval_count += 1
                yield _json_line(
                    {
                        "model": model,
                        "created_at": _now(),
                        "message": {"role": "assistant", "content": chunk},
                        "done": False,
                    }
                )
            yield _json_line(
                {
                    "model": model,
                    "created_at": _now(),
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                    "total_duration": time.perf_counter_ns() - started,
                    "load_duration": 0,
                    "eval_count": eval_count,
                    "eval_duration": time.perf_counter_ns() - started,
                }
            )

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    response = llm.generate(prompt, max_new_tokens=max_new_tokens, **options)
    return {
        "model": model,
        "created_at": _now(),
        "message": {"role": "assistant", "content": response},
        "done": True,
        "total_duration": time.perf_counter_ns() - started,
        "load_duration": 0,
        "eval_count": len(str(response).split()),
        "eval_duration": time.perf_counter_ns() - started,
    }
