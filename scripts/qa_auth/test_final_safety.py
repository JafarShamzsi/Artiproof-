"""Second/final review regressions. ALL process, Win32 and Docker calls mocked."""

import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import owned_process
from owned_process import OwnedProcess, ProcessConstructionError
from lifecycle import RunOwner
import run


class CleanupCreatedProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="final-safety-mocks-")
        self.addCleanup(self.temporary.cleanup)
        self.owner = RunOwner(Path(self.temporary.name), {}, process_factory=MagicMock())

    def evidence(self):
        return json.loads((self.owner.artifacts / "checks.json").read_text())

    def test_post_resume_inventory_failure_inside_container_cleanup_stops_new_process(self):
        process = MagicMock()
        self.owner.factory.return_value = process
        self.owner.containers.extend([{"name": "later"}, {"name": "failing"}])
        self.owner.original_error = "original acceptance failure"
        docker = MagicMock()
        def clean(record):
            if record["name"] == "failing":
                with patch.object(self.owner, "save_inventory", side_effect=[None, OSError("post-resume inventory failure"), None]):
                    self.owner.command("cleanup-created", ["mock-command"])
        docker.cleanup.side_effect = clean
        self.owner.cleanup(docker)
        self.assertGreaterEqual(process.stop.call_count, 1, "new resumed process must not be log-only cleanup")
        self.assertEqual(docker.cleanup.call_count, 2)
        self.assertEqual(self.evidence()["original_error"], "original acceptance failure")
        self.assertEqual(self.evidence()["status"], "failed")

    def test_cleanup_command_handle_failure_gets_bounded_final_retry(self):
        process = MagicMock()
        process.wait.return_value = 0
        process.stop.side_effect = [RuntimeError("handle close failed once"), None]
        self.owner.factory.return_value = process
        self.owner.containers.append({"name": "owned"})
        docker = MagicMock()
        docker.cleanup.side_effect = lambda record: self.owner.command("cleanup-command", ["mock-command"])
        self.owner.cleanup(docker)
        self.assertEqual(process.stop.call_count, 2)
        self.assertTrue(self.evidence()["cleanup_errors"], "transient failure must remain diagnostic")
        self.assertEqual(self.evidence()["status"], "failed")

    def test_permanent_handle_failure_is_bounded_and_does_not_skip_evidence_or_containers(self):
        process = MagicMock()
        process.wait.return_value = 0
        process.stop.side_effect = RuntimeError("persistent retained handle")
        self.owner.factory.return_value = process
        self.owner.containers.extend([{"name": "later"}, {"name": "failing"}])
        docker = MagicMock()
        docker.cleanup.side_effect = lambda record: self.owner.command("cleanup-command", ["mock"]) if record["name"] == "failing" else None
        self.owner.cleanup(docker)
        self.assertEqual(process.stop.call_count, 2)
        self.assertEqual(docker.cleanup.call_count, 2)
        self.assertEqual(self.evidence()["status"], "failed")

    def test_final_sweep_refuses_recursive_spawning_and_stops_at_two_attempts(self):
        process = MagicMock()
        process.wait.return_value = 0
        def stop(**kwargs):
            if process.stop.call_count == 1:
                raise RuntimeError("first close failure")
            with self.assertRaisesRegex(RuntimeError, "final cleanup sweep"):
                self.owner.start("must-not-spawn", ["mock"])
        process.stop.side_effect = stop
        self.owner.factory.return_value = process
        self.owner.containers.append({"name": "owned"})
        docker = MagicMock()
        docker.cleanup.side_effect = lambda record: self.owner.command("cleanup-command", ["mock"])
        self.owner.cleanup(docker)
        self.assertEqual(process.stop.call_count, 2)
        self.assertEqual(self.owner.factory.call_count, 1)
        self.assertEqual(len(self.owner.processes), 1)
        self.assertEqual(self.evidence()["status"], "failed")


