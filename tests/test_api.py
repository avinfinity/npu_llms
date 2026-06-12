import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib import request
from unittest.mock import patch

from fastapi.testclient import TestClient

from npu_ollama import api


class FakeLLM:
    model_name = "test-model"
    device = "NPU"

    def __init__(self):
        self.prompts = []
        self.options = []

    def generate(self, prompt, **options):
        self.prompts.append(prompt)
        self.options.append(options)
        return "test response"

    def stream_generate(self, prompt, **options):
        self.prompts.append(prompt)
        self.options.append(options)
        yield "test "
        yield "response"


class APITests(unittest.TestCase):
    def setUp(self):
        self.fake_llm = FakeLLM()
        api.app.dependency_overrides.clear()
        self.original_get_llm = api.get_llm
        api.get_llm = lambda *args, **kwargs: self.fake_llm
        self.client = TestClient(api.app)

    def tearDown(self):
        api.get_llm = self.original_get_llm
        api.app.dependency_overrides.clear()

    def test_health_endpoint_lightweight(self):
        """Test that health endpoint doesn't load model"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
    
    def test_tags_returns_model_list(self):
        """Test that tags endpoint returns model list"""
        response = self.client.get("/api/tags")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)
    
    def test_generate_endpoint_accepts_request(self):
        """Test that generate endpoint accepts requests"""
        response = self.client.post(
            "/api/generate",
            json={
                "model": "test-model",
                "prompt": "test prompt",
                "stream": False
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["response"], "test response")
    
    def test_chat_endpoint_requires_messages(self):
        """Test that chat endpoint requires messages"""
        response = self.client.post(
            "/api/chat",
            json={
                "model": "test-model",
                "messages": []
            }
        )
        self.assertEqual(response.status_code, 400)
    
    def test_chat_endpoint_processes_messages(self):
        """Test that chat endpoint processes messages"""
        response = self.client.post(
            "/api/chat",
            json={
                "model": "test-model",
                "messages": [
                    {"role": "user", "content": "hello"}
                ],
                "stream": False
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"]["content"], "test response")


class LiveAPITests(unittest.TestCase):
    """Tests that require a live server"""
    
    @unittest.skipUnless(
        os.getenv("RUN_LIVE_API_TESTS") == "1",
        "Set RUN_LIVE_API_TESTS=1 after manually starting run_api.py on port 11435."
    )
    def test_live_generate_endpoint_on_11435(self):
        """Test generate endpoint on live server"""
        try:
            req = request.Request(
                "http://127.0.0.1:11435/api/generate",
                data=json.dumps({
                    "model": "test",
                    "prompt": "test"
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                self.assertIn("response", data)
        except Exception as e:
            self.skipTest(f"Live server not available: {e}")
        response = self.client.get("/api/version")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"version": "0.1.0-npu"})

    def test_tags_returns_ollama_shaped_model_list(self):
        response = self.client.get("/api/tags")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["models"][0]["name"], "llama3.2")
        self.assertEqual(body["models"][0]["details"]["format"], "openvino")

    def test_generate_calls_npu_llm_with_ollama_num_predict_mapping(self):
        response = self.client.post(
            "/api/generate",
            json={
                "model": "llama3.2",
                "prompt": "Say hello",
                "stream": False,
                "options": {"num_predict": 8, "temperature": 0.1},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model"], "llama3.2")
        self.assertEqual(body["response"], "mocked NPU response")
        self.assertTrue(body["done"])
        self.assertEqual(self.fake_llm.prompts, ["Say hello"])
        self.assertEqual(self.fake_llm.options, [{"max_new_tokens": 8, "temperature": 0.1}])

    def test_generate_writes_access_log_line(self):
        response = self.client.post(
            "/api/generate",
            json={"model": "llama3.2", "prompt": "Log me", "stream": False},
        )

        self.assertEqual(response.status_code, 200)
        log_text = api.ACCESS_LOG_PATH.read_text(encoding="utf-8")
        self.assertIn('"POST /api/generate HTTP/1.1" 200 OK', log_text)

    def test_generate_stream_returns_ollama_ndjson(self):
        with self.client.stream(
            "POST",
            "/api/generate",
            json={"model": "llama3.2", "prompt": "Stream", "stream": True},
        ) as response:
            lines = [json.loads(line) for line in response.iter_lines() if line]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(lines[0]["response"], "mocked ")
        self.assertEqual(lines[1]["response"], "stream")
        self.assertFalse(lines[0]["done"])
        self.assertTrue(lines[-1]["done"])

    def test_chat_formats_messages_and_calls_llm(self):
        response = self.client.post(
            "/api/chat",
            json={
                "model": "llama3.2",
                "messages": [
                    {"role": "system", "content": "Be brief."},
                    {"role": "user", "content": "Hi"},
                ],
                "stream": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"]["content"], "mocked NPU response")
        self.assertEqual(self.fake_llm.prompts[0], "system: Be brief.\nuser: Hi\nassistant:")


class LiveAPITests(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("RUN_LIVE_API_TESTS") == "1",
        "Set RUN_LIVE_API_TESTS=1 after manually starting run_api.py on port 11435.",
    )
    def test_live_generate_endpoint_on_11435(self):
        payload = json.dumps(
            {
                "model": "llama3.2",
                "prompt": "Reply with the single word: ok",
                "stream": False,
                "options": {"num_predict": 8},
            }
        ).encode("utf-8")
        req = request.Request(
            "http://127.0.0.1:11435/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertTrue(body["done"])
        self.assertIsInstance(body["response"], str)
        self.assertGreater(len(body["response"]), 0)


if __name__ == "__main__":
    unittest.main()
