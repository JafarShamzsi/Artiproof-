"""Database-backed analysis intent, leases, write fencing and progress replay.

The broker is a delivery mechanism. A committed run remains dispatchable if
publishing fails, and duplicate delivery cannot claim a running/terminal run.
All business commits from a worker validate its current ownership token.
"""

import asyncio
import json
import math
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.analysis_run import AnalysisRun, AnalysisRunEvent
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck

LEASE_SECONDS = 360  # Longer than Celery's 300-second hard task limit.
TERMINAL = {"completed", "failed", "cancelled"}
RESOURCE_MODELS = {"source_check": SourceCheck, "researcher": ResearcherProfile}


class StaleExecution(Exception):
    """Ownership was lost, the resource was deleted, or its run was replaced."""


def _deadline():
    return sa.func.clock_timestamp() + sa.text(f"INTERVAL '{LEASE_SECONDS} seconds'")


def append_event(db, run_id: str, event: dict) -> None:
    progress = event.get("progress", 0)
    progress = float(progress) if isinstance(progress, (int, float)) and math.isfinite(progress) else 0.0
    payload = {
        "step": str(event.get("step", "progress"))[:64],
        "status": str(event.get("status", "processing"))[:32],
        "detail": str(event.get("detail", ""))[:800],
        "progress": max(0.0, min(1.0, progress)), "run_id": run_id,
    }
    db.add(AnalysisRunEvent(run_id=run_id, event_type=payload["step"], payload=payload))


