import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from npu import cli
from npu.registry import RegistryModel, load_registry


class CLITests(unittest.TestCase):
    def run_cli(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(argv)
        return code, output.getvalue()

    def test_no_command_prints_help_and_returns_error(self):
        code, output = self.run_cli([])

        self.assertEqual(code, 1)
        self.assertIn("usage:", output)

    def test_start_serves_with_host_and_port(self):
        with patch("npu.cli.server.serve") as serve:
            code, output = self.run_cli(["start", "--host", "0.0.0.0", "--port", "11500"])

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        serve.assert_called_once_with(host="0.0.0.0", port=11500)

    def test_serve_serves_with_host_and_port(self):
        with patch("npu.cli.server.serve") as serve:
            code, output = self.run_cli(["serve", "--host", "0.0.0.0", "--port", "11501"])

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        serve.assert_called_once_with(host="0.0.0.0", port=11501)

    def test_chat_dispatches_to_chat_command(self):
        with patch("npu.cli.chat", return_value=0) as chat:
            code, output = self.run_cli(
                [
                    "chat",
                    "demo-model",
                    "--device",
                    "GPU",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "11502",
                    "--no-browser",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        chat.assert_called_once_with("demo-model", "GPU", "0.0.0.0", 11502, False)

    def test_list_prints_available_registry_models_by_default(self):
        models = [
            RegistryModel(
                name="llama-3.2-1b-instruct-npu-ov",
                repo="https://huggingface.co/llmware/llama-3.2-1b-instruct-npu-ov",
            )
        ]

        with patch("npu.cli.load_registry", return_value=models):
            code, output = self.run_cli(["list"])

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "llama-3.2-1b-instruct-npu-ov")

    def test_list_installed_prints_installed_models(self):
        installed = [
            {
                "name": "local-model",
                "path": "C:\\models\\local-model",
                "size": 1,
            }
        ]

        with patch("npu.cli.installed_models", return_value=installed):
            code, output = self.run_cli(["list", "--installed"])

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "local-model")

    def test_pull_prints_pulled_model_path(self):
        path = Path("C:/models/demo-model")

        with patch("npu.cli.pull_model", return_value=path) as pull:
            code, output = self.run_cli(["pull", "demo-model"])

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), str(path))
        pull.assert_called_once_with("demo-model")

    def test_rm_removes_model(self):
        with patch("npu.cli.remove_model") as remove:
            code, output = self.run_cli(["rm", "demo-model"])

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        remove.assert_called_once_with("demo-model")

    def test_run_dispatches_model_prompt_and_device(self):
        with patch("npu.cli.run") as run:
            code, output = self.run_cli(["run", "demo-model", "Say hi", "--device", "GPU"])

        self.assertEqual(code, 0)
        self.assertEqual(output, "")
        run.assert_called_once_with("demo-model", "Say hi", "GPU")

    def test_ps_prints_ready_servers(self):
        with patch("npu.cli.candidate_ports", return_value=[11435, 11436]), patch(
            "npu.cli.is_server_ready",
            side_effect=[False, True],
        ):
            code, output = self.run_cli(["ps"])

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "npu\t127.0.0.1:11436")

    def test_install_startup_creates_scheduler_task(self):
        executable = Path("C:/Program Files/NPU/npu.exe")

        with patch("npu.cli.executable_path", return_value=executable), patch(
            "npu.cli.subprocess.run"
        ) as subprocess_run:
            code, output = self.run_cli(["install-startup", "--host", "127.0.0.1", "--port", "11503"])

        self.assertEqual(code, 0)
        self.assertIn("Installed startup task NPU", output)
        subprocess_run.assert_called_once_with(
            [
                "schtasks",
                "/Create",
                "/TN",
                "NPU",
                "/SC",
                "ONLOGON",
                "/TR",
                f'"{executable}" start --host 127.0.0.1 --port 11503',
                "/F",
            ],
            check=True,
        )

    def test_uninstall_startup_removes_scheduler_task(self):
        with patch("npu.cli.subprocess.run") as subprocess_run:
            code, output = self.run_cli(["uninstall-startup"])

        self.assertEqual(code, 0)
        self.assertIn("Removed startup task NPU", output)
        subprocess_run.assert_called_once_with(
            [
                "schtasks",
                "/Delete",
                "/TN",
                "NPU",
                "/F",
            ],
            check=True,
        )


class RegistryTests(unittest.TestCase):
    def test_empty_collection_falls_back_to_bundled_registry(self):
        with patch("npu.registry._collection_registry", return_value=[]), patch(
            "npu.registry._remote_registry",
            return_value=None,
        ):
            models = load_registry()

        self.assertGreater(len(models), 0)
        self.assertEqual(models[0].name, "llama-3.2-1b-instruct-npu-ov")


if __name__ == "__main__":
    unittest.main()
