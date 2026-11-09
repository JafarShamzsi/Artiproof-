"""Single Celery app re-exported from this package.

Both pipelines (source-check, researcher) and the cleanup beat schedule
register against this one ``celery_app`` so a single worker / beat command
runs the whole stack:

    celery -A app.tasks.celery_app worker --loglevel=info
    celery -A app.tasks.celery_app beat   --loglevel=info

If Celery isn't installed (lightweight test envs), ``celery_app`` is
``None`` and importing the task modules is a no-op.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


try:
    from celery import Celery

    celery_app: "Celery | None" = Celery(
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
        broker_connection_timeout=2,
        task_publish_retry=False,
        broker_transport_options={"socket_connect_timeout": 2, "socket_timeout": 2},
        timezone="UTC",
    )
except ImportError:
    celery_app = None
    logger.debug("Celery not installed; background tasks disabled")


# Importing these modules registers their @celery_app.task decorators.
# Done at the bottom so callers of `from app.tasks import celery_app` get a
# fully-wired instance with all tasks attached.
if celery_app is not None:
    try:
        from app.tasks import source_check_tasks  # noqa: F401
        from app.tasks import researcher_tasks  # noqa: F401
        from app.tasks import cleanup  # noqa: F401
        from app.tasks import scheduled_reports  # noqa: F401
        from app.tasks import analysis_tasks

        cleanup.schedule_beat(celery_app)
        scheduled_reports.schedule_beat(celery_app)
        analysis_tasks.schedule_beat(celery_app)
    except Exception:
        logger.exception("Failed to register Celery tasks / beat schedule")

    # Telemetry + DLQ signal handlers. Best-effort; failure here only
    # disables the run-log/DLQ surface, not the tasks themselves.
    try:
        from app.tasks.observability import register_observability_signals

        register_observability_signals(celery_app)
    except Exception:
        logger.exception("Failed to register Celery observability signals")


__all__ = ["celery_app"]
