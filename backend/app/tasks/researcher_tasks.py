"""Celery task: run the academic integrity analysis pipeline (with scrape phase)."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


from app.tasks import celery_app  # noqa: E402  (registered against the shared instance)


if celery_app is not None:

    @celery_app.task(name="researcher.run_pipeline")
    def run_researcher_pipeline(profile_id: str) -> dict:
        """Run the scrape + analysis pipeline as a Celery background task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_pipeline(profile_id))
        finally:
            loop.close()


async def _run_pipeline(profile_id: str) -> dict:
    from app.database import async_session
    from app.services.scrapers.scrape_orchestrator import ScrapeOrchestrator
    from app.services.academic_integrity.orchestrator import (
        AcademicIntegrityOrchestrator,
    )

    async with async_session() as db:
        scraper = ScrapeOrchestrator(db)
        async for ev in scraper.run_scraping(profile_id):
            if ev.get("status") == "failed":
                return {"profile_id": profile_id, "status": "failed"}

        analyzer = AcademicIntegrityOrchestrator(db)
        async for _ in analyzer.run_pipeline_streaming(profile_id):
            pass

    return {"profile_id": profile_id, "status": "completed"}
