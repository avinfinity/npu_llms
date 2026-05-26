import os
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Callable, Iterator, Optional

from .paths import models_dir
from .store import installed_models, model_path

LLMPipeline = None
StreamingStatus = None

DEFAULT_MODEL_NAME = os.getenv("NPU_MODEL", "llama-3.2-1b-instruct-npu-ov")
DEFAULT_MODEL_PATH = os.getenv("NPU_MODEL_PATH")
DEFAULT_DEVICE = os.getenv("NPU_DEVICE", "NPU")
DEFAULT_MAX_PROMPT_LEN = int(os.getenv("NPU_MAX_PROMPT_LEN", "8192"))
DEFAULT_MIN_RESPONSE_LEN = int(os.getenv("NPU_MIN_RESPONSE_LEN", "150"))
DEFAULT_PREFILL_HINT = os.getenv("NPU_PREFILL_HINT")
DEFAULT_GENERATE_HINT = os.getenv("NPU_GENERATE_HINT")


def is_npu_device(device: str) -> bool:
    return "NPU" in device.upper()


def resolve_model_path(model: Optional[str] = None) -> Path:
    if DEFAULT_MODEL_PATH and model is None:
        return Path(DEFAULT_MODEL_PATH)
    name = model or DEFAULT_MODEL_NAME
    candidate = model_path(name)
    if candidate.exists():
        return candidate
    legacy = Path("models") / name
    if legacy.exists():
        return legacy
    direct = Path(name)
    if direct.exists():
        return direct
    installed = installed_models()
    if installed:
        return Path(str(installed[0]["path"]))
    return models_dir() / name


class NPULLM:
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = DEFAULT_DEVICE,
        max_prompt_len: int = DEFAULT_MAX_PROMPT_LEN,
        min_response_len: int = DEFAULT_MIN_RESPONSE_LEN,
        prefill_hint: Optional[str] = DEFAULT_PREFILL_HINT,
        generate_hint: Optional[str] = DEFAULT_GENERATE_HINT,
    ):
        self.model_path = str(Path(model_path) if model_path else resolve_model_path())
        self.device = device
        self.model_name = Path(self.model_path).name
        self.max_prompt_len = max_prompt_len
        self.min_response_len = min_response_len
        self.prefill_hint = prefill_hint
        self.generate_hint = generate_hint
        self.loaded_at = time.time()
        self.pipeline_config = self._build_pipeline_config()
        self._pipe = self._load_pipeline()
        self._lock = threading.Lock()

    def _load_pipeline(self):
        global LLMPipeline, StreamingStatus
        if LLMPipeline is None:
            import openvino_genai as ov_genai

            LLMPipeline = ov_genai.LLMPipeline
            StreamingStatus = ov_genai.StreamingStatus
        elif StreamingStatus is None:
            class _StreamingStatus:
                RUNNING = "RUNNING"

            StreamingStatus = _StreamingStatus

        if self.pipeline_config:
            return LLMPipeline(self.model_path, self.device, self.pipeline_config)
        return LLMPipeline(self.model_path, self.device)

    def _build_pipeline_config(self) -> dict:
        if not is_npu_device(self.device):
            return {}
        config = {
            "MAX_PROMPT_LEN": self.max_prompt_len,
            "MIN_RESPONSE_LEN": self.min_response_len,
        }
        if self.prefill_hint:
            config["PREFILL_HINT"] = self.prefill_hint
        if self.generate_hint:
            config["GENERATE_HINT"] = self.generate_hint
        return config

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 4000,
        streamer: Optional[Callable[[str], object]] = None,
        **options,
    ) -> str:
        generation_options = {"max_new_tokens": max_new_tokens}
        generation_options.update({key: value for key, value in options.items() if value is not None})

        with self._lock:
            self._pipe.start_chat()
            try:
                return self._pipe.generate(prompt, streamer=streamer, **generation_options)
            finally:
                self._pipe.finish_chat()

    def stream_generate(self, prompt: str, max_new_tokens: int = 4000, **options) -> Iterator[str]:
        chunks: Queue[Optional[str]] = Queue()
        errors: Queue[BaseException] = Queue()

        def streamer(subword: str):
            chunks.put(subword)
            return StreamingStatus.RUNNING

        def run_generation():
            try:
                self.generate(prompt, max_new_tokens=max_new_tokens, streamer=streamer, **options)
            except BaseException as exc:
                errors.put(exc)
            finally:
                chunks.put(None)

        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

        while True:
            chunk = chunks.get()
            if chunk is None:
                break
            yield chunk

        if not errors.empty():
            raise errors.get()


_llm: Optional[NPULLM] = None
_llm_lock = threading.Lock()


def reset_llm() -> None:
    global _llm
    with _llm_lock:
        _llm = None


def get_llm(model: Optional[str] = None) -> NPULLM:
    global _llm
    if _llm is None or (model and _llm.model_name.lower() != model.lower()):
        with _llm_lock:
            if _llm is None or (model and _llm.model_name.lower() != model.lower()):
                path = str(resolve_model_path(model)) if model else None
                _llm = NPULLM(model_path=path)
    return _llm