class FakeKernel:
    """ctypes-compatible Python callables; never opens/creates a native object."""
    def __init__(self, *, initialize_ok=True, fail_duplicate_closes=0, fail_at=None):
        self.initialize_ok = initialize_ok
        self.fail_duplicate_closes = fail_duplicate_closes
        self.fail_at = fail_at
        self.closed = []
        self.kernel = MagicMock()
        self.kernel.CreateJobObjectW.return_value = 101
        self.kernel.SetInformationJobObject.return_value = 1
        self.kernel.GetCurrentProcess.return_value = 999
        self.kernel.InitializeProcThreadAttributeList.side_effect = self.initialize
        self.kernel.DuplicateHandle.side_effect = self.duplicate
        self.kernel.CloseHandle.side_effect = self.close
        self.kernel.UpdateProcThreadAttribute.return_value = 0 if fail_at == "attributes" else 1
        self.kernel.CreateProcessW.side_effect = self.create
        self.kernel.AssignProcessToJobObject.return_value = 0 if fail_at == "assign" else 1
        self.kernel.GetProcessTimes.return_value = 1
        self.kernel.ResumeThread.return_value = 0xFFFFFFFF if fail_at == "resume" else 1
        self.alive = False
        self.kernel.TerminateProcess.side_effect = self.terminate
        self.kernel.TerminateJobObject.side_effect = self.terminate
        self.kernel.WaitForSingleObject.side_effect = lambda *args: 258 if self.alive else 0
        self.kernel.QueryInformationJobObject.return_value = 1
        self.duplicate_index = 0

    def initialize(self, address, count, flags, size):
        if address is None:
            size._obj.value = 256
            return 0  # documented sizing call
        return int(self.initialize_ok)

    def duplicate(self, source, handle, target, output, *args):
        self.duplicate_index += 1
        output._obj.value = 200 + self.duplicate_index
        return 1

    def create(self, *args):
        info = args[-1]._obj
        info.hProcess, info.hThread, info.dwProcessId = 301, 302, 123
        self.alive = True
        return 1

    def terminate(self, *args):
        self.alive = False
        return 1

    def close(self, handle):
        value = handle.value if hasattr(handle, "value") else handle
        self.closed.append(value)
        if value == 201 and self.fail_duplicate_closes:
            self.fail_duplicate_closes -= 1
            return 0
        return 1