async def queue_run(db: AsyncSession, kind: str, resource) -> AnalysisRun:
    """Caller commits this run, its initial event and the resource together."""
    model = RESOURCE_MODELS[kind]
    await db.flush()
    locked = (await db.execute(sa.select(model).where(model.id == resource.id)
                              .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if locked is None or locked.deleted_at is not None:
        raise HTTPException(404, "Analysis resource not found")
    if locked.current_run_id:
        active = await db.get(AnalysisRun, locked.current_run_id)
        if active is not None and active.status not in TERMINAL:
            raise HTTPException(409, "An analysis is already queued or running")
    prior = None
    if kind == "researcher":
        from app.services.academic_integrity.orchestrator import revision_snapshot

        snapshot = revision_snapshot(locked)
        prior = {"has_revision": snapshot is not None,
                 "values": json.loads(json.dumps(snapshot, default=lambda d: d.isoformat()))}
    run = AnalysisRun(id=str(uuid.uuid4()), kind=kind, resource_id=resource.id,
                      user_id=resource.user_id, status="queued", attempts=0, max_attempts=3,
                      dispatch_count=0, prior_revision=prior)
    db.add(run)
    await db.flush()
    locked.current_run_id = run.id
    append_event(db, run.id, {"step": "queued", "status": "pending", "detail": "Queued for a worker", "progress": 0})
    return run


class ExecutionSession(AsyncSession):
    """Every commit fences business writes against the current run owner.

    Resource and run locks remain held through the commit. A worker resuming
    after lease expiry cannot commit findings after another worker takes over.
    """

    async def commit(self):
        execution = self.info.get("analysis_execution")
        if execution:
            model = RESOURCE_MODELS[execution["kind"]]
            with self.no_autoflush:
                resource = (await self.execute(sa.select(model.id).where(
                    model.id == execution["resource_id"], model.deleted_at.is_(None),
                    model.current_run_id == execution["run_id"],
                ).with_for_update())).scalar_one_or_none()
                if resource is None:
                    raise StaleExecution("Resource deleted or run replaced")
                owned = (await self.execute(sa.update(AnalysisRun).where(
                    AnalysisRun.id == execution["run_id"], AnalysisRun.status == "running",
                    AnalysisRun.owner_token == execution["owner_token"],
                    AnalysisRun.lease_expires_at > sa.func.clock_timestamp(),
                ).values(lease_expires_at=_deadline()).returning(AnalysisRun.id))).scalar_one_or_none()
                if owned is None:
                    raise StaleExecution("Analysis execution lease lost")
        await super().commit()


async def claim_run(db, run_id: str, owner_token: str):
    row = (await db.execute(sa.update(AnalysisRun).where(
        AnalysisRun.id == run_id, AnalysisRun.status == "queued",
        AnalysisRun.attempts < AnalysisRun.max_attempts,
    ).values(status="running", owner_token=owner_token, lease_expires_at=_deadline(),
             started_at=sa.func.now(), attempts=AnalysisRun.attempts + 1)
        .returning(AnalysisRun))).scalar_one_or_none()
    await db.commit()
    return row


async def execute_run(run_id: str, *, engine=None, session_factory=None) -> dict:
    if engine is None:
        from app.database import engine
    if session_factory is None:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
    token = str(uuid.uuid4())
    async with session_factory() as db:
        run = await claim_run(db, run_id, token)
        if run is None:
            return {"run_id": run_id, "status": "ignored"}
        kind, resource_id, prior = run.kind, run.resource_id, run.prior_revision
    execution = {"run_id": run_id, "kind": kind, "resource_id": resource_id, "owner_token": token}
    worker_sessions = async_sessionmaker(engine, class_=ExecutionSession, expire_on_commit=False,
                                        info={"analysis_execution": execution})
    status, error_code = "failed", "pipeline_no_terminal_event"
    try:
        async with worker_sessions() as db:
            if kind == "source_check":
                from app.services.source_verification.orchestrator import SourceVerificationOrchestrator

                events = SourceVerificationOrchestrator(db).run_pipeline_streaming(resource_id)
            else:
                from app.tasks.researcher_tasks import researcher_events

                events = researcher_events(db, resource_id, prior_revision=prior)
            async for event in events:
                if event.get("status") == "failed":
                    status, error_code = "failed", "pipeline_failed"
                elif event.get("step") == "complete" and event.get("status") == "completed":
                    status, error_code = "completed", None
                else:
                    append_event(db, run_id, event)
                    await db.commit()
            if error_code == "pipeline_no_terminal_event":
                raise RuntimeError("Pipeline ended without a terminal result")
    except StaleExecution:
        return {"run_id": run_id, "status": "superseded"}
    except Exception as exc:
        error_code = type(exc).__name__[:80]
        # Persist failure using a fresh fenced session; an aborted transaction
        # must never be reused to "save" the failure that caused its rollback.
        try:
            async with worker_sessions() as db:
                model = RESOURCE_MODELS[kind]
                resource = await db.get(model, resource_id)
                if resource is not None:
                    if kind == "source_check":
                        resource.status = "failed"
                        resource.overall_credibility_score = None
                        resource.ai_content_percentage = None
                        resource.misinfo_claims_found = None
                        resource.score_breakdown = None
                        from app.schemas.breakdown import SOURCE_FORMULA_VERSION

                        resource.model_metadata = {"formula_version": SOURCE_FORMULA_VERSION,
                                                   "processing_warnings": [{"type": "analysis_failed"}]}
                        resource.completed_at = datetime.now(timezone.utc)
                    else:
                        from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator

                        analyzer = AcademicIntegrityOrchestrator(db)
                        analyzer.restore_previous_revision(prior)
                        await analyzer.record_failed_attempt(resource_id, stage="analysis_failed")
                    await db.commit()
        except StaleExecution:
            return {"run_id": run_id, "status": "superseded"}
    async with session_factory() as db:
        finished = (await db.execute(sa.update(AnalysisRun).where(
            AnalysisRun.id == run_id, AnalysisRun.owner_token == token, AnalysisRun.status == "running",
            AnalysisRun.lease_expires_at > sa.func.clock_timestamp(),
        ).values(status=status, error_code=error_code, owner_token=None, lease_expires_at=None,
                 completed_at=sa.func.now()).returning(AnalysisRun.id))).scalar_one_or_none()
        if finished:
            append_event(db, run_id, {"step": "complete" if status == "completed" else "error",
                                     "status": status, "detail": "Analysis complete" if status == "completed" else "Analysis failed; review the result status and coverage", "progress": 1})
        await db.commit()
    return {"run_id": run_id, "status": status if finished else "superseded"}


async def execute_resource(kind: str, resource_id: str) -> dict:
    """Compatibility delivery entry point; all paths use the durable run claim."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as db:
            resource = await db.get(RESOURCE_MODELS[kind], resource_id)
            run_id = resource.current_run_id if resource is not None else None
        return await execute_run(run_id, engine=engine) if run_id else {"status": "ignored", "resource_id": resource_id}
    finally:
        await engine.dispose()


async def reconcile_and_dispatch(session_factory, publish) -> dict:
    """Repair expired attempts and redeliver committed intent.

    Use resource -> run lock order, matching fenced business commits. The
    dispatch lock does not access resources. Publishing can fail or duplicate
    delivery: intent survives, and workers still need an atomic claim.
    """
    repaired = dispatched = deferred = 0
    async with session_factory() as db:
        candidates = (await db.execute(sa.select(AnalysisRun.id, AnalysisRun.kind, AnalysisRun.resource_id).where(
            AnalysisRun.status == "running", AnalysisRun.lease_expires_at <= sa.func.clock_timestamp(),
        ).limit(100))).all()
    for run_id, kind, resource_id in candidates:
        async with session_factory() as db:
            model = RESOURCE_MODELS[kind]
            resource = (await db.execute(sa.select(model).where(model.id == resource_id).with_for_update())).scalar_one_or_none()
            run = (await db.execute(sa.select(AnalysisRun).where(
                AnalysisRun.id == run_id, AnalysisRun.status == "running",
                AnalysisRun.lease_expires_at <= sa.func.clock_timestamp(),
            ).with_for_update())).scalar_one_or_none()
            if run is None:
                continue
            resource_status = getattr(resource, "status" if kind == "source_check" else "analysis_status", None)
            resource_status = getattr(resource_status, "value", resource_status)
            if resource is None or resource.deleted_at is not None or resource.current_run_id != run.id:
                run.status, run.error_code = "cancelled", "resource_unavailable"
            elif resource_status in {"completed", "failed"}:
                # The result committed, but the worker died before its terminal
                # event. Never rerun already committed results in this window.
                run.status = resource_status
                run.error_code = None if resource_status == "completed" else "pipeline_failed"
            elif run.attempts < run.max_attempts:
                run.status, run.error_code = "queued", "lease_expired"
                run.next_dispatch_at = sa.func.now()
            else:
                run.status, run.error_code = "failed", "attempts_exhausted"
                if kind == "source_check":
                    resource.status = "failed"
                    resource.overall_credibility_score = None
                    resource.ai_content_percentage = None
                    resource.misinfo_claims_found = None
                    resource.score_breakdown = None
                    from app.schemas.breakdown import SOURCE_FORMULA_VERSION

                    resource.model_metadata = {"formula_version": SOURCE_FORMULA_VERSION,
                                               "processing_warnings": [{"type": "attempts_exhausted"}]}
                    resource.completed_at = datetime.now(timezone.utc)
                else:
                    from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator

                    analyzer = AcademicIntegrityOrchestrator(db)
                    analyzer.restore_previous_revision(run.prior_revision)
                    # This uses the same transaction and retains the locks.
                    # _save_results commits, so invalidate ownership first.
                    run.owner_token = None
                    run.lease_expires_at = None
                    await analyzer.record_failed_attempt(resource_id, stage="analysis_failed")
            run.owner_token = None
            run.lease_expires_at = None
            terminal = run.status in TERMINAL
            if terminal:
                run.completed_at = sa.func.now()
            append_event(db, run.id, {"step": "complete" if run.status == "completed" else "error" if terminal else "queued",
                                     "status": run.status, "progress": 1 if terminal else 0,
                                     "detail": "Analysis complete" if run.status == "completed" else "Worker attempt expired; retry queued" if not terminal else "Analysis failed or cancelled"})
            await db.commit()
            repaired += 1
    async with session_factory() as db:
        runs = (await db.execute(sa.select(AnalysisRun).where(
            AnalysisRun.status == "queued", AnalysisRun.next_dispatch_at <= sa.func.now(),
        ).order_by(AnalysisRun.created_at).limit(25).with_for_update(skip_locked=True))).scalars().all()
        for run in runs:
            try:
                publish(run.id)
                dispatched += 1
                delay = 30
            except Exception:
                deferred += 1
                delay = 15
            run.dispatch_count += 1
            run.next_dispatch_at = sa.func.now() + sa.text(f"INTERVAL '{delay} seconds'")
            if delay == 15:
                # A broker outage affects the whole batch. Bound connection
                # attempts per tick instead of blocking on every queued row.
                break
        await db.commit()
    return {"repaired": repaired, "dispatched": dispatched, "deferred": deferred}


def stream_cursor(request) -> int:
    value = request.headers.get("last-event-id", "0")
    if not value.isascii() or not value.isdecimal() or len(value) > 18:
        raise HTTPException(400, "Invalid Last-Event-ID")
    return int(value)


async def observe_run(run_id: str, request, *, after: int = 0, session_factory=None):
    """SSE observes committed events only. No broker publish or analysis call."""
    if session_factory is None:
        from app.database import async_session as session_factory
    cursor = max(0, after)
    while not await request.is_disconnected():
        async with session_factory() as db:
            run = await db.get(AnalysisRun, run_id)
            if run is None:
                return
            rows = (await db.execute(sa.select(AnalysisRunEvent).where(
                AnalysisRunEvent.run_id == run_id, AnalysisRunEvent.id > cursor,
            ).order_by(AnalysisRunEvent.id).limit(100))).scalars().all()
            terminal = run.status in TERMINAL
            state = run.status
        for row in rows:
            cursor = row.id
            # Browser EventSource.onmessage handles standard message events.
            # Step names remain in the payload; named SSE events would bypass
            # both submission screens' onmessage callbacks entirely.
            yield {"id": str(row.id), "event": "message", "data": json.dumps(row.payload)}
        if terminal and len(rows) < 100:
            if not rows:
                status = "completed" if state == "completed" else "failed"
                yield {"event": "message", "data": json.dumps(
                    {"step": "complete" if status == "completed" else "error", "status": status,
                     "detail": "Analysis complete" if status == "completed" else "Analysis failed or cancelled", "progress": 1, "run_id": run_id})}
            return
        await asyncio.sleep(1)
