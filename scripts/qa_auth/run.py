"""Own disposable services/processes for QA-01; no shared compose or env files.

Usage: <python> scripts/qa_auth/run.py all
Requires lane-local npm ci and Python backend requirements already installed.
"""

import argparse
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid

from lifecycle import LocalDocker, RunOwner, require_service_support

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(__file__).with_name("runtime.py")
SCRATCH = Path("C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01")
IMAGES = {
    "postgres": "postgres:16-alpine@sha256:aa6cb33cf4c19c765cefcf48d96176258800870a9a1e930ad126200f9d825139",
    "redis": "redis:7-alpine@sha256:c5d34a98396a4775e223c74e929162c35c5a2182901ba26b50ade939941ce14b",
}

BROWSER_HOLD = (
    "Browser execution hold: Playwright 1.60 automatic external redirects bypass routing callbacks. "
    "Requires independent containment design and explicit manager permission in a later reviewed change; no bypass switch."
)


def refuse_browser_mode(action):
    if action in ("all", "tracer", "resources", "smoke"):
        raise RuntimeError(BROWSER_HOLD)


def environment(artifacts):
    # Do not inspect/copy ambient provider credentials. Explicit non-secret allowlist.
    env = {key: os.environ[key] for key in (
        "PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
        "USERPROFILE", "LOCALAPPDATA", "APPDATA", "ProgramFiles", "ProgramFiles(x86)",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    ) if key in os.environ}
    env.update({
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://qa01:qa01-synthetic@127.0.0.1:55443/qa01",
        "DATABASE_URL_SYNC": "postgresql://qa01:qa01-synthetic@127.0.0.1:55443/qa01",
        "REDIS_URL": "redis://127.0.0.1:56443/0",
        "JWT_SECRET": "qa01-disposable-only-synthetic-key-not-for-production",
        "NEXTAUTH_SECRET": "qa01-disposable-only-nextauth-synthetic-key",
        "NEXTAUTH_URL": "http://127.0.0.1:3203",
        "NEXT_PUBLIC_BACKEND_URL": "http://127.0.0.1:8203",
        "APP_URL": "http://127.0.0.1:3203",
        "API_URL": "http://127.0.0.1:8203",
        "CORS_ORIGINS": '["http://127.0.0.1:3203"]',
        "ARTIFACT_BACKEND": "local",
        "ARTIFACT_LOCAL_ROOT": str(artifacts / "artifacts"),
        "QA_AUTH_ARTIFACTS": str(artifacts),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
        "NEXT_TELEMETRY_DISABLED": "1",
        "PLAYWRIGHT_BROWSERS_PATH": str(SCRATCH / "browsers"),
    })
    return env


def no_frontend_dotenv():
    # Next loads these automatically. Refuse by metadata only, never open them.
    for filename in (".env", ".env.local", ".env.development", ".env.development.local",
                     ".env.production", ".env.production.local", ".env.test", ".env.test.local"):
        if (ROOT / "frontend" / filename).exists():
            raise RuntimeError("Refusing Next startup/checks with a project dotenv file present")


def ports_unused():
    for port in (3203, 8203, 55443, 56443):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))


class NoReadinessRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        raise urllib.error.URLError("QA-01 readiness redirects are forbidden")


