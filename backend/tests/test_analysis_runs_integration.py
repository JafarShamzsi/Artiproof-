"""Real PostgreSQL ownership, transactional intent and recovery checks.

Use an explicitly designated, migrated integration database. Fixtures only
remove rows owned by their own UUID user, never truncate shared tables.
"""

import asyncio
import json
import os
import uuid
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.analysis_run import AnalysisRun, AnalysisRunEvent
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.services.analysis_runs import (
    ExecutionSession, StaleExecution, claim_run, execute_run, observe_run,
    queue_run, reconcile_and_dispatch,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["source_check", "researcher"])
async def test_http_stream_auth_wire_format_and_cursor_replay(database, monkeypatch, kind):
    from fastapi import FastAPI
    import httpx
    from app.config import settings
    from app.database import get_db
    from app.routers import source_check, researcher
    from app.utils.auth import get_current_user
    from app.services.analysis_runs import append_event
    from sse_starlette.sse import AppStatus

    _, sessions, user_id = database
    monkeypatch.setattr("app.database.async_session", sessions)
    monkeypatch.setattr(AppStatus, "should_exit_event", None)
    if kind == "source_check":
        resource_id, run_id = await submission(sessions, user_id)
        module, prefix, model = source_check, "/api/source-check", SourceCheck
    else:
        async with sessions() as db:
            profile = ResearcherProfile(id=str(uuid.uuid4()), user_id=user_id, researcher_name="Stream fixture")
            db.add(profile)
            run = await queue_run(db, kind, profile)
            await db.commit()
            resource_id, run_id = profile.id, run.id
        module, prefix, model = researcher, "/api/researcher", ResearcherProfile
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        run.status = "completed"
        resource = await db.get(model, resource_id)
        setattr(resource, "status" if kind == "source_check" else "analysis_status", "completed")
        append_event(db, run_id, {"step": "complete", "status": "completed", "progress": 1})
        await db.commit()
    monkeypatch.setattr(settings, "JWT_SECRET", "isolated-stream-integration-key")
    app = FastAPI()
    app.include_router(module.router)
    async def dependency():
        async with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, organization_id=None, role="researcher", tier="free")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://integration") as client:
        ticket_response = await client.post(f"{prefix}/{resource_id}/stream-ticket")
        assert ticket_response.status_code == 200
        endpoint = f"{prefix}/{resource_id}/stream"
        params = {"ticket": ticket_response.json()["ticket"]}
        response = await client.get(endpoint, params=params)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.text.splitlines()
        assert [line for line in lines if line.startswith("event:")] == ["event: message", "event: message"]
        payloads = [json.loads(line[6:]) for line in lines if line.startswith("data:")]
        assert [payload["step"] for payload in payloads] == ["queued", "complete"]
        cursor = next(line[4:] for line in lines if line.startswith("id:"))
        resumed = await client.get(endpoint, params=params, headers={"Last-Event-ID": cursor})
        assert resumed.status_code == 200
        resumed_payloads = [json.loads(line[6:]) for line in resumed.text.splitlines() if line.startswith("data:")]
        assert [payload["step"] for payload in resumed_payloads] == ["complete"]
        invalid = await client.get(endpoint, params=params, headers={"Last-Event-ID": "not-an-event-id"})
        assert invalid.status_code == 400
    async with sessions() as db:
        assert (await db.get(AnalysisRun, run_id)).attempts == 0  # HTTP never executed the run.


