import unittest
from unittest.mock import patch

from npu_ollama import llm as npu_llm


class FakePipeline:
    def __init__(self, model_path, device, config=None):
        self.model_path = model_path
        self.device = device
        self.config_was_passed = config is not None
        self.config = config or {}
        self.started = 0
        self.finished = 0
        self.calls = []

    def start_chat(self):
        self.started += 1

    def finish_chat(self):
        self.finished += 1

    def generate(self, prompt, streamer=None, **options):
        self.calls.append((prompt, options))
        output = f"answer: {prompt}"
        if streamer:
            for chunk in ["answer", ": ", prompt]:
                streamer(chunk)
        return output


class NPULLMTests(unittest.TestCase):
    def test_loads_pipeline_on_npu_with_model_path(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(model_path="./models/llama3.2", device="NPU")

        self.assertEqual(llm.model_name, "llama3.2")
        self.assertEqual(llm.device, "NPU")
        self.assertEqual(llm._pipe.model_path, "models\\llama3.2")
        self.assertEqual(llm._pipe.device, "NPU")
        self.assertTrue(llm._pipe.config_was_passed)
        self.assertEqual(llm._pipe.config["MAX_PROMPT_LEN"], 8192)
        self.assertEqual(llm._pipe.config["MIN_RESPONSE_LEN"], 150)
        self.assertNotIn("PREFILL_HINT", llm._pipe.config)

    def test_can_override_npu_prompt_window(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(
                model_path="./models/llama3.2",
                device="NPU",
                max_prompt_len=8192,
                min_response_len=256,
            )

        self.assertEqual(llm.pipeline_config, {"MAX_PROMPT_LEN": 8192, "MIN_RESPONSE_LEN": 256})
        self.assertEqual(llm._pipe.config, {"MAX_PROMPT_LEN": 8192, "MIN_RESPONSE_LEN": 256})

    def test_does_not_pass_npu_only_config_to_gpu(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(model_path="./models/llama3.2", device="GPU")

        self.assertEqual(llm.pipeline_config, {})
        self.assertFalse(llm._pipe.config_was_passed)
        self.assertEqual(llm._pipe.config, {})

    def test_does_not_pass_npu_only_config_to_cpu(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(model_path="./models/llama3.2", device="CPU")

        self.assertEqual(llm.pipeline_config, {})
        self.assertFalse(llm._pipe.config_was_passed)
        self.assertEqual(llm._pipe.config, {})

    def test_can_opt_into_npu_performance_hints(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(
                model_path="./models/llama3.2",
                device="NPU",
                prefill_hint="STATIC",
                generate_hint="BEST_PERF",
            )

        self.assertEqual(llm._pipe.config["PREFILL_HINT"], "STATIC")
        self.assertEqual(llm._pipe.config["GENERATE_HINT"], "BEST_PERF")

    def test_generate_starts_and_finishes_chat(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(model_path="./models/llama3.2", device="NPU")
            response = llm.generate("hello", max_new_tokens=16, temperature=0.2)

        self.assertEqual(response, "answer: hello")
        self.assertEqual(llm._pipe.started, 1)
        self.assertEqual(llm._pipe.finished, 1)
        self.assertEqual(llm._pipe.calls[0], ("hello", {"max_new_tokens": 16, "temperature": 0.2}))

    def test_stream_generate_yields_chunks(self):
        with patch.object(npu_llm, "LLMPipeline", FakePipeline):
            llm = npu_llm.NPULLM(model_path="./models/llama3.2", device="NPU")
            chunks = list(llm.stream_generate("hello", max_new_tokens=16))

        self.assertEqual(chunks, ["answer", ": ", "hello"])


if __name__ == "__main__":
    unittest.main()
