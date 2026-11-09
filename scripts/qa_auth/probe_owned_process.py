"""Opt-in harmless Windows Job probes. NO servers, network or Docker.

Run separately: python -B -m unittest discover -s scripts/qa_auth -p probe_owned_process.py -v
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from lifecycle import RunOwner
from owned_process import ProcessConstructionError
import run


class OwnedHarmlessProcessProbe(unittest.TestCase):
    def test_exited_parent_descendants_reaped_without_touching_other_job(self):
        directory = Path(tempfile.mkdtemp(dir=run.SCRATCH, prefix="harmless-job-probe-"))
        print(f"Harmless probe evidence retained: {directory}", flush=True)
        owner = RunOwner(directory, run.environment(directory))
        try:
            parent = owner.start("parent-exits", [sys.executable, "-B", "-c",
                "import subprocess,sys; subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(60)']); print('owned child spawned',flush=True)"])
            unrelated = owner.start("other-owned-job", [sys.executable, "-B", "-c", "import time; time.sleep(60)"])
            self.assertEqual(parent.wait(timeout=10), 0)
            self.assertGreater(parent.active_count(), 0)
            owner.stop(parent)
            self.assertTrue(parent.closed)
            self.assertIsNone(unrelated.poll(), "stopping one Job must not stop another owned Job")
            ledger = json.loads((directory / "inventory.json").read_text())
            for record in ledger["processes"]:
                self.assertGreater(record["creation_filetime"], 0)
                self.assertEqual(record["ownership"], "live-kernel-job-and-process-handles")
        finally:
            owner.cleanup()
        self.assertFalse(owner.failed(), (directory / "checks.json").read_text())

    def test_persistence_failure_prevents_child_instruction_execution(self):
        directory = Path(tempfile.mkdtemp(dir=run.SCRATCH, prefix="harmless-suspended-probe-"))
        print(f"Harmless probe evidence retained: {directory}", flush=True)
        marker = directory / "must-not-be-written.txt"
        # All constructors go through RunOwner, including exception-carried
        # ownership and its finite retries. Never discard a failed native object.
        owner = RunOwner(directory, run.environment(directory))
        save = owner.save_inventory
        def reject_owned_identity():
            if any(record["state"] == "owned-suspended" for record in owner.inventory["processes"]):
                raise OSError("synthetic inventory persistence failure")
            save()
        owner.save_inventory = reject_owned_identity
        try:
            with self.assertRaisesRegex((OSError, ProcessConstructionError), "synthetic inventory"):
                owner.start("persistence-failed", [sys.executable, "-B", "-c",
                    f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"])
        finally:
            owner.save_inventory = save
            owner.cleanup()
        self.assertTrue(all(entry.get("cleanup_complete") for entry in owner.processes
                            if entry["process"] is not None), "unresolved ownership; inspect retained evidence")
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