class ConstructorHandleTests(unittest.TestCase):
    def construct(self, fake, process, on_created=lambda identity: None, last_error=5):
        # OS calls (including error functions and raw-file-handle conversion) are mocked.
        with patch.object(owned_process.C, "WinDLL", return_value=fake.kernel), patch.object(owned_process.C, "get_last_error", return_value=last_error), patch.object(owned_process.C, "set_last_error"), patch.object(owned_process.C, "WinError", side_effect=lambda code: OSError("mock Win32 failure")), patch("msvcrt.get_osfhandle", return_value=777), patch.object(owned_process.shutil, "which", return_value="mock-python.exe"), patch.object(owned_process, "open", return_value=MagicMock(), create=True):
            process.__init__(["mock-python"], cwd=run.SCRATCH, env={}, log=MagicMock(), job_name="mock-job", on_created=on_created)

    def test_failed_attribute_initialization_never_deletes_uninitialized_buffer(self):
        fake = FakeKernel(initialize_ok=False)
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(OSError):
            self.construct(fake, process)
        fake.kernel.DeleteProcThreadAttributeList.assert_not_called()
        fake.kernel.CreateProcessW.assert_not_called()

    def test_preexisting_job_refusal_does_not_query_or_terminate_its_process_tree(self):
        fake = FakeKernel()
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(RuntimeError, "existing process Job"):
            self.construct(fake, process, last_error=183)
        fake.kernel.TerminateJobObject.assert_not_called()
        fake.kernel.QueryInformationJobObject.assert_not_called()
        self.assertEqual(fake.closed, [101])  # only our newly opened reference

    def test_failed_duplicate_handle_close_is_not_silent_success(self):
        fake = FakeKernel(fail_duplicate_closes=1)
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(RuntimeError, "cleanup"):
            self.construct(fake, process)
        self.assertEqual(fake.closed.count(201), 2, "one bounded independent retry of failed duplicate")
        self.assertEqual(fake.closed.count(202), 1, "successful duplicate must never be closed twice")
        fake.kernel.TerminateJobObject.assert_called()

    def test_persistent_duplicate_failure_retains_owned_object_for_caller_cleanup(self):
        fake = FakeKernel(fail_duplicate_closes=20)
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(RuntimeError) as raised:
            self.construct(fake, process)
        self.assertIs(getattr(raised.exception, "owned_process", None), process)
        self.assertFalse(process.closed)
        self.assertLessEqual(fake.closed.count(201), 2)

    def test_precreate_failure_deletes_only_successfully_initialized_attributes(self):
        fake = FakeKernel(fail_at="attributes")
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(OSError, "mock Win32"):
            self.construct(fake, process)
        fake.kernel.CreateProcessW.assert_not_called()
        fake.kernel.DeleteProcThreadAttributeList.assert_called_once()
        self.assertTrue(process.closed)

    def test_assignment_failure_terminates_our_suspended_root_before_closing(self):
        fake = FakeKernel(fail_at="assign")
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(OSError, "mock Win32"):
            self.construct(fake, process)
        fake.kernel.ResumeThread.assert_not_called()
        fake.kernel.TerminateProcess.assert_called_once_with(301, 1)
        self.assertTrue(process.closed)

    def test_resume_failure_terminates_assigned_job_and_preserves_original(self):
        fake = FakeKernel(fail_at="resume")
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(OSError, "mock Win32"):
            self.construct(fake, process)
        fake.kernel.TerminateJobObject.assert_called_once_with(101, 1)
        self.assertTrue(process.closed)

    def test_persist_callback_failure_does_not_resume_and_cleans_all_handles(self):
        fake = FakeKernel()
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaisesRegex(OSError, "synthetic identity persistence"):
            self.construct(fake, process, on_created=MagicMock(side_effect=OSError("synthetic identity persistence")))
        fake.kernel.ResumeThread.assert_not_called()
        self.assertTrue(process.closed)
        self.assertEqual(set(fake.closed), {101, 201, 202, 301, 302})

    def test_retained_constructor_handle_is_adopted_by_run_owner_not_lost(self):
        fake = FakeKernel(fail_duplicate_closes=3)
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(RuntimeError) as raised:
            self.construct(fake, process)
        with tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="retained-constructor-mock-") as directory:
            owner = RunOwner(Path(directory), {}, process_factory=MagicMock(side_effect=raised.exception))
            with self.assertRaises(RuntimeError) as original:
                owner.command("constructor-failed", ["mock"])
            owner.original_error = str(original.exception)
            owner.cleanup()
            self.assertIs(owner.processes[0]["process"], process)
            self.assertTrue(process.closed)
            self.assertEqual(fake.closed.count(201), 4)  # two constructor + two owner attempts
            self.assertTrue(owner.failed(), "earlier close failures must not become a passing run")

    def test_permanent_constructor_handle_failure_is_retained_after_bounded_owner_attempts(self):
        fake = FakeKernel(fail_duplicate_closes=100)
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(RuntimeError) as raised:
            self.construct(fake, process)
        with tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="persistent-constructor-mock-") as directory:
            owner = RunOwner(Path(directory), {}, process_factory=MagicMock(side_effect=raised.exception))
            with self.assertRaises(RuntimeError) as original:
                owner.command("constructor-failed", ["mock"])
            owner.original_error = str(original.exception)
            owner.cleanup()
            self.assertFalse(process.closed)
            self.assertEqual([name for name, handle in process._auxiliary_handles], ["stdin"])
            self.assertEqual(fake.closed.count(201), 4)  # finite, no fifth close hidden in a sweep
            self.assertEqual(owner.processes[0]["stop_attempts"], 2)
            self.assertTrue(owner.failed())