def wait_ready(url, process, seconds=180):
    if url not in ("http://127.0.0.1:8203/api/health", "http://127.0.0.1:3203/login"):
        raise ValueError("Readiness requires an exact owned local endpoint")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoReadinessRedirect())
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"Service exited with {exit_code}: {url}")
        try:
            with opener.open(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Service unavailable after {seconds}s: {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("tracer", "resources", "smoke", "api", "all", "unit", "frontend-checks", "safe-checks", "harness-checks", "harmless-probes"))
    args = parser.parse_args()
    refuse_browser_mode(args.action)  # BEFORE directories, processes, ports or Docker
    artifacts = SCRATCH / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    artifacts.mkdir(parents=True)
    env = environment(artifacts)
    node = shutil.which("node")
    owner = RunOwner(artifacts, env)
    docker = None
    results = owner.results
    print(f"Evidence: {artifacts}", flush=True)

    def stop(process):
        owner.stop(process)

    def run(label, command, cwd=artifacts, timeout=300, required=True):
        print(label, flush=True)
        return owner.command(label, command, cwd=cwd, timeout=timeout, required=required)

    def start(label, command, cwd=artifacts):
        return owner.start(label, command, cwd=cwd)

    try:
        if args.action == "unit":
            run("backend-unit", [sys.executable, str(RUNTIME), "pytest", str(ROOT / "backend/tests"), "-q"], timeout=300)
            return
        if args.action == "harness-checks":
            run("harness-unit", [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(RUNTIME.parent), "-p", "test_*.py", "-v"])
            run("pip-check", [sys.executable, "-m", "pip", "check"])
            return
        if args.action == "harmless-probes":
            run("harmless-job-probes", [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(RUNTIME.parent), "-p", "probe_owned_process.py", "-v"], timeout=45)
            return
        no_frontend_dotenv()
        if args.action in ("frontend-checks", "safe-checks"):
            checks = [
                ("frontend-unit", "vitest/vitest.mjs", ["run"]),
                ("types", "typescript/bin/tsc", ["--noEmit"]),
                ("auth-lint", "eslint/bin/eslint.js", ["e2e-auth", "playwright.auth.config.ts"]),
                ("full-lint", "eslint/bin/eslint.js", ["."]),
                ("smoke-collection", "@playwright/test/cli.js", ["test", "--list"]),
            ]
            if args.action == "frontend-checks":
                checks.append(("build", "next/dist/bin/next", ["build"]))
            else:
                checks.append(("network-policy-mocks", None, ["--test", str(ROOT / "frontend/e2e-auth/network-policy.check.mjs")]))
            for label, tool, options in checks:
                if tool is None:
                    run(label, [node, *options], ROOT / "frontend", timeout=60, required=False)
                    continue
                run(label, [node, str(ROOT / "frontend/node_modules" / tool), *options], ROOT / "frontend", timeout=600, required=False)
            if owner.failed():
                raise RuntimeError("Frontend check failure(s) preserved in checks.json")
            return
        require_service_support()  # fail closed BEFORE any Docker operation
        ports_unused()
        docker = LocalDocker(owner)
        # Endpoint string validation is not engine readiness. Real approval-mode
        # execution must also verify the selected pipe serves a Linux engine.
        info = docker.call(["info", "--format", "{{.OSType}}"], timeout=15)
        if info.returncode or info.stdout.strip() != "linux":
            raise RuntimeError("Fixed local Docker pipe is unavailable or not a Linux engine")
        containers = {}
        for service, port, target, extra in (
            ("postgres", 55443, 5432, ["--tmpfs", "/var/lib/postgresql/data", "-e", "POSTGRES_USER=qa01", "-e", "POSTGRES_PASSWORD=qa01-synthetic", "-e", "POSTGRES_DB=qa01"]),
            ("redis", 56443, 6379, []),
        ):
            containers[service] = docker.create(service, port, target, extra, IMAGES[service])
        for service, command in (("postgres", ["pg_isready", "-U", "qa01", "-d", "qa01"]), ("redis", ["redis-cli", "ping"])):
            identity = containers[service]["container_id"]
            for attempt in range(60):
                ready = docker.call(["exec", identity, *command], timeout=10)
                if ready.returncode == 0:
                    break
                results[-1]["accepted"] = "transient-readiness-probe; final readiness still required"
                time.sleep(0.5)
            else:
                raise RuntimeError(f"{service} unavailable")
        run("migrations", [sys.executable, str(RUNTIME), "migrate"])
        api = start("backend", [sys.executable, str(RUNTIME), "api"])
        wait_ready("http://127.0.0.1:8203/api/health", api)
        if args.action in ("tracer", "resources", "smoke", "all"):
            frontend = start("frontend", [node, str(ROOT / "frontend/node_modules/next/dist/bin/next"),
                "dev", "--hostname", "127.0.0.1", "--port", "3203"], ROOT / "frontend")
            wait_ready("http://127.0.0.1:3203/login", frontend)
            if args.action == "smoke":
                env.update({"PLAYWRIGHT_NO_WEBSERVER": "1", "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:3203",
                            "PLAYWRIGHT_JSON_OUTPUT_FILE": str(artifacts / "smoke.json")})
                run("default-smoke", [node, str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test",
                    "--config=playwright.config.ts", "--workers=1", "--reporter=list,json", "--output", str(artifacts / "smoke")], ROOT / "frontend", timeout=600)
                return
            slices = ["tracer", "journey", "resources"] if args.action == "all" else [args.action]
            for index, spec in enumerate(slices):
                if index:
                    stop(api)
                    api = start(f"backend-{spec}", [sys.executable, str(RUNTIME), "api"])
                    wait_ready("http://127.0.0.1:8203/api/health", api)
                env["QA_AUTH_BROWSER_SLICE"] = spec
                run(f"browser-{spec}", [node, str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test",
                    "--config=playwright.auth.config.ts", f"{spec}.spec.ts"], ROOT / "frontend", timeout=240, required=False)
        if args.action in ("api", "all"):
            if args.action == "all":
                # Fresh limiter buckets for the independent API suite, not
                # production limiter overrides or forged forwarded headers.
                stop(api)
                api = start("backend-api-suite", [sys.executable, str(RUNTIME), "api"])
                wait_ready("http://127.0.0.1:8203/api/health", api)
            run("auth-api", [sys.executable, str(RUNTIME), "pytest", str(ROOT / "backend/tests/test_pilot_auth_journeys.py"), "-m", "integration", "-q"], required=False)
        if owner.failed():
            raise RuntimeError("Acceptance failure(s) preserved in checks.json; not a green end-to-end run")
    except BaseException as error:
        owner.original_error = f"{type(error).__name__}: {error}"
        raise
    finally:
        owner.cleanup(docker)
        if owner.failed() and owner.original_error is None:
            raise RuntimeError("Checks/cleanup uncertain; see checks.json and inventory.json")


if __name__ == "__main__":
    main()
