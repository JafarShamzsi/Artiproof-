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
            from app.services.analysis_runs import execute_resource

            return loop.run_until_complete(execute_resource("source_check", check_id))
        finally:
            loop.close()


async def _run_pipeline(check_id: str) -> dict:
    from app.services.analysis_runs import execute_resource

    return await execute_resource("source_check", check_id)
