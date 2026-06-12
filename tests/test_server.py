import socket
import unittest
from unittest.mock import patch

from npu import cli
from npu import server


class ServerPortTests(unittest.TestCase):
    def test_prefers_npu_port_env(self):
        with patch.dict("os.environ", {"NPU_PORT": "11500"}, clear=True):
            self.assertEqual(server.resolve_port("127.0.0.1"), 11500)

    def test_uses_default_port_when_available(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(server.resolve_port("127.0.0.1"), 11435)

    def test_falls_back_when_default_port_is_taken(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 11435))
            sock.listen(1)
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(server.resolve_port("127.0.0.1"), 11436)

    def test_cli_serve_defers_default_port_selection_to_server(self):
        with patch("npu.server.serve") as serve:
            self.assertEqual(cli.main(["serve"]), 0)

        serve.assert_called_once_with(host="127.0.0.1", port=None)

    def test_cli_serve_explicit_port_overrides_resolution(self):
        with patch("npu.server.serve") as serve:
            self.assertEqual(cli.main(["serve", "--port", "11500"]), 0)

        serve.assert_called_once_with(host="127.0.0.1", port=11500)


if __name__ == "__main__":
    unittest.main()
