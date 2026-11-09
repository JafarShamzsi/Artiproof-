"""Reviewed failure regressions. All Docker/process failure paths are MOCKED.

Original main() reproductions failed twice at b837cf4; red log retained in scratch.
The corrected ownership seam lets every failure be exercised without OS lifecycle.
"""

import json
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run
from lifecycle import LOCAL_DOCKER, LocalDocker, RunOwner, validate_endpoint
from owned_process import OwnedProcess, ProcessConstructionError


class CleanupFaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="correction-mocks-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.owner = RunOwner(self.directory, {}, process_factory=MagicMock())

    def evidence(self):
        return json.loads((self.directory / "checks.json").read_text())

    def intent(self, name="owned", attempted=True):
        record = {"name": name, "labels": {"artiproof.qa.run": self.owner.run_id, "artiproof.qa.resource": name},
                  "attempted": attempted, "state": "ambiguous"}
        self.owner.containers.append(record)
        return record

    def metadata(self, record):
        return {"id": "a" * 64, "name": "/" + record["name"], "labels": dict(record["labels"]), "running": True}

    def test_process_stop_timeout_still_cleans_containers_and_writes_evidence(self):
        record = self.intent()
        process = MagicMock()
        process.stop.side_effect = subprocess.TimeoutExpired("owned", 10)
        self.owner.processes.append({"process": process, "record": {"label": "owned-child"}, "log": MagicMock()})
        docker = MagicMock()
        self.owner.original_error = "original readiness failure"
        self.owner.cleanup(docker)
        docker.cleanup.assert_called_once_with(record)
        self.assertEqual(self.evidence()["original_error"], "original readiness failure")
        self.assertEqual(len(self.evidence()["cleanup_errors"]), 2)  # initial + bounded final attempt
        self.assertEqual(process.stop.call_count, 2)
        self.assertEqual(self.evidence()["status"], "failed")

    def test_create_timeout_after_side_effect_is_not_untracked(self):
        docker = LocalDocker(self.owner)
        def create_timeout(args, **kwargs):
            ledger = json.loads((self.directory / "inventory.json").read_text())
            self.assertEqual(ledger["containers"][0]["state"], "create-attempt-ambiguous")
            self.assertTrue(ledger["containers"][0]["attempted"])
            self.assertEqual(ledger["containers"][0]["labels"]["artiproof.qa.run"], self.owner.run_id)
            raise subprocess.TimeoutExpired("mock-create-after-side-effect", 60)
        with patch.object(docker, "inspect", return_value=None), patch.object(docker, "call", side_effect=create_timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                docker.create("redis", 56443, 6379, [], "mock-image")
        record = self.owner.containers[0]
        with patch.object(docker, "inspect", side_effect=[self.metadata(record), None]), patch.object(docker, "call", return_value=MagicMock(returncode=0)) as call:
            self.owner.original_error = "create timeout"
            self.owner.cleanup(docker)
        self.assertEqual(call.call_args.args[0], ["stop", "--time", "5", "a" * 64])
        self.assertEqual(record["cleanup"], "confirmed-absent-after-stop")
        self.assertEqual(self.evidence()["original_error"], "create timeout")

    def test_container_stop_timeout_and_nonzero_continue_remaining_cleanup(self):
        for failure in (subprocess.TimeoutExpired("mock-stop", 15), MagicMock(returncode=7)):
            with self.subTest(failure=type(failure).__name__):
                self.owner.containers.clear()
                first, second = self.intent("first"), self.intent("second")
                docker = LocalDocker(self.owner)
                def inspect(identity):
                    if identity == "a" * 64:
                        return None
                    return self.metadata(first if identity == "first" else second)
                effects = [failure, MagicMock(returncode=0)]
                with patch.object(docker, "inspect", side_effect=inspect), patch.object(docker, "call", side_effect=effects) as call:
                    self.owner.cleanup(docker)
                self.assertEqual(call.call_count, 2)
                self.assertTrue(self.evidence()["cleanup_errors"])
                self.assertEqual(first["cleanup"], "confirmed-absent-after-stop")

    def test_wrong_ownership_never_stops_unrelated_resource(self):
        for defect in ("run", "resource", "name", "id", "missing_labels"):
            with self.subTest(defect=defect):
                self.owner.containers.clear()
                record = self.intent()
                record["container_id"] = "a" * 64
                value = self.metadata(record)
                if defect in ("run", "resource"):
                    value["labels"][f"artiproof.qa.{defect}"] = "someone-else"
                elif defect == "missing_labels":
                    value["labels"] = {}
                else:
                    value[defect] = "/someone-else" if defect == "name" else "b" * 64
                docker = LocalDocker(self.owner)
                with patch.object(docker, "inspect", return_value=value), patch.object(docker, "call") as call:
                    self.owner.cleanup(docker)
                call.assert_not_called()
                self.assertEqual(record["cleanup"], "uncertain-or-refused")
                self.assertTrue(self.owner.failed())

    def test_preexisting_name_collision_never_authorizes_cleanup_even_matching_labels(self):
        docker = LocalDocker(self.owner)
        with patch.object(docker, "inspect", return_value={"existing": True}), patch.object(docker, "call") as call:
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                docker.create("redis", 56443, 6379, [], "mock-image")
            self.owner.cleanup(docker)
        call.assert_not_called()
        self.assertFalse(self.owner.containers[0]["attempted"])

    def test_name_race_after_preflight_does_not_adopt_preexisting_matching_labels(self):
        docker = LocalDocker(self.owner)
        def conflict(args, **kwargs):
            name = self.owner.containers[-1]["name"]
            return subprocess.CompletedProcess([], 125, f'Conflict. The container name "/{name}" is already in use', "")
        with patch.object(docker, "inspect", return_value=None) as inspect, patch.object(docker, "call", side_effect=conflict) as call:
            with self.assertRaisesRegex(RuntimeError, "create failed"):
                docker.create("redis", 56443, 6379, [], "mock-image")
            self.owner.cleanup(docker)
        self.assertEqual(inspect.call_count, 1)  # preflight only, no adoption
        self.assertEqual(call.call_count, 1)  # create only, no stop
        self.assertEqual(self.owner.containers[0]["cleanup"], "name-collision-no-stop")

    def test_exited_parent_still_stops_owned_descendants(self):
        process = MagicMock()
        process.poll.return_value = 0
        self.owner.processes.append({"process": process, "record": {"label": "exited-parent"}, "log": MagicMock()})
        self.owner.cleanup()
        process.stop.assert_called_once_with(timeout=10)
        process.poll.assert_not_called()  # root status never gates tree cleanup

    def test_ambiguous_create_not_observed_is_uncertain_not_a_cleanup_pass(self):
        record = self.intent()
        record["state"] = "create-attempt-ambiguous"
        docker = LocalDocker(self.owner)
        with patch.object(docker, "inspect", return_value=None), patch.object(docker, "call") as call:
            self.owner.cleanup(docker)
        call.assert_not_called()
        self.assertEqual(record["cleanup"], "uncertain-or-refused")
        self.assertTrue(self.owner.failed())

    def test_inspect_timeout_does_not_skip_next_container(self):
        first, second = self.intent("first"), self.intent("second")
        docker = LocalDocker(self.owner)
        with patch.object(docker, "inspect", side_effect=[subprocess.TimeoutExpired("mock inspect", 15), None]) as inspect:
            self.owner.cleanup(docker)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(first["cleanup"], "confirmed-absent")
        self.assertEqual(second["cleanup"], "uncertain-or-refused")

    def test_command_timeout_remains_original_when_stop_also_times_out(self):
        process = MagicMock()
        process.wait.side_effect = subprocess.TimeoutExpired("original command timeout", 30)
        process.stop.side_effect = subprocess.TimeoutExpired("cleanup timeout", 10)
        self.owner.factory = MagicMock(return_value=process)
        with self.assertRaises(subprocess.TimeoutExpired) as original:
            self.owner.command("original", ["mock"], timeout=30)
        self.assertEqual(original.exception.cmd, "original command timeout")
        self.owner.original_error = str(original.exception)
        self.owner.cleanup()
        self.assertIn("original command timeout", self.evidence()["original_error"])
        self.assertGreaterEqual(len(self.evidence()["cleanup_errors"]), 2)

    def test_successful_launcher_with_uncertain_tree_cleanup_cannot_continue(self):
        process = MagicMock()
        process.wait.return_value = 0
        process.stop.side_effect = subprocess.TimeoutExpired("descendant cleanup", 10)
        self.owner.factory = MagicMock(return_value=process)
        with self.assertRaisesRegex(RuntimeError, "cleanup uncertain"):
            self.owner.command("launcher-exited-zero", ["mock"])
        self.owner.cleanup()
        self.assertEqual(self.evidence()["status"], "failed")

    def test_inventory_write_error_does_not_suppress_checks_evidence(self):
        with patch.object(self.owner, "save_inventory", side_effect=OSError("mock disk error")):
            self.owner.cleanup()
        self.assertEqual(self.evidence()["cleanup_errors"][0]["resource"], "inventory.json")

    def test_closed_but_unconfirmed_object_cannot_report_cleanup_success(self):
        process = OwnedProcess.__new__(OwnedProcess)
        process.closed = True
        process.root_exit_confirmed = False
        process.tree_exit_confirmed = True
        process.stop = MagicMock()  # model the reviewed closed-object no-op
        self.owner.processes.append({"process": process, "record": {"label": "closed-unconfirmed"}, "log": MagicMock()})
        self.owner.cleanup()
        entry = self.owner.processes[0]
        self.assertFalse(entry["cleanup_complete"])
        self.assertEqual(entry["stop_attempts"], 2)
        self.assertEqual(entry["record"]["state"], "cleanup-unresolved")
        self.assertEqual(entry["record"]["cleanup_disposition"], "unresolved-budget-exhausted")
        self.assertEqual(entry["record"]["exit_confirmation"], {"root": False, "tree": True, "handles_closed": True})
        self.assertEqual(self.evidence()["unresolved_processes"], [entry["record"]])
        self.assertEqual(self.evidence()["status"], "failed")
        self.assertEqual(process.stop.call_count, 2)

    def test_unassigned_owner_exhaustion_retains_live_handles_and_original_failure(self):
        from test_final_safety import FreshOwnerRegressionTests
        fake, process, error = FreshOwnerRegressionTests().abort_fault("terminate-failed")
        self.owner.factory = MagicMock(side_effect=error)
        with self.assertRaises(ProcessConstructionError) as caught:
            self.owner.command("retained-root", ["mock"])
        self.assertIs(caught.exception, error)
        self.owner.original_error = str(error)
        docker = MagicMock()
        self.owner.containers.extend([{"name": "later"}, {"name": "first"}])
        self.owner.cleanup(docker)
        entry = self.owner.processes[0]
        self.assertEqual(entry["stop_attempts"], 2)
        self.assertEqual(fake.kernel.TerminateProcess.call_count, 3)  # one constructor + two owner
        self.assertTrue(fake.alive)
        self.assertIsNotNone(process.process)
        self.assertFalse(process.closed)
        self.assertEqual(entry["record"]["cleanup_disposition"], "unresolved-budget-exhausted")
        self.assertEqual(len(entry["record"]["cleanup_failures"]), 2)
        self.assertTrue(entry["record"]["cleanup_failures"][0]["diagnostics"])
        self.assertEqual(docker.cleanup.call_count, 2)
        self.assertEqual(self.evidence()["original_error"], str(error))
        self.assertEqual(len(self.evidence()["unresolved_processes"]), 1)
        self.assertEqual(self.evidence()["status"], "failed")
        calls = fake.kernel.TerminateProcess.call_count
        self.owner.cleanup()
        self.assertEqual(fake.kernel.TerminateProcess.call_count, calls, "repeated cleanup cannot reset budget")

    def test_unresolved_ownership_fails_even_without_a_recorded_cleanup_exception(self):
        self.owner.processes.append({"process": MagicMock(), "record": {"label": "pending"}, "log": MagicMock()})
        self.assertFalse(self.owner.failed(), "running resources are not unresolved before finalization")
        self.owner._finalizing = True
        self.assertTrue(self.owner.failed())

    def test_constructor_ownership_retry_can_resolve_but_never_erase_original_failure(self):
        from test_final_safety import FreshOwnerRegressionTests
        fake, process, error = FreshOwnerRegressionTests().abort_fault("terminate-failed")
        self.owner.factory = MagicMock(side_effect=error)
        with self.assertRaises(ProcessConstructionError):
            self.owner.command("retry-root", ["mock"])
        fake.kernel.TerminateProcess.side_effect = fake.terminate
        self.owner.original_error = str(error)
        self.owner.cleanup()
        entry = self.owner.processes[0]
        self.assertEqual(entry["stop_attempts"], 2)
        self.assertTrue(entry["cleanup_complete"])
        self.assertEqual(entry["record"]["state"], "exit-confirmed-handles-closed")
        self.assertTrue(process.cleanup_complete)
        self.assertEqual(self.evidence()["unresolved_processes"], [])
        self.assertEqual(self.evidence()["status"], "failed")
        self.assertEqual(self.evidence()["original_error"], str(error))

    def test_multiple_cleanup_errors_and_original_failure_are_aggregated(self):
        self.intent("one")
        self.intent("two")
        docker = MagicMock()
        docker.cleanup.side_effect = RuntimeError("mock inspect error")
        self.owner.original_error = "original assertion"
        self.owner.cleanup(docker)
        self.assertEqual(docker.cleanup.call_count, 2)
        self.assertEqual(len(self.evidence()["cleanup_errors"]), 2)
        self.assertEqual(self.evidence()["original_error"], "original assertion")

    def test_red_journey_still_runs_later_independent_checks_and_fails(self):
        def factory(command, **kwargs):
            kwargs["on_created"]({"pid": 123, "creation_filetime": 456, "job_name": kwargs["job_name"]})
            process = MagicMock()
            process.wait.return_value = 1 if command == ["mock-red-journey"] else 0
            return process
        self.owner.factory = factory
        self.owner.command("journey", ["mock-red-journey"], required=False)
        self.owner.command("resources", ["mock-green"], required=False)
        self.owner.command("api", ["mock-green"], required=False)
        self.owner.cleanup()
        self.assertEqual([item["exit_code"] for item in self.evidence()["checks"]], [1, 0, 0])
        self.assertEqual(self.evidence()["status"], "failed")

    def test_main_all_is_held_instead_of_executing_browser_chain(self):
        # Manager's final correction supersedes the old main(all) behavior.
        # Lower-level red-result aggregation remains tested above, not bypassed.
        with patch.object(run, "RunOwner") as owner, patch.object(run, "LocalDocker") as docker, patch.object(run, "require_service_support") as support, patch.object(run, "ports_unused"), patch.object(run.sys, "argv", ["run.py", "all"]):
            with self.assertRaisesRegex(RuntimeError, "Browser execution hold"):
                run.main()
        owner.assert_not_called()
        docker.assert_not_called()
        support.assert_not_called()

    def test_process_identity_persisted_before_factory_resumes(self):
        def factory(command, **kwargs):
            self.assertEqual(json.loads((self.directory / "inventory.json").read_text())["processes"][0]["state"], "intent")
            kwargs["on_created"]({"pid": 123, "creation_filetime": 456})
            record = json.loads((self.directory / "inventory.json").read_text())["processes"][0]
            self.assertEqual((record["pid"], record["creation_filetime"], record["state"]), (123, 456, "owned-suspended"))
            return MagicMock()
        self.owner.factory = factory
        self.owner.start("safe-mock", ["mock"])
        self.owner.cleanup()

    def test_unsupported_process_mode_fails_before_any_docker_spawn(self):
        with patch.object(run, "SCRATCH", self.directory), patch.object(run, "RunOwner", return_value=self.owner), patch.object(run, "LocalDocker") as docker, patch.object(run, "require_service_support", side_effect=RuntimeError("unsupported Job mode")), patch.object(run, "ports_unused"), patch.object(run, "no_frontend_dotenv"), patch.object(run.sys, "argv", ["run.py", "api"]):
            with self.assertRaisesRegex(RuntimeError, "unsupported Job"):
                run.main()
        docker.assert_not_called()
        self.owner.factory.assert_not_called()


class EndpointTests(unittest.TestCase):
    def test_remote_and_unsupported_targets_rejected_before_spawn(self):
        for platform, endpoint in (("nt", "tcp://127.0.0.1:2375"), ("nt", "ssh://remote"), ("nt", "npipe:////./pipe/other"), ("posix", LOCAL_DOCKER), ("posix", "unix:///var/run/docker.sock")):
            with self.subTest(platform=platform, endpoint=endpoint), self.assertRaises(ValueError):
                validate_endpoint(endpoint, platform)

    def test_every_docker_call_explicitly_pins_endpoint_and_empty_config(self):
        with tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="endpoint-mock-") as temporary:
            owner = RunOwner(Path(temporary), {})
            with patch.dict(run.os.environ, {"DOCKER_HOST": "ssh://remote", "DOCKER_CONTEXT": "remote-context", "DOCKER_CONFIG": "unread-credentials"}):
                docker = LocalDocker(owner)
                with patch.object(owner, "command", return_value=MagicMock(returncode=0)) as command:
                    for args in (["run"], ["inspect"], ["exec"], ["stop"], ["info"]):
                        docker.call(args)
                for call in command.call_args_list:
                    self.assertEqual(call.args[1][:5], ["docker", "--config", str(Path(temporary) / "docker-empty-config"), "--host", LOCAL_DOCKER])
                    self.assertLessEqual(call.kwargs["timeout"], 15)
                env = run.environment(Path(temporary))
                self.assertFalse(any(key.startswith("DOCKER_") for key in env))

    def test_invalid_endpoint_never_invokes_command(self):
        owner = MagicMock()
        with self.assertRaises(ValueError):
            LocalDocker(owner, "tcp://remote:2375")
        owner.command.assert_not_called()

    def test_endpoint_mutation_is_revalidated_before_every_command(self):
        with tempfile.TemporaryDirectory(dir=run.SCRATCH) as temporary:
            owner = RunOwner(Path(temporary), {})
            docker = LocalDocker(owner)
            docker.endpoint = "ssh://remote"
            with patch.object(owner, "command") as command, self.assertRaises(ValueError):
                docker.call(["stop", "anything"])
            command.assert_not_called()

    def test_invalid_command_timeout_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory(dir=run.SCRATCH) as temporary:
            owner = RunOwner(Path(temporary), {})
            docker = LocalDocker(owner)
            with patch.object(owner, "command") as command:
                for timeout in (0, -1, 61):
                    with self.assertRaises(ValueError):
                        docker.call(["inspect", "mock"], timeout=timeout)
            command.assert_not_called()

    def test_inspect_error_about_another_name_is_not_proof_of_absence(self):
        with tempfile.TemporaryDirectory(dir=run.SCRATCH) as temporary:
            owner = RunOwner(Path(temporary), {})
            docker = LocalDocker(owner)
            result = subprocess.CompletedProcess([], 1, "Error: No such container: someone-else", "")
            with patch.object(docker, "call", return_value=result), self.assertRaisesRegex(RuntimeError, "inspection failed"):
                docker.inspect("our-exact-name")


