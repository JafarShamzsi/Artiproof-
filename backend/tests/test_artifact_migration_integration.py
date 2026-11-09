import json
import os
import uuid
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.cli import migrate_artifacts as migration
from app.config import settings
from app.models.analysis_run import AnalysisRun
from app.models.report import Report
from app.models.source_check import SourceCheck
from app.models.user import User
from app.services import artifact_storage as storage

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
PDF = b"%PDF-1.7\nMigration test payload\n%%EOF"


@pytest.fixture
async def migration_db(tmp_path):
    url = os.getenv("ARTIPROOF_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Set ARTIPROOF_INTEGRATION_DATABASE_URL to an isolated migrated test DB")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        # Migration scans the whole DB. Never run it against existing artifacts,
        # including another test's data or an incorrectly selected real DB.
        if await migration.inventory(db) or await db.scalar(sa.select(AnalysisRun.id).limit(1)):
            await engine.dispose()
            pytest.skip("Migration acceptance requires a DB with no preexisting artifacts/runs")
    user_id = uuid.uuid4().hex
    async with sessions() as db:
        db.add(User(id=user_id, email=user_id + "@migration.invalid", full_name="Migration test"))
        await db.commit()
    source = settings.model_copy(update={"ARTIFACT_BACKEND": "local", "ARTIFACT_LOCAL_ROOT": str(tmp_path / "source"),
                                         "ARTIFACT_LEGACY_ROOT": str(tmp_path)})
    target = source.model_copy(update={"ARTIFACT_LOCAL_ROOT": str(tmp_path / "target")})
    try:
        yield sessions, user_id, source, target, tmp_path / "manifest.json"
    finally:
        async with sessions() as db:
            await db.execute(sa.delete(Report).where(Report.user_id == user_id))
            await db.execute(sa.delete(SourceCheck).where(SourceCheck.user_id == user_id))
            await db.execute(sa.delete(AnalysisRun).where(AnalysisRun.user_id == user_id))
            await db.execute(sa.delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()


async def records(sessions, user_id, reference):
    ids = [uuid.uuid4().hex for _ in range(3)]
    async with sessions() as db:
        for identity in ids[:2]:
            db.add(SourceCheck(id=identity, user_id=user_id, input_type="document", input_content="sample.pdf", original_pdf_path=reference))
        db.add(Report(id=ids[2], user_id=user_id, report_type="source_verification", title="Migration sample", pdf_path=reference))
        await db.commit()
    return ids


async def test_dry_run_then_verified_apply_and_idempotent_resume(migration_db):
    sessions, user_id, source, target, manifest_path = migration_db
    legacy = manifest_path.parent / "legacy.pdf"
    legacy.write_bytes(PDF)
    await records(sessions, user_id, str(legacy))
    manifest = await migration.plan(sessions, source, target)
    migration.save_manifest(manifest_path, manifest)
    assert len(manifest["groups"]) == 1
    assert len(manifest["groups"][0]["records"]) == 3
    assert not Path(target.ARTIFACT_LOCAL_ROOT).exists()  # Dry run never copies.
    async with sessions() as db:
        assert {row["reference"] for row in await migration.inventory(db)} == {str(legacy)}
    await migration.apply_manifest(sessions, manifest, manifest_path, target)
    migrated = manifest["groups"][0]["target"]
    assert storage.read_pdf(migrated, config=target) == PDF
    assert legacy.read_bytes() == PDF  # Original retained for rollback.
    await migration.apply_manifest(sessions, json.loads(manifest_path.read_text()), manifest_path, target)
    async with sessions() as db:
        assert {row["reference"] for row in await migration.inventory(db)} == {migrated}
    assert len(list(Path(target.ARTIFACT_LOCAL_ROOT).rglob("*.pdf"))) == 1
    assert json.loads(manifest_path.read_text())["complete"] is True


async def test_destination_verified_before_reference_changes(migration_db, monkeypatch):
    sessions, user_id, source, target, manifest_path = migration_db
    original = storage.put_pdf(PDF, "original", config=source)
    await records(sessions, user_id, original)
    manifest = await migration.plan(sessions, source, target)
    real_read = storage.read_pdf
    def corrupted(reference, *, config=None):
        return b"%PDF-corrupted" if config.ARTIFACT_LOCAL_ROOT == target.ARTIFACT_LOCAL_ROOT else real_read(reference, config=config)
    monkeypatch.setattr(storage, "read_pdf", corrupted)
    with pytest.raises(RuntimeError, match="Destination verification failed"):
        await migration.apply_manifest(sessions, manifest, manifest_path, target)
    async with sessions() as db:
        assert {row["reference"] for row in await migration.inventory(db)} == {original}


async def test_changed_source_aborts_without_copying(migration_db):
    sessions, user_id, source, target, manifest_path = migration_db
    legacy = manifest_path.parent / "legacy.pdf"
    legacy.write_bytes(PDF)
    await records(sessions, user_id, str(legacy))
    manifest = await migration.plan(sessions, source, target)
    legacy.write_bytes(PDF + b"changed")
    with pytest.raises(RuntimeError, match="Source content changed"):
        await migration.apply_manifest(sessions, manifest, manifest_path, target)
    assert not Path(target.ARTIFACT_LOCAL_ROOT).exists()


async def test_reference_conflict_rolls_back_whole_alias_group_then_resumes(migration_db):
    sessions, user_id, source, target, manifest_path = migration_db
    original = storage.put_pdf(PDF, "original", config=source)
    ids = await records(sessions, user_id, original)
    manifest = await migration.plan(sessions, source, target)
    async with sessions() as db:
        await db.execute(sa.update(SourceCheck).where(SourceCheck.id == ids[1]).values(original_pdf_path="changed.pdf"))
        await db.commit()
    with pytest.raises(RuntimeError, match="reference changed"):
        await migration.apply_manifest(sessions, manifest, manifest_path, target)
    # Copy is journaled, but neither the other source nor the report may move.
    async with sessions() as db:
        assert (await db.get(SourceCheck, ids[0])).original_pdf_path == original
        assert (await db.get(Report, ids[2])).pdf_path == original
        await db.execute(sa.update(SourceCheck).where(SourceCheck.id == ids[1]).values(original_pdf_path=original))
        await db.commit()
    resumed = json.loads(manifest_path.read_text())
    await migration.apply_manifest(sessions, resumed, manifest_path, target)
    assert len(list(Path(target.ARTIFACT_LOCAL_ROOT).rglob("*.pdf"))) == 1


async def test_active_analysis_prevents_migration_plan(migration_db):
    sessions, user_id, source, target, _ = migration_db
    async with sessions() as db:
        db.add(AnalysisRun(id=uuid.uuid4().hex, kind="source_check", resource_id=uuid.uuid4().hex, user_id=user_id, status="queued"))
        await db.commit()
    with pytest.raises(RuntimeError, match="Drain queued/running"):
        await migration.plan(sessions, source, target)


async def test_second_migrator_is_excluded_before_storage_writes(migration_db):
    sessions, user_id, source, target, manifest_path = migration_db
    original = storage.put_pdf(PDF, "original", config=source)
    await records(sessions, user_id, original)
    manifest = await migration.plan(sessions, source, target)
    async with sessions.kw["bind"].connect() as connection:
        await connection.execute(sa.text("SELECT pg_advisory_lock(834910207)"))
        await connection.commit()
        with pytest.raises(RuntimeError, match="Another artifact migration"):
            await migration.apply_manifest(sessions, manifest, manifest_path, target)
        assert not Path(target.ARTIFACT_LOCAL_ROOT).exists()
        await connection.execute(sa.text("SELECT pg_advisory_unlock(834910207)"))
        await connection.commit()


async def test_process_exit_after_journal_releases_lock_and_resumes(migration_db):
    sessions, user_id, source, target, manifest_path = migration_db
    original = storage.put_pdf(PDF, "original", config=source)
    await records(sessions, user_id, original)
    manifest = await migration.plan(sessions, source, target)
    migration.save_manifest(manifest_path, manifest)
    code = """
import asyncio, os, sys
from types import SimpleNamespace
from app.cli import migrate_artifacts as migration
save = migration.save_manifest
def exit_after_journal(path, manifest):
    save(path, manifest)
    os._exit(71)
migration.save_manifest = exit_after_journal
asyncio.run(migration.main_async(SimpleNamespace(apply=True, maintenance_confirmed=True, manifest=sys.argv[1])))
"""
    environment = {**os.environ, **migration.describe(target),
                   "DATABASE_URL": os.environ["ARTIPROOF_INTEGRATION_DATABASE_URL"]}
    child = await asyncio.to_thread(subprocess.run, [sys.executable, "-c", code, str(manifest_path)],
        cwd=str(storage.BACKEND_ROOT), env=environment, capture_output=True, text=True, timeout=25)
    assert child.returncode == 71, child.stderr
    journal = json.loads(manifest_path.read_text())
    assert journal["groups"][0]["target"]
    async with sessions() as db:
        assert {record["reference"] for record in await migration.inventory(db)} == {original}
    # The crashed process's dedicated advisory lock must be gone. Resume must
    # reuse the copied artifact rather than writing a second one.
    await migration.apply_manifest(sessions, journal, manifest_path, target)
    assert len(list(Path(target.ARTIFACT_LOCAL_ROOT).rglob("*.pdf"))) == 1
