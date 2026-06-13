import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch, MagicMock

from npu import llm as npu_llm


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
    
    def stream_generate(self, prompt, **options):
        self.calls.append((prompt, options))
        yield "answer"
        yield ": "
        yield prompt


class NoTemplatePipeline(FakePipeline):
    def start_chat(self):
        raise RuntimeError("Chat template wasn't found.")


class NPULLMTests(unittest.TestCase):
    
    def test_model_name_extracted_from_path(self):
        """Test that model_name is correctly extracted from path"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "test-model-v1"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{}')
            
            with patch("openvino.get_available_devices", return_value=["NPU", "CPU"]):
                with patch("openvino_genai.LLMPipeline", FakePipeline):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
            
            self.assertEqual(llm.model_name, "test-model-v1")
    
    def test_device_validation_succeeds_with_npu(self):
        """Test device validation when NPU is available"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "test-model"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{}')
            
            with patch("openvino.get_available_devices", return_value=["NPU", "CPU"]):
                with patch("openvino_genai.LLMPipeline", FakePipeline):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
            
            # Should not raise, and device should be set
            self.assertIsNotNone(llm.device)
    
    def test_device_validation_raises_without_npu(self):
        """Test device validation fails when NPU not available"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "test-model"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{}')
            
            with patch("openvino.get_available_devices", return_value=["CPU"]):
                with self.assertRaises(RuntimeError):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
    
    def test_chat_capability_detected_with_template(self):
        """Test that chat capability is detected when chat_template exists"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "chat-model"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{"chat_template": "{{ messages }}"}')
            
            with patch("openvino.get_available_devices", return_value=["NPU"]):
                with patch("openvino_genai.LLMPipeline", FakePipeline):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
            
            self.assertTrue(llm.capabilities.get("supports_chat"))
    
    def test_generate_method_exists(self):
        """Test that generate method exists and is callable"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "test-model"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{}')
            
            with patch("openvino.get_available_devices", return_value=["NPU"]):
                with patch("openvino_genai.LLMPipeline", FakePipeline):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
            
            self.assertTrue(callable(llm.generate))
    
    def test_stream_generate_method_exists(self):
        """Test that stream_generate method exists and is callable"""
        with TemporaryDirectory() as tmp:
            model_dir = Path(tmp) / "test-model"
            model_dir.mkdir()
            (model_dir / "config.json").write_text('{}')
            (model_dir / "tokenizer_config.json").write_text('{}')
            
            with patch("openvino.get_available_devices", return_value=["NPU"]):
                with patch("openvino_genai.LLMPipeline", FakePipeline):
                    llm = npu_llm.NPULLM(model_path=str(model_dir), device="NPU")
            
            self.assertTrue(callable(llm.stream_generate))


if __name__ == "__main__":
    unittest.main()
