"""Bounded, evidence-first ownership. Docker calls require an explicit local pipe.

Inventory is diagnostic, NOT authorization to kill recovered PIDs/resources.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from owned_process import OwnedProcess, require_supported_platform

LOCAL_DOCKER = "npipe:////./pipe/docker_engine"
INSPECT_METADATA = '{"id":{{json .Id}},"name":{{json .Name}},"labels":{{json .Config.Labels}},"running":{{json .State.Running}}}'


def validate_endpoint(endpoint, platform=None):
    if (platform or os.name) != "nt" or endpoint != LOCAL_DOCKER:
        raise ValueError("Only the fixed Windows local Docker named pipe is supported; no context/TCP/SSH/Unix fallback")
    return endpoint


class RunOwner:
    def __init__(self, artifacts, env, *, process_factory=None):
        self.artifacts, self.env = Path(artifacts), env
        self.run_id = str(uuid.uuid4())
        self.factory = process_factory or OwnedProcess
        self.processes, self.containers, self.results, self.cleanup_errors = [], [], [], []
        self.original_error = None
        self._finalizing = False
        self.inventory = {"run_id": self.run_id, "processes": [], "containers": self.containers,
                          "recovery": "diagnostic-only; no PID replay; inspect exact owned metadata manually"}
        self.save_inventory()

    def write(self, name, value):
        target = self.artifacts / name
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(value, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(target)

    def save_inventory(self):
        self.write("inventory.json", self.inventory)

    def start(self, label, command, cwd=None):
        if self._finalizing:
            raise RuntimeError("Cannot spawn during the final cleanup sweep")
        record = {"label": label, "job_name": f"qa01-{self.run_id}-{uuid.uuid4()}", "state": "intent"}
        self.inventory["processes"].append(record)
        self.save_inventory()
        log = (self.artifacts / f"{label}.log").open("wb")
        entry = {"record": record, "process": None, "log": log}
        self.processes.append(entry)

        def created(identity):
            record.update(identity, state="owned-suspended")
            self.save_inventory()  # Failure aborts before the child can resume.

        try:
            entry["process"] = self.factory(command, cwd=cwd or self.artifacts, env=self.env,
                                            log=log, job_name=record["job_name"], on_created=created)
            record["state"] = "running"
            self.save_inventory()
            return entry["process"]
        except BaseException as original:
            # Constructor failures can retain Win32 handles. A returned process
            # can also already be resumed when the following inventory save fails.
            if entry["process"] is None:
                entry["process"] = getattr(original, "owned_process", None)
            record["state"] = "start-failed-owned-object-tracked" if entry["process"] is not None else "spawn-failed-no-object-returned"
            if entry["process"] is not None:
                try:
                    self.stop(entry["process"])
                except BaseException as error:
                    self.cleanup_errors.append({"resource": label, "phase": "start-failure", "error": str(error)})
            raise

    def stop(self, process):
        # Live object/handles only. The inventory's PID is never a termination input.
        entry = next(item for item in self.processes if item["process"] is process)
        if entry.get("cleanup_complete"):
            return
        if entry.get("stop_attempts", 0) >= 2:
            raise RuntimeError("Owned process cleanup budget exhausted (two attempts)")
        entry["stop_attempts"] = entry.get("stop_attempts", 0) + 1
        entry["record"]["stop_attempts"] = entry["stop_attempts"]
        try:
            process.stop(timeout=10)
            if isinstance(process, OwnedProcess) and not process.cleanup_complete:
                raise RuntimeError("Owned process exit/handle cleanup is not confirmed")
        except BaseException as error:
            entry["cleanup_complete"] = False
            entry["record"]["state"] = "cleanup-unresolved"
            entry["record"].setdefault("cleanup_failures", []).append({
                "attempt": entry["stop_attempts"], "error": str(error),
                "diagnostics": list(getattr(error, "__notes__", []))})
            entry["record"]["cleanup_disposition"] = (
                "unresolved-budget-exhausted" if entry["stop_attempts"] >= 2 else "unresolved-retry-pending")
            raise
        finally:
            if isinstance(process, OwnedProcess):
                entry["record"]["exit_confirmation"] = {
                    "root": process.root_exit_confirmed, "tree": process.tree_exit_confirmed,
                    "handles_closed": process.closed}
        entry["cleanup_complete"] = True
        entry["record"]["state"] = "exit-confirmed-handles-closed"
        entry["record"]["cleanup_disposition"] = "complete"
        self.save_inventory()

    def command(self, label, command, cwd=None, timeout=30, required=True):
        process = None
        cleanup_failure = None
        try:
            process = self.start(label, command, cwd)
            code = process.wait(timeout=timeout)
            self.results.append({"check": label, "exit_code": code})
        except BaseException as error:
            self.results.append({"check": label, "exit_code": None, "error": str(error)})
            raise
        finally:
            # A successful launcher is not proof that all its descendants exited.
            # Stop errors are deferred to final cleanup, never replace original errors.
            if process is not None:
                try:
                    self.stop(process)
                except BaseException as error:
                    self.cleanup_errors.append({"resource": label, "error": str(error)})
                    cleanup_failure = error
        if cleanup_failure is not None:
            raise RuntimeError(f"{label} process cleanup uncertain: {cleanup_failure}") from cleanup_failure
        if required and code:
            raise RuntimeError(f"{label} failed ({code}); see its log")
        result = subprocess.CompletedProcess(command, code, (self.artifacts / f"{label}.log").read_text(encoding="utf-8", errors="replace"), "")
        result.check_record = self.results[-1]
        return result

    def cleanup(self, docker=None):
        # No single failure can abort remaining resource attempts or evidence output.
        for entry in reversed(list(self.processes)):
            try:
                if entry["process"] is not None:
                    self.stop(entry["process"])
            except BaseException as error:
                self.cleanup_errors.append({"resource": entry["record"]["label"], "error": str(error)})
            finally:
                try:
                    entry["log"].close()
                except BaseException as error:
                    self.cleanup_errors.append({"resource": "log", "error": str(error)})
        if docker is not None:
            for container in reversed(self.containers):
                try:
                    docker.cleanup(container)
                except BaseException as error:
                    container["cleanup"] = "uncertain-or-refused"
                    self.cleanup_errors.append({"resource": container["name"], "error": str(error)})
        # Docker cleanup can add processes even when start()/command() raises.
        # Seal spawning, then make one finite final pass over ALL live objects.
        # stop() caps each object's total attempts at two across every phase.
        self._finalizing = True
        for entry in tuple(self.processes):
            if entry["process"] is not None and not entry.get("cleanup_complete") and entry.get("stop_attempts", 0) < 2:
                try:
                    self.stop(entry["process"])
                except BaseException as error:
                    self.cleanup_errors.append({"resource": entry["record"]["label"], "phase": "final-process-sweep", "error": str(error)})
            try:
                entry["log"].close()
            except BaseException as error:
                self.cleanup_errors.append({"resource": "log", "error": str(error)})
        try:
            self.save_inventory()
        except BaseException as error:
            self.cleanup_errors.append({"resource": "inventory.json", "error": str(error)})
        # Attempt separately even if inventory persistence failed.
        evidence = {"run_id": self.run_id, "original_error": self.original_error,
                    "checks": self.results, "cleanup_errors": self.cleanup_errors,
                    "unresolved_processes": [entry["record"] for entry in self.processes
                                            if entry["process"] is not None and not entry.get("cleanup_complete")],
                    "status": "failed" if self.failed() else "passed"}
        self.write("checks.json", evidence)

    def failed(self):
        return bool(self.original_error or self.cleanup_errors
                    or (self._finalizing and any(entry["process"] is not None and not entry.get("cleanup_complete")
                                                for entry in self.processes))
                    or any(item["exit_code"] != 0 and not item.get("accepted") for item in self.results))


class LocalDocker:
    def __init__(self, owner, endpoint=LOCAL_DOCKER, *, platform=None):
        self.endpoint = validate_endpoint(endpoint, platform)
        self.owner = owner
        self.config = owner.artifacts / "docker-empty-config"
        self.config.mkdir(exist_ok=True)  # empty owned directory; no credential/config reads
        owner.inventory["docker_endpoint"] = self.endpoint
        owner.save_inventory()
        self.serial = 0

    def call(self, args, *, timeout=15):
        validate_endpoint(self.endpoint)
        if not 0 < timeout <= 60:
            raise ValueError("Docker command timeout must be bounded to 1..60 seconds")
        self.serial += 1
        return self.owner.command(f"docker-{self.serial}",
                                  ["docker", "--config", str(self.config), "--host", self.endpoint, *args],
                                  timeout=timeout, required=False)

    def inspect(self, identity):
        result = self.call(["inspect", "--type", "container", "--format", INSPECT_METADATA, identity])
        if result.returncode:
            if re.search(r"No such (?:object|container):\s*" + re.escape(identity) + r"\s*$", result.stdout, re.MULTILINE):
                result.check_record["accepted"] = "exact-resource absence observed"
                return None
            raise RuntimeError(f"Exact-resource inspection failed ({result.returncode})")
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or not all(key in value for key in ("id", "name", "labels", "running")):
            raise RuntimeError("Malformed exact-resource ownership metadata")
        return value

    def create(self, service, port, target, extra, image):
        token = str(uuid.uuid4())
        record = {"name": f"qa01-auth-{service}-{token}", "labels": {
            "artiproof.lane": "qa-01", "artiproof.qa.run": self.owner.run_id,
            "artiproof.qa.resource": token}, "state": "intent", "attempted": False,
            "endpoint": self.endpoint}
        self.owner.containers.append(record)
        self.owner.save_inventory()  # BEFORE inspect/create, including timeouts
        if self.inspect(record["name"]) is not None:
            record["state"] = "preexisting-collision-refused"
            self.owner.save_inventory()
            raise RuntimeError("Exact name already exists; never adopt or clean up preexisting resources")
        record.update(state="create-attempt-ambiguous", attempted=True)
        self.owner.save_inventory()
        labels = [part for key, value in record["labels"].items() for part in ("--label", f"{key}={value}")]
        result = self.call(["run", "--detach", "--rm", "--name", record["name"], *labels,
                            "--publish", f"127.0.0.1:{port}:{target}", *extra, image], timeout=60)
        if result.returncode:
            # A name race after preflight is NOT evidence that we created the
            # existing object, even if its metadata happens to match our labels.
            if "Conflict." in result.stdout and record["name"] in result.stdout and "already in use" in result.stdout:
                record["state"] = "create-conflict-refused"
                self.owner.save_inventory()
            raise RuntimeError(f"Container create failed ({result.returncode}); ownership remains ambiguous")
        value = self.inspect(record["name"])
        self.require_owned(record, value)
        record.update(state="owned", container_id=value["id"])
        self.owner.save_inventory()
        return record

    def require_owned(self, record, value):
        if (value is None or value["name"] != "/" + record["name"]
                or any((value.get("labels") or {}).get(key) != expected for key, expected in record["labels"].items())
                or (record.get("container_id") and value["id"] != record["container_id"])):
            raise RuntimeError("Ownership mismatch; no stop authorized")
        identity = value["id"]
        if len(identity) != 64 or any(char not in "0123456789abcdef" for char in identity):
            raise RuntimeError("Invalid immutable container identity; no stop authorized")

    def cleanup(self, record):
        if record["state"] == "create-conflict-refused":
            record["cleanup"] = "name-collision-no-stop"
            return
        if not record["attempted"]:
            record["cleanup"] = "not-created-by-run-no-stop"
            return
        value = self.inspect(record["name"])
        if value is None:
            if record["state"] == "create-attempt-ambiguous":
                raise RuntimeError("Create outcome ambiguous, no owned resource observed yet; manual exact-identity reinspection required")
            record["cleanup"] = "confirmed-absent"
            return
        self.require_owned(record, value)
        # Stop the verified immutable ID, never a mutable name/global label/pattern.
        result = self.call(["stop", "--time", "5", value["id"]], timeout=15)
        if result.returncode:
            raise RuntimeError(f"Owned container stop failed ({result.returncode})")
        if self.inspect(value["id"]) is not None:
            raise RuntimeError("Owned container still exists after stop; cleanup uncertain")
        record["cleanup"] = "confirmed-absent-after-stop"


def require_service_support():
    require_supported_platform()
    validate_endpoint(LOCAL_DOCKER)
