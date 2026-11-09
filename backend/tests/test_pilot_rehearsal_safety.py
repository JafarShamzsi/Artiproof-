"""Offline OPS-01 guard regressions; no app settings, services or credentials."""

import importlib.util
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/pilot_rehearsal/rehearse.py"
spec = importlib.util.spec_from_file_location("ops01_rehearse", SCRIPT)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class SafetyTests(unittest.TestCase):
    def test_only_explicit_synthetic_loopback_target(self):
        ops.validate_target("postgresql://ops01_synthetic@127.0.0.1:55446/ops01_synthetic_source")
        for url in (
            "postgresql://ops01_synthetic@localhost:55446/ops01_synthetic_source",
            "postgresql://ops01_synthetic@192.168.1.2:55446/ops01_synthetic_source",
            "postgresql://ops01_synthetic@prod.example:55446/ops01_synthetic_source",
            "postgresql://ops01_synthetic@127.0.0.1:5432/ops01_synthetic_source",
            "postgresql://ops01_synthetic@127.0.0.1:55446/artiproof",
            "postgresql://postgres@127.0.0.1:55446/ops01_synthetic_source",
            "postgresql://ops01_synthetic:secret@127.0.0.1:55446/ops01_synthetic_source",
            "postgresql://ops01_synthetic@127.0.0.1:55446/ops01_synthetic_source?host=live",
            "postgresql://ops01_synthetic@127.0.0.1:55446/ops01_synthetic_source#live",
            "sqlite:///ops01_synthetic_source",
        ):
            with self.subTest(url=url), self.assertRaises(ops.Unsafe):
                ops.validate_target(url)

    def test_occupied_port_blocks_without_contact(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaises(ops.Unsafe):
                ops.assert_ports_free([listener.getsockname()[1]])

    def test_scratch_escape_and_existing_run_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ops, "SCRATCH", root):
                with self.assertRaises(ops.Unsafe):
                    ops.new_run(root.parent / "escape")
                run = root / "ops01-test"
                ops.new_run(run)
                marker = run / "keep.txt"
                marker.write_text("preexisting", encoding="utf-8")
                with self.assertRaises(ops.Unsafe):
                    ops.new_run(run)
                self.assertEqual(marker.read_text(), "preexisting")

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ops, "SCRATCH", root / "scratch"):
                # Mock resolution to cover Windows junctions without symlink privilege.
                with patch.object(Path, "resolve", return_value=root / "outside"):
                    with self.assertRaises(ops.Unsafe):
                        ops.new_run(root / "scratch" / "ops01-test")

    def test_missing_postgres_is_blocked_not_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ops.preflight(Path(tmp), None)
            self.assertEqual(result["release_status"], "BLOCKED")
            self.assertEqual(result["recovery_status"], "BLOCKED")

    def test_migration_graph_rejects_multiple_heads_and_unknown_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("revision = 'a'\ndown_revision = None\n")
            self.assertEqual(ops.migration_head(root), "a")
            (root / "b.py").write_text("revision = 'b'\ndown_revision = None\n")
            with self.assertRaises(ops.Unsafe):
                ops.migration_head(root)
            (root / "b.py").write_text("revision = 'b'\ndown_revision = 'missing'\n")
            with self.assertRaises(ops.Unsafe):
                ops.migration_head(root)

    def test_child_environment_does_not_forward_credentials(self):
        with patch.dict("os.environ", {"PGPASSWORD": "never", "AWS_SECRET_ACCESS_KEY": "never"}):
            env = ops.child_env(Path("synthetic"))
        self.assertNotIn("PGPASSWORD", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertEqual(env["PGCONNECT_TIMEOUT"], "3")

    def test_hash_mismatch_blocks_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "synthetic.pdf"
            artifact.write_bytes(b"changed")
            with self.assertRaises(ops.Unsafe):
                ops.verify_hash(artifact, "0" * 64)

    def test_rehearsal_refuses_missing_tools_before_subprocess(self):
        with patch.object(ops.subprocess, "run") as execute:
            with self.assertRaises(ops.Unsafe):
                ops.rehearse(Path("unused"), Path("missing-tools"), Path("unused"))
            execute.assert_not_called()

    def test_mocked_lifecycle_stops_only_its_cluster_and_never_cleans(self):
        # Command/guard contract only: NOT PostgreSQL recovery evidence.
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            commands = []

            def execute(argv, **kwargs):
                commands.append(argv)
                tool = argv[0]
                output = ""
                if tool == "initdb":
                    (run / "cluster").mkdir()
                if tool == "pg_dump":
                    (run / "backup/database.dump").write_bytes(b"synthetic mock dump")
                if tool == "psql" and "SELECT version_num" in argv[-1]:
                    output = "0018_analysis_runs"
                if tool == "psql" and "SELECT id ||" in argv[-1]:
                    output = "1|synthetic.pdf|" + ops.digest(run / "backup/synthetic.pdf")
                return subprocess.CompletedProcess(argv, 0, output, "")

            with patch.object(ops, "tool_paths", return_value={x: x for x in ops.PG_TOOLS}), \
                    patch.object(ops, "assert_ports_free"), \
                    patch.object(ops, "migration_head", return_value="0018_analysis_runs"), \
                    patch.object(ops.subprocess, "run", side_effect=execute):
                result = ops.rehearse(run, run, run)
            self.assertEqual(result["release_status"], "BLOCKED")
            self.assertEqual(commands[-1][-1], "stop")
            self.assertEqual(commands[-1][2], str(run / "cluster"))
            self.assertTrue((run / "backup/database.dump").is_file())
            self.assertEqual(sum(x[0] == "pg_restore" for x in commands), 2)
            self.assertFalse(any("--clean" in x or "dropdb" in x for x in commands))

    def test_start_failure_attempts_stop_of_owned_cluster(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            commands = []

            def execute(argv, **kwargs):
                commands.append(argv)
                if argv[0] == "initdb":
                    (run / "cluster").mkdir()
                return subprocess.CompletedProcess(argv, 1 if argv[-1] == "start" else 0, "", "")

            with patch.object(ops, "tool_paths", return_value={x: x for x in ops.PG_TOOLS}), \
                    patch.object(ops, "assert_ports_free"), \
                    patch.object(ops, "migration_head", return_value="0018_analysis_runs"), \
                    patch.object(ops.subprocess, "run", side_effect=execute):
                with self.assertRaises(ops.Unsafe):
                    ops.rehearse(run, run, run)
            self.assertEqual(commands[-1][-1], "stop")
            self.assertFalse(any(x[0] == "psql" for x in commands))

    def test_cli_requires_explicit_confirmation(self):
        with patch("sys.argv", [str(SCRIPT), "rehearse"]), \
                patch.object(ops, "new_run") as create:
            self.assertEqual(ops.main(), 2)
            create.assert_not_called()

    def test_occupied_rehearsal_port_prevents_all_subprocesses(self):
        with patch.object(ops, "tool_paths", return_value={x: x for x in ops.PG_TOOLS}), \
                patch.object(ops, "migration_head", return_value="0018_analysis_runs"), \
                patch.object(ops, "assert_ports_free", side_effect=ops.Unsafe("occupied")), \
                patch.object(ops.subprocess, "run") as execute:
            with self.assertRaises(ops.Unsafe):
                ops.rehearse(Path("unused"), Path("unused"), Path("unused"))
            execute.assert_not_called()

    def test_initdb_failure_never_stops_any_cluster(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            with patch.object(ops, "tool_paths", return_value={x: x for x in ops.PG_TOOLS}), \
                    patch.object(ops, "migration_head", return_value="0018_analysis_runs"), \
                    patch.object(ops, "assert_ports_free"), \
                    patch.object(ops.subprocess, "run", return_value=
                                 subprocess.CompletedProcess([], 1, "", "init failed")) as execute:
                with self.assertRaises(ops.Unsafe):
                    ops.rehearse(run, run, run)
                self.assertEqual(execute.call_count, 1)
                self.assertEqual(execute.call_args.args[0][0], "initdb")

    def test_cli_cannot_report_pass_if_stop_or_recovery_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ops, "SCRATCH", root), \
                    patch("sys.argv", [str(SCRIPT), "rehearse", "--pg-bin", "missing",
                                       "--confirm-synthetic-only", "--run-name", "ops01-failed"]), \
                    patch.object(ops, "preflight", return_value={}), \
                    patch.object(ops, "rehearse", side_effect=ops.Unsafe("pg_ctl stop failed")):
                self.assertEqual(ops.main(), 2)
            import json
            evidence = json.loads((root / "ops01-failed/evidence.json").read_text())
            self.assertEqual(evidence["recovery_status"], "BLOCKED")

    def test_duplicate_and_disconnected_migration_cycles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("revision = 'a'\ndown_revision = None\n")
            (root / "b.py").write_text("revision = 'a'\ndown_revision = None\n")
            with self.assertRaises(ops.Unsafe):
                ops.migration_head(root)
            (root / "b.py").write_text("revision = 'b'\ndown_revision = 'c'\n")
            (root / "c.py").write_text("revision = 'c'\ndown_revision = 'b'\n")
            with self.assertRaises(ops.Unsafe):
                ops.migration_head(root)


if __name__ == "__main__":
    unittest.main()
