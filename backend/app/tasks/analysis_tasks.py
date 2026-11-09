"""Durable analysis delivery and recovery tasks. Run beat alongside workers."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.tasks import celery_app


async def _execute(run_id):
    from app.services.analysis_runs import execute_run

    # Celery sync tasks each own an event loop; pooled asyncpg connections
    # must not cross those loop boundaries.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        return await execute_run(run_id, engine=engine)
    finally:
        await engine.dispose()


async def _dispatch():
    from app.services.analysis_runs import reconcile_and_dispatch

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return await reconcile_and_dispatch(sessions, lambda run_id: celery_app.send_task(
            "analysis.execute_run", args=[run_id], retry=False,
        ))
    finally:
        await engine.dispose()


if celery_app is not None:
    @celery_app.task(name="analysis.execute_run")
    def execute_analysis_run(run_id: str):
        return asyncio.run(_execute(run_id))

    @celery_app.task(name="analysis.reconcile_and_dispatch")
    def dispatch_analysis_runs():
        return asyncio.run(_dispatch())


def schedule_beat(app):
    app.conf.beat_schedule = {
        **(app.conf.beat_schedule or {}),
        "dispatch-durable-analysis-runs": {
            "task": "analysis.reconcile_and_dispatch", "schedule": 10.0,
        },
    }
