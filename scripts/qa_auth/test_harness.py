"""Fast safety/fixture regressions; no database, auth mocks or paid providers."""

import ast
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import MagicMock, patch

import run
import runtime


class HarnessTests(unittest.TestCase):
    def test_environment_is_allowlisted_and_uses_only_lane_services(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-poison", "GOOGLE_CLIENT_SECRET": "synthetic-poison"}):
            env = run.environment(Path(os.environ["QA_AUTH_ARTIFACTS"]))
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("GOOGLE_CLIENT_SECRET", env)
        self.assertIn("127.0.0.1:55443/qa01", env["DATABASE_URL"])
        self.assertEqual(env["REDIS_URL"], "redis://127.0.0.1:56443/0")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_next_dotenv_is_refused_without_opening_it(self):
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "open", side_effect=AssertionError("must not read dotenv")):
            with self.assertRaisesRegex(RuntimeError, "dotenv"):
                run.no_frontend_dotenv()

    def test_all_four_ports_are_checked_before_service_creation(self):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        with patch.object(socket, "socket", return_value=sock):
            run.ports_unused()
        self.assertEqual(sock.bind.call_args_list, [unittest.mock.call(("127.0.0.1", port)) for port in (3203, 8203, 55443, 56443)])

    def test_busy_port_is_a_hard_failure(self):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        sock.bind.side_effect = OSError("port occupied")
        with patch.object(socket, "socket", return_value=sock), self.assertRaises(OSError):
            run.ports_unused()

    def test_provider_network_is_denied_before_dns_or_connect(self):
        # Restore the global socket functions on exit, even if this test fails.
        with patch.object(socket, "getaddrinfo", socket.getaddrinfo), patch.object(socket.socket, "connect", socket.socket.connect):
            runtime.local_network_only()
            with self.assertRaisesRegex(OSError, "forbids external"):
                socket.getaddrinfo("api.openai.com", 443)
            with socket.socket() as sock, self.assertRaisesRegex(OSError, "forbids external"):
                sock.connect(("8.8.8.8", 443))

    def test_python_sources_compile_without_writing_bytecode(self):
        for file in run.RUNTIME.parent.glob("*.py"):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        file = run.ROOT / "backend/tests/test_pilot_auth_journeys.py"
        ast.parse(file.read_text(encoding="utf-8"), filename=str(file))


if __name__ == "__main__":
    unittest.main()