@pytest.mark.parametrize("checkpoint", ["during_collection", "after_failure_commit"])
async def test_killed_researcher_preserves_original_revision_once(database, monkeypatch, checkpoint):
    engine, sessions, user_id = database
    async with sessions() as db:
        profile = ResearcherProfile(id=str(uuid.uuid4()), user_id=user_id, researcher_name="Recovery fixture",
            official_h_index=20, integrity_score=80, integrity_breakdown={"formula_version": "1.1"}, analysis_status="pending")
        db.add(profile)
        run = await queue_run(db, "researcher", profile)
        await db.commit()
        profile_id, run_id = profile.id, run.id
    code = """
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings
from app.models.researcher import ResearcherProfile
from app.services.analysis_runs import execute_run
from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator
from app.tasks import researcher_tasks
async def interrupted_collection(db, profile_id, *, prior_revision=None):
    profile = await db.get(ResearcherProfile, profile_id)
    profile.analysis_status = "processing"
    profile.official_h_index = 99
    await db.commit()
    if sys.argv[2] == "after_failure_commit":
        analyzer = AcademicIntegrityOrchestrator(db)
        analyzer.restore_previous_revision(prior_revision)
        await analyzer.record_failed_attempt(profile_id)
    yield {"step": "researcher_kill_checkpoint", "status": "processing", "progress": 0.5}
    await asyncio.Event().wait()
researcher_tasks.researcher_events = interrupted_collection
async def main():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        await execute_run(sys.argv[1], engine=engine)
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    environment = {**os.environ, "DATABASE_URL": os.environ["ARTIPROOF_INTEGRATION_DATABASE_URL"]}
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", code, run_id, checkpoint,
        cwd=str(Path(__file__).resolve().parents[1]), env=environment,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(200):
            async with sessions() as db:
                ready = await db.scalar(sa.select(AnalysisRunEvent.id).where(
                    AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.event_type == "researcher_kill_checkpoint"))
            if ready:
                break
            if child.returncode is not None:
                _, stderr = await child.communicate()
                pytest.fail("Researcher child exited before checkpoint: " + stderr.decode(errors="replace"))
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Researcher worker did not persist its checkpoint")
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
    finally:
        if child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.communicate(), timeout=10)
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        assert run.status == "running"
        assert run.prior_revision["values"]["official_h_index"] == 20
        run.lease_expires_at = sa.func.now() - sa.text("INTERVAL '1 second'")
        await db.commit()
    published = []
    await reconcile_and_dispatch(sessions, published.append)

    from app.tasks import researcher_tasks
    from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator
    async def replacement(db, profile_id, *, prior_revision=None):
        analyzer = AcademicIntegrityOrchestrator(db)
        analyzer.restore_previous_revision(prior_revision)
        await analyzer.record_failed_attempt(profile_id)
        yield {"step": "error", "status": "failed", "progress": 1}
    monkeypatch.setattr(researcher_tasks, "researcher_events", replacement)
    if checkpoint == "during_collection":
        assert run_id in published
        assert (await execute_run(run_id, engine=engine, session_factory=sessions))["status"] == "failed"
    else:
        assert run_id not in published
    assert (await execute_run(run_id, engine=engine, session_factory=sessions))["status"] == "ignored"
    from app.models.researcher_snapshot import ResearcherSnapshot
    async with sessions() as db:
        profile = await db.get(ResearcherProfile, profile_id)
        assert profile.analysis_status == "failed"
        assert profile.integrity_score is None
        snapshots = (await db.execute(sa.select(ResearcherSnapshot).where(
            ResearcherSnapshot.researcher_profile_id == profile_id))).scalars().all()
        assert len(snapshots) == 1
        assert snapshots[0].official_h_index == 20
        assert snapshots[0].integrity_score == 80
        assert await db.scalar(sa.select(sa.func.count()).select_from(AnalysisRunEvent).where(
            AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.event_type == "error")) == 1


@pytest.mark.parametrize("checkpoint", ["before_result", "after_result"])
async def test_killed_worker_recovers_one_committed_result(database, monkeypatch, checkpoint):
    """Kill an actual child process after a DB checkpoint; no provider calls."""
    engine, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    code = """
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings
from app.models.source_check import SourceCheck, ClaimAnalysis
from app.services.analysis_runs import execute_run
from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
async def checkpoint_pipeline(self, source_id):
    source = await self.db.get(SourceCheck, source_id)
    source.status = "processing"
    await self.db.commit()
    if sys.argv[2] == "after_result":
        self.db.add(ClaimAnalysis(source_check_id=source_id, claim_text="Controlled recovery finding",
            verdict="true", confidence=0.8, explanation="Integration fixture"))
        source.overall_credibility_score = 80
        source.status = "completed"
        await self.db.commit()
    yield {"step": "kill_checkpoint", "status": "processing", "progress": 0.8}
    await asyncio.Event().wait()