class FreshOwnerRegressionTests(unittest.TestCase):
    """Independent review's four failures, reproduced before QA-02 repair."""

    def abort_fault(self, mode):
        fake = FakeKernel(fail_at="assign")
        if mode == "terminate-failed":
            fake.kernel.TerminateProcess.side_effect = lambda *args: 0
        elif mode == "poll-failed":
            fake.kernel.WaitForSingleObject.side_effect = lambda *args: 0xFFFFFFFF
        elif mode == "wait-timeout":
            fake.kernel.TerminateProcess.side_effect = lambda *args: 1
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(ProcessConstructionError) as caught:
            ConstructorHandleTests().construct(fake, process)
        self.assertIs(caught.exception.owned_process, process)
        return fake, process, caught.exception

    def test_unassigned_terminate_failure_retains_live_root(self):
        fake, process, error = self.abort_fault("terminate-failed")
        self.assertFalse(fake.alive and process.process is None,
                         "live root lost its process ownership after termination failure")

    def test_unassigned_poll_failure_retains_root_for_abort(self):
        fake, process, error = self.abort_fault("poll-failed")
        self.assertFalse(fake.alive and process.process is None,
                         "WAIT_FAILED discarded ownership before confirmed root exit")

    def test_unassigned_async_timeout_retains_wait_handle(self):
        fake, process, error = self.abort_fault("wait-timeout")
        self.assertIsNotNone(process.process, "asynchronous termination is not confirmed exit")

    def test_owner_does_not_mark_live_root_cleanup_complete(self):
        fake, process, error = self.abort_fault("terminate-failed")
        with tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="qa02-independent-caller-") as directory:
            owner = RunOwner(Path(directory), {}, process_factory=MagicMock(side_effect=error))
            with self.assertRaises(ProcessConstructionError) as caught:
                owner.command("constructor-failed", ["mock"])
            self.assertIs(caught.exception, error)
            owner.original_error = str(error)
            docker = MagicMock()
            owner.containers.append({"name": "later"})
            owner.cleanup(docker)
            docker.cleanup.assert_called_once()
            evidence = json.loads((Path(directory) / "checks.json").read_text())
            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(evidence["original_error"], str(error))
            self.assertFalse(owner.processes[0].get("cleanup_complete"),
                             "closed-object no-op falsely records cleanup complete")


