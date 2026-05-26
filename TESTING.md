# Testing

Run the mocked unit/API tests without starting FastAPI or loading the real NPU model:

```powershell
.\.npu-env\Scripts\python.exe -m unittest discover -s tests -v
```

Start the Ollama-compatible FastAPI server explicitly when you want it:

```powershell
.\.npu-env\Scripts\python.exe run_api.py
```

By default, `run_api.py` listens on `127.0.0.1:11435`. Override it with:

```powershell
$env:OLLAMA_HOST = "127.0.0.1"
$env:OLLAMA_PORT = "11435"
.\.npu-env\Scripts\python.exe run_api.py
```

The NPU prompt window defaults to 8192 tokens. Change it before starting the API if your prompts or chat history need a different limit:

```powershell
$env:NPU_MAX_PROMPT_LEN = "8192"
.\.npu-env\Scripts\python.exe run_api.py
```

`PREFILL_HINT` and `GENERATE_HINT` are NPU-only performance options. The app does not send them by default because newer OpenVINO versions enable dynamic prefill automatically when `MAX_PROMPT_LEN` is larger than the prefill chunk size. Only set them if your installed OpenVINO/NPU driver combination supports them:

```powershell
$env:NPU_PREFILL_HINT = "STATIC"
$env:NPU_GENERATE_HINT = "BEST_PERF"
.\.npu-env\Scripts\python.exe run_api.py
```

In a second terminal, run the live API test against the manually started server:

```powershell
$env:RUN_LIVE_API_TESTS = "1"
.\.npu-env\Scripts\python.exe -m unittest tests.test_api.LiveAPITests -v
```

The live test sends a real `/api/generate` request to `http://127.0.0.1:11435/api/generate`, so it will load the configured OpenVINO model onto the NPU.
