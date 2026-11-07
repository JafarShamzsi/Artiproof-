"""
Celery tasks for academic integrity analysis pipeline.
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

    @celery_app.task(name="researcher.run_pipeline")
    def run_researcher_pipeline(profile_id: str) -> dict:
        """Run the academic integrity pipeline as a Celery background task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_pipeline(profile_id))
        finally:
            loop.close()

except ImportError:
    celery_app = None
    logger.debug("Celery not available, background tasks disabled")


async def _run_pipeline(profile_id: str) -> dict:
    from app.database import async_session
    from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator

    async with async_session() as db:
        orchestrator = AcademicIntegrityOrchestrator(db)
        async for _ in orchestrator.run_pipeline_streaming(profile_id):
            pass

    return {"profile_id": profile_id, "status": "completed"}