class ExitConfirmationTests(unittest.TestCase):
    def construct(self, fake):
        process = OwnedProcess.__new__(OwnedProcess)
        ConstructorHandleTests().construct(fake, process)
        return process

    def test_poll_failure_does_not_gate_unassigned_termination(self):
        fake, process, error = FreshOwnerRegressionTests().abort_fault("poll-failed")
        fake.kernel.TerminateProcess.assert_called_once_with(301, 1)
        self.assertIsNotNone(process.process)
        self.assertFalse(process.root_exit_confirmed)
        self.assertFalse(process.cleanup_complete)
        fake.kernel.WaitForSingleObject.side_effect = lambda *args: 0
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_eventual_unassigned_termination_closes_only_after_signaled_wait(self):
        fake, process, error = FreshOwnerRegressionTests().abort_fault("terminate-failed")
        self.assertIsNotNone(process.process)
        self.assertIsNotNone(process.thread)
        self.assertNotIn(301, fake.closed)
        self.assertNotIn(302, fake.closed)
        fake.kernel.TerminateProcess.side_effect = fake.terminate
        process.stop()
        self.assertFalse(fake.alive)
        self.assertTrue(process.root_exit_confirmed)
        self.assertTrue(process.cleanup_complete)
        self.assertEqual(fake.closed.count(301), 1)
        self.assertEqual(fake.closed.count(302), 1)

    def test_asynchronous_termination_still_requires_later_signaled_wait(self):
        fake, process, error = FreshOwnerRegressionTests().abort_fault("wait-timeout")
        fake.alive = False  # model asynchronous completion before the retry
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_close_alone_cannot_release_live_root_or_tree(self):
        fake = FakeKernel()
        process = self.construct(fake)
        with self.assertRaisesRegex(RuntimeError, "exit unresolved"):
            process.close()
        self.assertEqual((process.job, process.thread, process.process), (101, 302, 301))
        self.assertFalse(process.closed)
        self.assertFalse(process.cleanup_complete)
        fake.kernel.TerminateProcess.assert_not_called()
        fake.kernel.TerminateJobObject.assert_not_called()
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_assigned_termination_failure_preserves_first_error_and_retry_handles(self):
        fake = FakeKernel()
        process = self.construct(fake)
        fake.kernel.TerminateJobObject.side_effect = lambda *args: 0
        primary = OSError("original Job termination failure")
        with patch.object(process, "active_count", return_value=1), patch.object(owned_process.C, "get_last_error", return_value=5), patch.object(owned_process.C, "WinError", return_value=primary):
            with self.assertRaises(OSError) as caught:
                process.stop(timeout=0)
        self.assertIs(caught.exception, primary)
        self.assertTrue(primary.__notes__)
        self.assertEqual((process.job, process.thread, process.process), (101, 302, 301))
        fake.kernel.TerminateProcess.assert_not_called()
        fake.kernel.TerminateJobObject.side_effect = fake.terminate
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_wait_failed_is_win32_error_not_timeout_and_retains_process(self):
        fake = FakeKernel()
        process = self.construct(fake)
        fake.kernel.WaitForSingleObject.side_effect = lambda *args: 0xFFFFFFFF
        with patch.object(owned_process.C, "get_last_error", return_value=6), patch.object(owned_process.C, "WinError", return_value=OSError("mock WAIT_FAILED")):
            with self.assertRaisesRegex(OSError, "WAIT_FAILED"):
                process.stop(timeout=0)
        self.assertIsNotNone(process.process)
        self.assertFalse(process.cleanup_complete)
        fake.kernel.WaitForSingleObject.side_effect = lambda *args: 0
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_later_handle_close_failure_does_not_replace_original_termination_error(self):
        fake = FakeKernel()
        process = self.construct(fake)
        def terminated_but_call_failed(*args):
            fake.alive = False
            return 0
        fake.kernel.TerminateJobObject.side_effect = terminated_but_call_failed
        close = fake.kernel.CloseHandle.side_effect
        fake.kernel.CloseHandle.side_effect = lambda value: 0 if value == 301 else close(value)
        primary = OSError("first termination error")
        with patch.object(owned_process.C, "get_last_error", return_value=5), patch.object(owned_process.C, "WinError", return_value=primary):
            with self.assertRaises(OSError) as caught:
                process.stop()
        self.assertIs(caught.exception, primary)
        self.assertIn("process: CloseHandle returned failure", primary.__notes__[0])
        self.assertEqual(process.process, 301)
        self.assertTrue(process.root_exit_confirmed)
        fake.kernel.CloseHandle.side_effect = close
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_unresolved_root_does_not_prevent_independent_auxiliary_cleanup(self):
        fake, process, error = FreshOwnerRegressionTests().abort_fault("wait-timeout")
        process._auxiliary_handles.append(("independent-test-handle", 555))
        with self.assertRaises(owned_process.subprocess.TimeoutExpired):
            process.stop(timeout=0)
        self.assertIn(555, fake.closed)
        self.assertEqual(process._auxiliary_handles, [])
        self.assertIsNotNone(process.process)
        self.assertFalse(process.cleanup_complete)

    def test_exited_root_does_not_prove_descendant_exit(self):
        fake = FakeKernel()
        process = self.construct(fake)
        with patch.object(process, "active_count", return_value=1):
            with self.assertRaises(owned_process.subprocess.TimeoutExpired):
                process.stop(timeout=0)
        self.assertTrue(process.root_exit_confirmed)
        self.assertFalse(process.tree_exit_confirmed)
        self.assertEqual(process.job, 101)
        self.assertIsNone(process.process)
        self.assertFalse(process.cleanup_complete)
        process.stop()
        self.assertTrue(process.cleanup_complete)

    def test_successful_exit_proof_survives_core_close_failure_and_retries_once(self):
        for name, handle in (("job", 101), ("thread", 302), ("process", 301)):
            with self.subTest(handle=name):
                fake = FakeKernel()
                process = self.construct(fake)
                close = fake.kernel.CloseHandle.side_effect
                failed = False
                def close_once(value):
                    nonlocal failed
                    if value == handle and not failed:
                        failed = True
                        return 0
                    return close(value)
                fake.kernel.CloseHandle.side_effect = close_once
                with self.assertRaisesRegex(RuntimeError, "Owned handle close uncertain"):
                    process.stop()
                self.assertEqual(getattr(process, name), handle)
                self.assertTrue(process.root_exit_confirmed)
                self.assertTrue(process.tree_exit_confirmed)
                self.assertFalse(process.cleanup_complete)
                process.stop()
                self.assertTrue(process.cleanup_complete)
                self.assertEqual(fake.kernel.TerminateJobObject.call_count, 1)

    def test_preexisting_job_with_persistent_close_failure_never_adopts_tree(self):
        fake = FakeKernel()
        fake.kernel.CloseHandle.side_effect = lambda value: 0
        process = OwnedProcess.__new__(OwnedProcess)
        with self.assertRaises(ProcessConstructionError):
            ConstructorHandleTests().construct(fake, process, last_error=183)
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, "Owned handle close uncertain"):
                process.stop()
        fake.kernel.SetInformationJobObject.assert_not_called()
        fake.kernel.QueryInformationJobObject.assert_not_called()
        fake.kernel.TerminateJobObject.assert_not_called()
        fake.kernel.TerminateProcess.assert_not_called()
        self.assertEqual(process.job, 101)

    def test_probe_source_routes_both_tests_through_owner_without_executing_probe(self):
        # Static AST only. Do NOT import or execute any native probe source.
        source = Path(__file__).with_name("probe_owned_process.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        direct = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == "OwnedProcess"]
        self.assertEqual(direct, [], "direct probe constructor bypasses exception-carried ownership")
        tests = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
        self.assertEqual(len(tests), 2)
        for method in tests:
            calls = [node.func.attr for node in ast.walk(method) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                     and node.func.value.id == "owner"]
            self.assertIn("start", calls)
            finalizers = [node.finalbody for node in ast.walk(method) if isinstance(node, ast.Try) and node.finalbody]
            self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                and node.func.attr == "cleanup" for block in finalizers
                                for statement in block for node in ast.walk(statement)))


