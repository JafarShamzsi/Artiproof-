"""
Celery tasks for source verification pipeline.
"""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from celery import Celery

    celery_app = Celery(
        "artiproof",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_time_limit=300,
        task_soft_time_limit=240,
    )

    @celery_app.task(name="source_check.run_pipeline")
    def run_source_check_pipeline(check_id: str) -> dict:
        """Run the source verification pipeline as a Celery background task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_pipeline(check_id))
        finally:
            loop.close()

    # Register the cleanup task and its daily beat schedule. Done after
    # celery_app exists so the cleanup module can import it; deferred import
    # avoids a circular dependency.
    try:
        from app.tasks.cleanup import schedule_beat  # noqa: WPS433

        schedule_beat(celery_app)
    except Exception:
        logger.exception("Failed to schedule cleanup beat task")

except ImportError:
    celery_app = None
    logger.debug("Celery not available, background tasks disabled")


async def _run_pipeline(check_id: str) -> dict:
    from app.database import async_session
    from app.services.source_verification.orchestrator import SourceVerificationOrchestrator

    async with async_session() as db:
        orchestrator = SourceVerificationOrchestrator(db)
        await orchestrator.run_pipeline(check_id)

    return {"check_id": check_id, "status": "completed"}