class ReadinessPolicyTests(unittest.TestCase):
    def test_exited_owned_handle_reports_exit_code_without_popen_attributes(self):
        with self.assertRaisesRegex(RuntimeError, "exited with 7"):
            run.wait_ready("http://127.0.0.1:8203/api/health", SimpleNamespace(poll=lambda: 7))

    def test_readiness_uses_no_environment_proxy_and_exact_local_url(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.status = 200
        process = MagicMock()
        process.poll.return_value = None
        with patch.object(run.urllib.request, "build_opener", return_value=opener) as build:
            run.wait_ready("http://127.0.0.1:8203/api/health", process)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], run.NoReadinessRedirect)
        opener.open.assert_called_once_with("http://127.0.0.1:8203/api/health", timeout=3)

    def test_external_readiness_rejected_before_open(self):
        with patch.object(run.urllib.request, "build_opener") as build, self.assertRaises(ValueError):
            run.wait_ready("https://external.invalid/", MagicMock())
        build.assert_not_called()

    def test_readiness_redirect_rejected_without_dispatch(self):
        with self.assertRaises(run.urllib.error.URLError):
            run.NoReadinessRedirect().redirect_request(None, None, 302, "Found", {}, "https://external.invalid/")


if __name__ == "__main__":
    unittest.main()
