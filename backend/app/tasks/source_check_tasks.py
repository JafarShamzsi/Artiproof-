"""Celery task: run the source verification pipeline."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


from app.tasks import celery_app  # noqa: E402  (registered against the shared instance)


if celery_app is not None:

    @celery_app.task(name="source_check.run_pipeline")
    def run_source_check_pipeline(check_id: str) -> dict:
        """Run the source verification pipeline as a Celery background task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_pipeline(check_id))
        finally:
            loop.close()


async def _run_pipeline(check_id: str) -> dict:
    from app.database import async_session
    from app.services.source_verification.orchestrator import (
        SourceVerificationOrchestrator,
    )

    async with async_session() as db:
        orchestrator = SourceVerificationOrchestrator(db)
        await orchestrator.run_pipeline(check_id)

    return {"check_id": check_id, "status": "completed"}
