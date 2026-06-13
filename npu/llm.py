import json
import logging
import threading
from pathlib import Path
from queue import Queue
from typing import Optional, Iterator, Callable

import openvino as ov
import openvino_genai as ov_genai

from .store import model_path as get_model_path

logger = logging.getLogger(__name__)


if not hasattr(ov, "get_available_devices"):

    def _get_available_devices():

        return ov.Core().available_devices

    ov.get_available_devices = _get_available_devices


class NPULLM:

    def __init__(
        self,
        model_path: str,
        device: str = "NPU",
    ):

        self.model_path = model_path
        self.model_name = Path(model_path).name
        self.device = self._validate_device(device)

        self._lock = threading.Lock()

        logger.info(
            f"Loading model={self.model_name} "
            f"device={self.device}"
        )

        self.model_config = self._load_json(
            "config.json"
        )

        self.tokenizer_config = self._load_json(
            "tokenizer_config.json"
        )

        self.capabilities = self._detect_capabilities()

        self.pipe = ov_genai.LLMPipeline(
            self.model_path,
            self.device
        )

        if self.capabilities["supports_chat"]:
            try:
                self.pipe.start_chat()
                logger.info("Chat mode enabled")
            except Exception:
                logger.warning(
                    "Chat template exists but "
                    "chat initialization failed"
                )

    ##################################################
    # Metadata loading
    ##################################################

    def _load_json(
        self,
        filename
    ):

        path = Path(self.model_path) / filename

        if not path.exists():
            return {}

        try:
            with open(
                path,
                encoding="utf8"
            ) as f:

                return json.load(f)

        except Exception as e:

            logger.warning(
                f"Could not load {filename}: {e}"
            )

            return {}

    ##################################################
    # Device handling
    ##################################################

    def _validate_device(
        self,
        device
    ):

        available = ov.get_available_devices()

        npu = next(
            (
                d for d in available
                if "NPU" in d
            ),
            None
        )

        if npu:
            return npu

        raise RuntimeError(
            f"NPU not available. "
            f"Available={available}"
        )

    ##################################################
    # Model capability detection
    ##################################################

    def _detect_capabilities(
        self
    ):

        chat_template = bool(
            self.tokenizer_config.get(
                "chat_template"
            )
        )

        prompt_wrapper = (
            self.model_config.get(
                "prompt_wrapper"
            )
        )

        prompt_format = (
            self.model_config.get(
                "prompt_format"
            )
        )

        is_rag = (
            "context_passage"
            in str(prompt_format)
        )

        return {

            "supports_chat":
                chat_template,

            "prompt_wrapper":
                prompt_wrapper,

            "prompt_format":
                prompt_format,

            "rag":
                is_rag
        }

    ##################################################
    # Prompt construction
    ##################################################

    def _build_prompt(
        self,
        prompt,
        context=""
    ):

        cap = self.capabilities

        if cap["supports_chat"]:
            return prompt

        if cap["prompt_wrapper"]:

            template = (
                cap["prompt_format"]
                or
                "<human>\n{question}\n<bot>:"
            )

            return (
                template
                .replace(
                    "{question}",
                    prompt
                )
                .replace(
                    "{context_passage}",
                    context
                )
            )

        return prompt

    ##################################################
    # Generation
    ##################################################

    def generate(
        self,
        prompt: str,
        context: str = "",
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.1,
    ):

        prompt = self._build_prompt(
            prompt,
            context
        )

        config = ov_genai.GenerationConfig()

        config.max_new_tokens = max_new_tokens
        config.temperature = temperature
        config.top_p = top_p
        config.repetition_penalty = repetition_penalty

        with self._lock:

            return self.pipe.generate(
                prompt,
                config
            )

    ##################################################
    # Streaming
    ##################################################

    def stream_generate(
        self,
        prompt: str,
        context=""
    ) -> Iterator[str]:

        q = Queue()

        prompt = self._build_prompt(
            prompt,
            context
        )

        config = ov_genai.GenerationConfig()

        config.max_new_tokens = 512
        config.temperature = .7

        def streamer(token):

            q.put(token)
            return False

        def run():

            try:

                self.pipe.generate(
                    prompt,
                    config,
                    streamer
                )

            finally:

                q.put(None)

        threading.Thread(
            target=run,
            daemon=True
        ).start()

        while True:

            item = q.get()

            if item is None:
                break

            yield item

    ##################################################
    # Cleanup
    ##################################################

    def close(self):

        try:
            if self.capabilities[
                "supports_chat"
            ]:

                self.pipe.finish_chat()

        except:
            pass


##################################################
# Singleton
##################################################

_instance = None
_lock = threading.Lock()
_current_model = None
_current_device = None


def get_llm(
    model_path: Optional[str] = None,
    device: str = "NPU"
):

    global _instance, _current_model, _current_device

    # Resolve model path if just name provided
    if model_path:
        resolved_path = str(get_model_path(model_path))
    else:
        resolved_path = None

    # Check if we need to reload (model or device changed)
    needs_reload = (
        _instance is None or
        (resolved_path and resolved_path != _current_model) or
        device != _current_device
    )

    if needs_reload:

        with _lock:

            needs_reload = (
                _instance is None or
                (resolved_path and resolved_path != _current_model) or
                device != _current_device
            )

            if needs_reload:

                if not resolved_path:
                    raise ValueError("model_path required")

                _instance = NPULLM(
                    resolved_path,
                    device
                )

                _current_model = resolved_path
                _current_device = device

    return _instance


def reset_llm():

    global _instance, _current_model, _current_device

    if _instance:

        _instance.close()

    _instance = None
    _current_model = None
    _current_device = None
