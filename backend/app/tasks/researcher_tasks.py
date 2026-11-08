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
            from app.services.analysis_runs import execute_resource

            return loop.run_until_complete(execute_resource("researcher", profile_id))
        finally:
            loop.close()


async def _run_pipeline(profile_id: str) -> dict:
    from app.database import async_session

    terminal_status = "failed"
    async with async_session() as db:
        async for event in researcher_events(db, profile_id):
            if event.get("step") == "complete" and event.get("status") == "completed":
                terminal_status = "completed"
    return {"profile_id": profile_id, "status": terminal_status}


async def researcher_events(db, profile_id: str, *, prior_revision=None):
    from sqlalchemy import delete
    from app.models.researcher import ScrapedPublication, CitationEdge, CoAuthorRelation
    from app.services.scrapers.scrape_orchestrator import ScrapeOrchestrator
    from app.services.academic_integrity.orchestrator import (
        AcademicIntegrityOrchestrator,
    )

    analyzer = AcademicIntegrityOrchestrator(db)
    if prior_revision is not None:
        analyzer.restore_previous_revision(prior_revision)
        # Each durable attempt rebuilds collector artifacts. The saved prior
        # revision survives partial collector commits and retry cleanup.
        for model in (ScrapedPublication, CitationEdge, CoAuthorRelation):
            await db.execute(delete(model).where(model.researcher_profile_id == profile_id))
        await db.commit()
    else:
        await analyzer.capture_previous_revision(profile_id)
    scraper = ScrapeOrchestrator(db)
    stage = "data_collection_failed"
    try:
        async for event in scraper.run_scraping(profile_id):
            if event.get("status") == "failed":
                await analyzer.record_failed_attempt(profile_id)
                yield event
                return
            yield {**event, "step": "collection_complete" if event.get("step") == "complete" else event.get("step", "collection"),
                   "status": "done" if event.get("status") == "completed" else event.get("status", "processing"),
                   "progress": event.get("progress", 0) * 0.5}
        stage = "analysis_failed"
        async for event in analyzer.run_pipeline_streaming(profile_id):
            yield {**event, "progress": 0.5 + event.get("progress", 0) * 0.5}
    except Exception as exc:
        from app.services.analysis_runs import StaleExecution

        # Do not turn loss of ownership into a new assessment failure.
        if isinstance(exc, StaleExecution):
            raise
        logger.exception("Researcher pipeline failed at %s", stage)
        await db.rollback()
        await analyzer.record_failed_attempt(profile_id, stage=stage)
        yield {"step": "error", "status": "failed", "detail": "Researcher analysis failed", "progress": 1}