class BrowserHoldTests(unittest.TestCase):
    def test_browser_modes_fail_before_owner_ports_docker_or_process_creation(self):
        for mode in ("all", "tracer", "resources", "smoke"):
            with self.subTest(mode=mode), patch.object(run.sys, "argv", ["run.py", mode]), patch.object(run, "RunOwner") as owner, patch.object(run, "LocalDocker") as docker, patch.object(run, "ports_unused") as ports, patch.object(run, "require_service_support") as support, patch.object(run, "wait_ready"), patch.object(run, "no_frontend_dotenv"), patch.object(run, "SCRATCH", run.SCRATCH / "never-created-by-held-mode"):
                # If the old code reaches this point the mock owner cannot launch anything.
                with self.assertRaisesRegex(RuntimeError, "browser.*hold|Browser.*hold"):
                    run.main()
                owner.assert_not_called()
                docker.assert_not_called()
                ports.assert_not_called()
                support.assert_not_called()

    def test_existing_api_mode_stays_api_only_with_every_lifecycle_call_mocked(self):
        with tempfile.TemporaryDirectory(dir=run.SCRATCH, prefix="api-mode-mock-") as directory:
            commands = []
            def factory(command, **kwargs):
                commands.append(command)
                kwargs["on_created"]({"pid": 123, "creation_filetime": 456})
                process = MagicMock()
                process.wait.return_value = 0
                return process
            owner = RunOwner(Path(directory), {}, process_factory=factory)
            docker = MagicMock()
            docker.call.return_value.returncode = 0
            docker.call.return_value.stdout = "linux"
            def create(service, *args):
                record = {"name": service, "container_id": "a" * 64}
                owner.containers.append(record)
                return record
            docker.create.side_effect = create
            with patch.object(run, "SCRATCH", Path(directory)), patch.object(run, "RunOwner", return_value=owner), patch.object(run, "LocalDocker", return_value=docker), patch.object(run, "require_service_support"), patch.object(run, "ports_unused"), patch.object(run, "wait_ready"), patch.object(run, "no_frontend_dotenv"), patch.object(run.sys, "argv", ["run.py", "api"]):
                run.main()
            self.assertEqual(len(commands), 3)  # migrate, API process, HTTP pytest command
            self.assertFalse(any("playwright" in str(command) or "next/dist" in str(command) for command in commands))
            self.assertEqual(docker.cleanup.call_count, 2)


if __name__ == "__main__":
    unittest.main()