SourceVerificationOrchestrator.run_pipeline_streaming = checkpoint_pipeline
async def main():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        await execute_run(sys.argv[1], engine=engine)
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    environment = {**os.environ, "DATABASE_URL": os.environ["ARTIPROOF_INTEGRATION_DATABASE_URL"]}
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", code, run_id, checkpoint,
        cwd=str(Path(__file__).resolve().parents[1]), env=environment,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(200):
            async with sessions() as db:
                ready = await db.scalar(sa.select(AnalysisRunEvent.id).where(
                    AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.event_type == "kill_checkpoint"))
            if ready:
                break
            if child.returncode is not None:
                _, stderr = await child.communicate()
                pytest.fail("Child worker exited before checkpoint: " + stderr.decode(errors="replace"))
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Worker did not persist its kill checkpoint")
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
        assert child.returncode != 0
    finally:
        if child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.communicate(), timeout=10)

    # Expedite the real 360-second lease clock. All claim/recovery/commit logic
    # still executes against PostgreSQL and the killed owner's persisted state.
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        assert run.status == "running"
        assert run.attempts == 1
        run.lease_expires_at = sa.func.now() - sa.text("INTERVAL '1 second'")
        await db.commit()
    published = []
    await reconcile_and_dispatch(sessions, published.append)

    from app.models.source_check import ClaimAnalysis
    from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
    async def replacement_pipeline(self, source_id):
        source = await self.db.get(SourceCheck, source_id)
        self.db.add(ClaimAnalysis(source_check_id=source_id, claim_text="Controlled recovery finding",
            verdict="true", confidence=0.8, explanation="Integration fixture"))
        source.overall_credibility_score, source.status = 80, "completed"
        await self.db.commit()
        yield {"step": "complete", "status": "completed", "progress": 1}
    monkeypatch.setattr(SourceVerificationOrchestrator, "run_pipeline_streaming", replacement_pipeline)
    if checkpoint == "before_result":
        assert run_id in published
        assert (await execute_run(run_id, engine=engine, session_factory=sessions))["status"] == "completed"
    else:
        assert run_id not in published
    assert (await execute_run(run_id, engine=engine, session_factory=sessions))["status"] == "ignored"
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.attempts == (2 if checkpoint == "before_result" else 1)
        assert await db.scalar(sa.select(sa.func.count()).select_from(ClaimAnalysis).where(ClaimAnalysis.source_check_id == source_id)) == 1
        assert await db.scalar(sa.select(sa.func.count()).select_from(AnalysisRunEvent).where(
            AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.event_type == "complete")) == 1


