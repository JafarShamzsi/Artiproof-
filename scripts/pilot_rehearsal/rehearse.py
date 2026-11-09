"""OPS-01 offline preflight and native PostgreSQL synthetic recovery only.

No app imports, dotenv, Docker, arbitrary URLs, existing databases or cleanup.
Outputs are retained in a newly created lane scratch directory, even on failure.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import uuid
from urllib.parse import urlsplit


SCRATCH = Path("C:/Users/Axel/AppData/Local/hermes/cache/scratch/ops-01")
REPO = Path(__file__).resolve().parents[2]
PORTS = (3206, 8206, 55446, 56446)
DATABASES = ("ops01_synthetic_source", "ops01_synthetic_restore", "ops01_synthetic_rollback")
USER = "ops01_synthetic"
PG_TOOLS = ("initdb", "pg_ctl", "psql", "pg_dump", "pg_restore")


class Unsafe(ValueError):
    """Fail closed before contacting a service or mutating an existing resource."""


def validate_target(url: str) -> None:
    """Exact allowlist, not hostname resolution; URL input is never used by CLI."""
    try:
        target = urlsplit(url)
        valid = (
            target.scheme == "postgresql"
            and target.hostname == "127.0.0.1"
            and target.port == 55446
            and target.username == USER
            and target.password is None
            and target.path in {f"/{name}" for name in DATABASES}
            and not target.query
            and not target.fragment
            and url == f"postgresql://{USER}@127.0.0.1:55446{target.path}"
        )
    except ValueError:
        valid = False
    if not valid:
        raise Unsafe("Only exact OPS-01 synthetic loopback targets are allowed")


def assert_ports_free(ports=PORTS) -> None:
    """Bind probes only; no requests to listeners and no process termination."""
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise Unsafe(f"Required port {port} unavailable; do not stop its owner") from exc


def new_run(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent != SCRATCH.resolve() or not resolved.name.startswith("ops01-"):
        raise Unsafe("Run must be a new ops01-* direct child of lane scratch")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        resolved.mkdir()  # Never reuse, overwrite, remove or clean up a prior run.
    except FileExistsError as exc:
        raise Unsafe("Run already exists; preserved unchanged") from exc
    return resolved


def migration_head(directory: Path) -> str:
    """Read revision constants with AST; never execute migrations/settings."""
    revisions = {}
    for file in sorted(directory.glob("*.py")):
        values = {}
        for node in ast.parse(file.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        values[target.id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"revision", "down_revision"}:
                    values[node.target.id] = ast.literal_eval(node.value)
        if "revision" not in values or "down_revision" not in values:
            raise Unsafe(f"Missing revision constants: {file.name}")
        revision, parent = values["revision"], values["down_revision"]
        if not isinstance(revision, str) or revision in revisions:
            raise Unsafe("Invalid/duplicate migration revision")
        if parent is not None and not isinstance(parent, str):
            raise Unsafe("Branched migration parents require owner review")
        revisions[revision] = parent
    parents = {parent for parent in revisions.values() if parent is not None}
    heads = set(revisions) - parents
    if not revisions or not parents.issubset(revisions) or len(heads) != 1:
        raise Unsafe("Expected one migration head with known parents")
    head = next(iter(heads))
    visited = set()
    current = head
    while current is not None:
        if current in visited:
            raise Unsafe("Migration cycle")
        visited.add(current)
        current = revisions[current]
    if visited != set(revisions):
        raise Unsafe("Disconnected migration graph")
    return head


def tool_paths(pg_bin: Path | None) -> dict:
    if pg_bin is None:
        return {}
    suffix = ".exe" if os.name == "nt" else ""
    return {name: str((pg_bin / (name + suffix)).resolve()) for name in PG_TOOLS
            if (pg_bin / (name + suffix)).is_file()}


def preflight(repo: Path, pg_bin: Path | None) -> dict:
    result = {
        "release_status": "BLOCKED",
        "recovery_status": "BLOCKED",
        "scope": "offline repository inspection; no deployment authorization",
        "required_ports": list(PORTS),
        "postgres_tools": sorted(tool_paths(pg_bin)),
        "blockers": ["Manual go/no-go and hosting acceptance not performed"],
    }
    try:
        result["repository_migration_head"] = migration_head(repo / "backend/alembic/versions")
        assert_ports_free()
        result["ports"] = "free at probe time; must recheck immediately before startup"
    except (Unsafe, OSError, SyntaxError, ValueError) as exc:
        result["blockers"].append(str(exc))
    if len(tool_paths(pg_bin)) != len(PG_TOOLS):
        result["blockers"].append("Complete explicitly selected native PostgreSQL bin unavailable")
    result["recovery_note"] = "Not executed; tool presence and free ports are not recovery evidence"
    return result


def child_env(run: Path) -> dict:
    # Allowlist OS runtime variables only. No PG*, app, cloud or provider values.
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "COMSPEC")
           if key in os.environ}
    env.update({"PGCONNECT_TIMEOUT": "3", "PGPASSFILE": str(run / "no-pgpass"),
                "PGSERVICEFILE": str(run / "no-pgservice"), "PGSYSCONFDIR": str(run),
                "TEMP": str(run), "TMP": str(run), "LC_ALL": "C"})
    return env


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hash(path: Path, expected: str) -> None:
    if digest(path) != expected:
        raise Unsafe("Backup/restored artifact hash mismatch")


def rehearse(run: Path, pg_bin: Path, repo: Path) -> dict:
    tools = tool_paths(pg_bin)
    if len(tools) != len(PG_TOOLS):
        raise Unsafe("Native PostgreSQL tools unavailable; recovery BLOCKED")
    head = migration_head(repo / "backend/alembic/versions")
    if not all(ch.isalnum() or ch == "_" for ch in head):
        raise Unsafe("Unexpected revision identifier")
    assert_ports_free()
    data = run / "cluster"
    env = child_env(run)
    commands = []

    def command(tool, *args):
        argv = [tools[tool], *map(str, args)]
        commands.append(argv)
        with (run / "commands.json").open("w", encoding="utf-8") as log:
            json.dump(commands, log, indent=2)
        completed = subprocess.run(argv, env=env, cwd=run, capture_output=True,
                                   text=True, timeout=60, check=False)
        with (run / "tool-output.log").open("a", encoding="utf-8") as log:
            log.write(completed.stdout + completed.stderr)
        if completed.returncode:
            raise Unsafe(f"{tool} failed ({completed.returncode}); inspect retained tool-output.log")
        return completed.stdout.strip()

    def sql(database, statement, bootstrap=False):
        if bootstrap:
            if database != "postgres":
                raise Unsafe("Unknown bootstrap database")
        else:
            validate_target(f"postgresql://{USER}@127.0.0.1:55446/{database}")
        return command("psql", "-X", "-w", "-h", "127.0.0.1", "-p", "55446",
                       "-U", USER, "-d", database, "-v", "ON_ERROR_STOP=1", "-At", "-c", statement)

    started = False
    try:
        command("initdb", "-D", data, "-U", USER, "--auth-local=trust", "--auth-host=trust",
                "--encoding=UTF8", "--no-locale")
        # Restrict even trust authentication to the one explicit IPv4 loopback address.
        (data / "pg_hba.conf").write_text("host all all 127.0.0.1/32 trust\n", encoding="ascii")
        assert_ports_free()
        started = True  # stop our unique cluster even if pg_ctl start times out
        command("pg_ctl", "-D", data, "-l", run / "postgres.log", "-w", "-t", "15",
                "-o", "-h 127.0.0.1 -p 55446", "start")
        for database in DATABASES:
            sql("postgres", f'CREATE DATABASE "{database}";', bootstrap=True)
        artifact = run / "source-artifact.pdf"
        artifact.write_bytes(b"%PDF-1.4\n% OPS-01 synthetic backup fixture only\n%%EOF\n")
        expected = digest(artifact)
        sql(DATABASES[0], "CREATE TABLE alembic_version (version_num varchar(64) PRIMARY KEY);"
            f"INSERT INTO alembic_version VALUES ('{head}');"
            "CREATE TABLE ops01_fixture (id integer PRIMARY KEY, artifact text, sha256 text);"
            f"INSERT INTO ops01_fixture VALUES (1, 'synthetic.pdf', '{expected}');")
        backup = run / "backup"
        backup.mkdir()
        shutil.copyfile(artifact, backup / "synthetic.pdf")
        command("pg_dump", "-w", "-h", "127.0.0.1", "-p", "55446", "-U", USER,
                "-d", DATABASES[0], "-Fc", "-f", backup / "database.dump")
        hashes = {name: digest(backup / name) for name in ("database.dump", "synthetic.pdf")}
        (backup / "manifest.json").write_text(json.dumps({"synthetic": True, "head_marker": head,
            "hashes": hashes}, indent=2), encoding="utf-8")
        # Simulated bad release changes only the newly created source DB/artifact.
        sql(DATABASES[0], "UPDATE ops01_fixture SET sha256 = 'bad-release';")
        artifact.write_bytes(b"synthetic bad release")
        for database in DATABASES[1:]:
            for name, checksum in hashes.items():
                verify_hash(backup / name, checksum)
            command("pg_restore", "-w", "-h", "127.0.0.1", "-p", "55446", "-U", USER,
                    "-d", database, "--exit-on-error", "--no-owner", "--no-privileges",
                    backup / "database.dump")
            restored = run / database
            restored.mkdir()
            shutil.copyfile(backup / "synthetic.pdf", restored / "synthetic.pdf")
            verify_hash(restored / "synthetic.pdf", expected)
            if sql(database, "SELECT version_num FROM alembic_version;") != head:
                raise Unsafe("Restored migration marker mismatch")
            if sql(database, "SELECT id || '|' || artifact || '|' || sha256 FROM ops01_fixture;") != f"1|synthetic.pdf|{expected}":
                raise Unsafe("Restored DB/artifact reference mismatch")
        result = {"release_status": "BLOCKED", "recovery_status": "TESTED_SYNTHETIC_ONLY",
                  "database_and_artifact_restore": "passed", "synthetic_rollback": "passed",
                  "head_marker": head, "application_migrations": "BLOCKED: not applied by this fixture",
                  "exclusions": ["Application schema/data", "Redis/worker", "live object storage",
                                 "host restart", "hosting", "record provenance (DATA01)"],
                  "backup_hashes": hashes}
    finally:
        if started:
            command("pg_ctl", "-D", data, "-w", "-t", "15", "-m", "fast", "stop")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "rehearse"))
    parser.add_argument("--pg-bin", type=Path, help="Explicit reviewed native PostgreSQL bin directory")
    parser.add_argument("--run-name", default=f"ops01-{uuid.uuid4().hex}")
    parser.add_argument("--confirm-synthetic-only", action="store_true")
    args = parser.parse_args()
    run = None
    try:
        if args.mode == "rehearse" and (not args.confirm_synthetic_only or args.pg_bin is None):
            raise Unsafe("Rehearsal requires --pg-bin and --confirm-synthetic-only")
        run = new_run(SCRATCH / args.run_name)
        result = preflight(REPO, args.pg_bin)
        if args.mode == "rehearse":
            result = rehearse(run, args.pg_bin, REPO)
        (run / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"evidence": str(run / "evidence.json"), **result}, indent=2))
        return 0 if result["recovery_status"] == "TESTED_SYNTHETIC_ONLY" else 2
    except (Unsafe, OSError, ValueError, subprocess.SubprocessError) as exc:
        result = {"release_status": "BLOCKED", "recovery_status": "BLOCKED", "error": str(exc)}
        if run is not None:
            (run / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
