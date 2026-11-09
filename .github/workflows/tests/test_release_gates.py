"""CI contract regressions; run with Python 3.12 + PyYAML (no app imports)."""

import pathlib
import shlex
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[3]


def workflow(name):
    # BaseLoader preserves the GitHub Actions `on` key (YAML 1.2 semantics).
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


class ReleaseGates(unittest.TestCase):
    def test_events_permissions_and_isolation(self):
        for name in ("ci.yml", "codeql.yml", "security.yml"):
            with self.subTest(workflow=name):
                data = workflow(name)
                for event in ("pull_request", "push", "workflow_dispatch", "merge_group"):
                    self.assertIn(event, data["on"])
                self.assertNotIn("pull_request_target", data["on"])
                self.assertEqual(data["permissions"], {"contents": "read"})
                group = data["concurrency"]["group"]
                self.assertIn("github.workflow", group)
                self.assertIn("github.event.pull_request.number", group)
                self.assertIn("github.ref", group)
                for job in data["jobs"].values():
                    self.assertEqual(job["runs-on"], "ubuntu-24.04")
                    self.assertLessEqual(int(job["timeout-minutes"]), 30)
                    for step in job["steps"]:
                        self.assertNotIn("continue-on-error", step)
                        if step.get("uses", "").startswith("actions/checkout@"):
                            self.assertEqual(step["with"]["persist-credentials"], "false")

    def test_required_checks_and_real_integration(self):
        jobs = workflow("ci.yml")["jobs"]
        self.assertIn("backend", jobs)
        self.assertIn("frontend", jobs)
        backend = jobs["backend"]
        self.assertIn("postgres", backend["services"])
        self.assertIn("redis", backend["services"])
        self.assertIn("ARTIPROOF_INTEGRATION_REDIS_URL", backend["env"])
        commands = "\n".join(step.get("run", "") for step in backend["steps"])
        for command in ("alembic upgrade head", "pytest", "-m integration", "test_analysis_runs_integration.py", "test_artifact_migration_integration.py", "--junitxml"):
            self.assertIn(command, commands)

    def test_production_frontend_and_failure_artifacts(self):
        jobs = workflow("ci.yml")["jobs"]
        frontend = jobs["frontend"]
        commands = "\n".join(step.get("run", "") for step in frontend["steps"])
        for command in ("npm ci", "tsc --noEmit", "npm run lint", "npm run test:unit", "npm run build -- --webpack", "npm run test:smoke"):
            self.assertIn(command, commands)
        for job in jobs.values():
            self.assertTrue(any(step.get("uses", "").startswith("actions/upload-artifact@") and step.get("if") == "failure()" for step in job["steps"]))
        config = (ROOT / "frontend/playwright.config.ts").read_text()
        self.assertIn('process.env.CI ? "npm run start" : "npm run dev"', config)
        # Playwright clears its outputDir: do not erase unit/audit/build evidence.
        self.assertIn('outputDir: "./test-results/playwright"', config)

    def test_security_suites_are_in_required_real_integration_command(self):
        backend = workflow("ci.yml")["jobs"]["backend"]
        steps = backend["steps"]
        integration = next(step for step in steps if "--junitxml=test-results/integration.xml" in step.get("run", ""))
        self.assertNotIn("if", integration)
        self.assertNotIn("continue-on-error", backend)
        self.assertNotIn("continue-on-error", integration)
        self.assertEqual(integration["working-directory"], "backend")
        command = shlex.split(integration["run"].splitlines()[0])
        self.assertEqual(command, [
            "pytest", "-m", "integration",
            "tests/test_analysis_runs_integration.py",
            "tests/test_artifact_migration_integration.py",
            "tests/test_team_consent_integration.py",
            "tests/test_report_scope_integration.py",
            "--junitxml=test-results/integration.xml",
        ])
        self.assertTrue(backend["env"]["ARTIPROOF_INTEGRATION_DATABASE_URL"].startswith("postgresql+asyncpg://"))
        migration = next(step for step in steps if "alembic upgrade head" in step.get("run", ""))
        self.assertNotIn("if", migration)
        self.assertLess(steps.index(migration), steps.index(integration))

    def test_integration_junit_guard_rejects_empty_or_skipped_reports(self):
        steps = workflow("ci.yml")["jobs"]["backend"]["steps"]
        integration = next(step for step in steps if "--junitxml=test-results/integration.xml" in step.get("run", ""))
        guard = next(shlex.split(line.strip()) for line in integration["run"].splitlines()
                     if line.strip().startswith("python -c "))
        self.assertEqual(guard[:2], ["python", "-c"])
        for report, succeeds in (
            ('<testsuites><testsuite tests="2" skipped="0"/></testsuites>', True),
            ('<testsuites><testsuite tests="0" skipped="0"/></testsuites>', False),
            ('<testsuites/>', False),
            ('<testsuites><testsuite tests="2" skipped="1"/></testsuites>', False),
            ('<testsuites><testsuite tests="1"/><testsuite tests="1" skipped="1"/></testsuites>', False),
            ('invalid XML', False),
        ):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as directory:
                results = pathlib.Path(directory) / "test-results"
                results.mkdir()
                (results / "integration.xml").write_text(report)
                result = subprocess.run([sys.executable, *guard[1:]], cwd=directory, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)

    def test_codeql_is_explicitly_licensed_and_read_only(self):
        jobs = workflow("codeql.yml")["jobs"]
        self.assertIn("CODEQL_LICENSE_CONFIRMED", jobs["analyze"]["if"])
        self.assertIn("availability", jobs)
        analyze = next(step for step in jobs["analyze"]["steps"] if step.get("uses", "").startswith("github/codeql-action/analyze@"))
        self.assertEqual(analyze["with"]["upload"], "false")

    def test_nonlicensed_scanner_rejects_incomplete_reports(self):
        steps = workflow("security.yml")["jobs"]["bandit"]["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)
        self.assertIn("bandit==1.9.4", commands)
        self.assertIn("bandit -r backend/app -lll -iii", commands)
        self.assertIn("assert not r['errors']", commands)
        self.assertIn("No code scanned", commands)


if __name__ == "__main__":
    unittest.main()