@pytest.fixture
async def database():
    url = os.getenv("ARTIPROOF_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Set ARTIPROOF_INTEGRATION_DATABASE_URL to a migrated test database")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = str(uuid.uuid4())
    async with sessions() as db:
        db.add(User(id=user_id, email=f"run-{user_id}@integration.invalid", full_name="Run integration"))
        await db.commit()
    try:
        yield engine, sessions, user_id
    finally:
        async with sessions() as db:
            await db.execute(sa.delete(SourceCheck).where(SourceCheck.user_id == user_id))
            await db.execute(sa.delete(ResearcherProfile).where(ResearcherProfile.user_id == user_id))
            await db.execute(sa.delete(AnalysisRun).where(AnalysisRun.user_id == user_id))
            await db.execute(sa.delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()


async def submission(sessions, user_id):
    async with sessions() as db:
        source = SourceCheck(id=str(uuid.uuid4()), user_id=user_id, input_type="text", input_content="Integration sample", status="pending")
        db.add(source)
        run = await queue_run(db, "source_check", source)
        await db.commit()
        return source.id, run.id


async def test_intent_and_initial_event_rollback_with_resource(database):
    _, sessions, user_id = database
    async with sessions() as db:
        source = SourceCheck(id=str(uuid.uuid4()), user_id=user_id, input_type="text", input_content="Rollback", status="pending")
        db.add(source)
        run = await queue_run(db, "source_check", source)
        source_id, run_id = source.id, run.id
        await db.rollback()
    async with sessions() as db:
        assert await db.get(SourceCheck, source_id) is None
        assert await db.get(AnalysisRun, run_id) is None
        assert (await db.scalar(sa.select(sa.func.count()).select_from(AnalysisRunEvent).where(AnalysisRunEvent.run_id == run_id))) == 0


async def test_duplicate_claim_has_one_owner_and_active_submission_conflicts(database):
    _, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    async def claim(token):
        async with sessions() as db:
            return await claim_run(db, run_id, token)
    claims = await asyncio.gather(claim("one"), claim("two"))
    assert sum(row is not None for row in claims) == 1
    async with sessions() as db:
        source = await db.get(SourceCheck, source_id)
        with pytest.raises(HTTPException) as error:
            await queue_run(db, "source_check", source)
        assert error.value.status_code == 409
        run = await db.get(AnalysisRun, run_id)
        assert run.attempts == 1


async def test_expired_worker_cannot_commit_after_replacement(database):
    engine, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    async with sessions() as db:
        await claim_run(db, run_id, "old")
    worker_sessions = async_sessionmaker(engine, class_=ExecutionSession, expire_on_commit=False,
        info={"analysis_execution": {"kind": "source_check", "resource_id": source_id, "run_id": run_id, "owner_token": "old"}})
    async with worker_sessions() as old:
        source = await old.get(SourceCheck, source_id)
        source.overall_credibility_score = 99
        async with sessions() as db:
            await db.execute(sa.update(AnalysisRun).where(AnalysisRun.id == run_id).values(lease_expires_at=sa.func.now() - sa.text("INTERVAL '1 second'")))
            await db.commit()
        await reconcile_and_dispatch(sessions, lambda _: None)
        async with sessions() as db:
            replacement = await claim_run(db, run_id, "new")
            assert replacement.attempts == 2
        with pytest.raises(StaleExecution):
            await old.commit()
        await old.rollback()
    async with sessions() as db:
        assert (await db.get(SourceCheck, source_id)).overall_credibility_score is None
        assert (await db.get(AnalysisRun, run_id)).owner_token == "new"


async def test_broker_failure_leaves_intent_retryable(database):
    _, sessions, user_id = database
    _, run_id = await submission(sessions, user_id)
    def unavailable(_):
        raise ConnectionError("Broker offline")
    result = await reconcile_and_dispatch(sessions, unavailable)
    assert result["deferred"] >= 1
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        assert run.status == "queued"
        assert run.dispatch_count == 1
        run.next_dispatch_at = sa.func.now()
        await db.commit()
    published = []
    await reconcile_and_dispatch(sessions, published.append)
    assert run_id in published


async def test_committed_results_recovered_without_running_again_and_replayed(database):
    _, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    async with sessions() as db:
        await claim_run(db, run_id, "crashed")
        source = await db.get(SourceCheck, source_id)
        source.status, source.overall_credibility_score = "completed", 75
        await db.execute(sa.update(AnalysisRun).where(AnalysisRun.id == run_id).values(lease_expires_at=sa.func.now() - sa.text("INTERVAL '1 second'")))
        await db.commit()
    published = []
    await reconcile_and_dispatch(sessions, published.append)
    assert run_id not in published
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    first = [event async for event in observe_run(run_id, request, session_factory=sessions)]
    second = [event async for event in observe_run(run_id, request, session_factory=sessions)]
    assert first == second
    assert json.loads(first[-1]["data"])["status"] == "completed"
    assert [event["event"] for event in first] == ["message", "message"]
    assert [json.loads(event["data"])["step"] for event in first] == ["queued", "complete"]
    resumed = [event async for event in observe_run(run_id, request, after=int(first[0]["id"]), session_factory=sessions)]
    assert resumed == first[1:]


async def test_researcher_prior_revision_is_durable_before_collection(database):
    _, sessions, user_id = database
    async with sessions() as db:
        profile = ResearcherProfile(id=str(uuid.uuid4()), user_id=user_id, researcher_name="Revision", integrity_score=80, official_h_index=20, integrity_breakdown={"formula_version": "1.1"})
        db.add(profile)
        run = await queue_run(db, "researcher", profile)
        await db.commit()
        profile.official_h_index = 99
        await db.commit()
        run_id = run.id
    async with sessions() as db:
        run = await db.get(AnalysisRun, run_id)
        assert run.prior_revision["values"]["official_h_index"] == 20


async def test_execute_run_duplicate_delivery_writes_one_result(database, monkeypatch):
    engine, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
    calls = []
    async def pipeline(self, resource_id):
        calls.append(resource_id)
        source = await self.db.get(SourceCheck, resource_id)
        source.status, source.overall_credibility_score = "completed", 80
        await self.db.commit()
        yield {"step": "complete", "status": "completed", "progress": 1}
    monkeypatch.setattr(SourceVerificationOrchestrator, "run_pipeline_streaming", pipeline)
    results = await asyncio.gather(*[execute_run(run_id, engine=engine, session_factory=sessions) for _ in range(2)])
    assert sorted(row["status"] for row in results) == ["completed", "ignored"]
    assert calls == [source_id]
    async with sessions() as db:
        terminal = (await db.execute(sa.select(AnalysisRunEvent).where(AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.event_type == "complete"))).scalars().all()
        assert len(terminal) == 1


async def test_pipeline_without_terminal_event_cannot_leave_resource_processing(database, monkeypatch):
    engine, sessions, user_id = database
    source_id, run_id = await submission(sessions, user_id)
    from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
    async def incomplete(self, resource_id):
        source = await self.db.get(SourceCheck, resource_id)
        source.status = "processing"
        await self.db.commit()
        yield {"step": "started", "status": "processing", "progress": 0.1}
    monkeypatch.setattr(SourceVerificationOrchestrator, "run_pipeline_streaming", incomplete)
    assert (await execute_run(run_id, engine=engine, session_factory=sessions))["status"] == "failed"
    async with sessions() as db:
        source = await db.get(SourceCheck, source_id)
        assert source.status == "failed"
        assert source.overall_credibility_score is None
        assert source.model_metadata["processing_warnings"] == [{"type": "analysis_failed"}]


async def test_real_redis_delivery_runs_without_a_stream(database, monkeypatch):
    """CI supplies Redis; local PostgreSQL-only verification skips this test."""
    redis_url = os.getenv("ARTIPROOF_INTEGRATION_REDIS_URL")
    if not redis_url:
        pytest.skip("Set ARTIPROOF_INTEGRATION_REDIS_URL for real broker delivery")
    from celery import Celery
    from celery.contrib.testing.worker import start_worker
    from app.config import settings
    from app.tasks.analysis_tasks import execute_analysis_run

    _, sessions, user_id = database
    monkeypatch.setattr(settings, "DATABASE_URL", os.environ["ARTIPROOF_INTEGRATION_DATABASE_URL"])
    source_id, run_id = await submission(sessions, user_id)
    # The short fixture intentionally fails extraction before any provider call.
    app = Celery("durable-integration", broker=redis_url)
    queue = "durable-" + uuid.uuid4().hex
    app.conf.update(task_default_queue=queue, task_serializer="json", accept_content=["json"], task_publish_retry=False)
    app.task(name="analysis.execute_run")(execute_analysis_run.run)
    try:
        with start_worker(app, pool="solo", perform_ping_check=False, shutdown_timeout=10):
            published = await reconcile_and_dispatch(sessions, lambda rid: app.send_task("analysis.execute_run", args=[rid], retry=False))
            assert published["dispatched"] >= 1
            for _ in range(100):
                async with sessions() as db:
                    run = await db.get(AnalysisRun, run_id)
                    if run.status in {"completed", "failed"}:
                        assert run.status == "failed"
                        assert run.attempts == 1
                        assert (await db.get(SourceCheck, source_id)).status == "failed"
                        break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("Real Redis worker did not finish the committed run")
    finally:
        app.close()


async def test_exhausted_researcher_attempt_clears_stale_results(database):
    _, sessions, user_id = database
    async with sessions() as db:
        profile = ResearcherProfile(id=str(uuid.uuid4()), user_id=user_id, researcher_name="Expired", integrity_score=80, official_h_index=20, integrity_breakdown={"formula_version": "1.1"}, analysis_status="pending")
        db.add(profile)
        run = await queue_run(db, "researcher", profile)
        await db.commit()
        await claim_run(db, run.id, "expired")
        run.attempts = run.max_attempts
        run.lease_expires_at = sa.func.now() - sa.text("INTERVAL '1 second'")
        profile.official_h_index = 99
        await db.commit()
        run_id, profile_id = run.id, profile.id
    await reconcile_and_dispatch(sessions, lambda _: None)
    async with sessions() as db:
        profile = await db.get(ResearcherProfile, profile_id)
        run = await db.get(AnalysisRun, run_id)
        assert run.status == "failed"
        assert run.error_code == "attempts_exhausted"
        assert profile.analysis_status == "failed"
        assert profile.integrity_score is None
        from app.models.researcher_snapshot import ResearcherSnapshot
        snapshot = (await db.execute(sa.select(ResearcherSnapshot).where(ResearcherSnapshot.researcher_profile_id == profile_id))).scalar_one()
        assert snapshot.official_h_index == 20
