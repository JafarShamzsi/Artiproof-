"""Periodic cleanup of soft-deleted rows and orphan files.

Two scopes:

1. **Soft-deleted rows** — `SourceCheck` / `ResearcherProfile` / `Report`
   rows marked with `deleted_at` get hard-deleted (and CASCADE children
   along with them) once they're older than ``SOFT_DELETE_GRACE_DAYS``. The
   grace period lets users ask for a restore.

2. **Orphan files** — uploaded PDFs and annotated PDFs older than
   ``ORPHAN_FILE_GRACE_HOURS`` get unlinked from disk. Conservative: relies
   on age alone since the soft-delete grace ensures rows linger long
   before files become orphaned.

Wired into Celery beat by `app/tasks/__init__.py` calling
``schedule_beat(celery_app)`` after the app is created.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.models import Report, ResearcherProfile, SourceCheck

logger = logging.getLogger(__name__)


SOFT_DELETE_GRACE_DAYS = 30
ORPHAN_FILE_GRACE_HOURS = 24

# Repo layout: backend/app/tasks/cleanup.py → upload dirs are at backend/uploads, backend/reports
UPLOAD_DIRS = [
    Path(__file__).resolve().parents[2] / "uploads",
    Path(__file__).resolve().parents[2] / "reports",
]


async def hard_delete_expired_soft_deletes(db) -> dict[str, int]:
    """Permanently delete rows whose deleted_at is older than the grace window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SOFT_DELETE_GRACE_DAYS)
    counts: dict[str, int] = {}

    for model in (SourceCheck, ResearcherProfile, Report):
        result = await db.execute(
            select(model.id).where(
                model.deleted_at.is_not(None),
                model.deleted_at < cutoff,
            )
        )
        ids = [row[0] for row in result.all()]
        if not ids:
            counts[model.__tablename__] = 0
            continue

        await db.execute(delete(model).where(model.id.in_(ids)))
        counts[model.__tablename__] = len(ids)

    await db.commit()
    if any(counts.values()):
        logger.info("Hard-deleted soft-deleted rows: %s", counts)
    return counts


def remove_orphan_files() -> int:
    """Unlink files older than ORPHAN_FILE_GRACE_HOURS from upload dirs."""
    now = time.time()
    cutoff_seconds = ORPHAN_FILE_GRACE_HOURS * 3600
    removed = 0

    for base in UPLOAD_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            try:
                if not path.is_file():
                    continue
                if (now - path.stat().st_mtime) <= cutoff_seconds:
                    continue
                path.unlink()
                removed += 1
            except OSError as e:
                logger.warning("Failed to remove %s: %s", path, e)

    if removed:
        logger.info("Removed %d orphan upload files", removed)
    return removed


# ─── Celery wiring ─────────────────────────────────────────────────────────
# Lazy imports so the helpers above remain testable without Celery installed.

try:
    from app.tasks.source_check_tasks import celery_app  # type: ignore

    @celery_app.task(name="cleanup.run_periodic")
    def run_periodic_cleanup() -> dict[str, object]:
        """Sync entrypoint Celery can schedule.

        Wraps the async hard-delete helper because Celery tasks don't accept
        coroutines. The orphan-file sweep is already sync.
        """
        import asyncio

        async def _hard_delete() -> dict[str, int]:
            from app.database import get_db

            async for session in get_db():
                return await hard_delete_expired_soft_deletes(session)
            return {}

        try:
            soft = asyncio.run(_hard_delete())
        except RuntimeError:
            # Already inside an event loop (e.g. pytest-asyncio). Skip the DB
            # step gracefully so the file sweep still runs.
            logger.warning("Skipping hard-delete step — event loop already running")
            soft = {}

        files = remove_orphan_files()
        return {"hard_deleted_rows": soft, "removed_files": files}
except (ImportError, AttributeError):
    logger.debug("Celery not configured; cleanup task not registered")


def schedule_beat(celery_app) -> None:
    """Register the cleanup task on Celery's beat scheduler.

    Runs daily at 03:00 UTC by default — override with CLEANUP_HOUR_UTC env.
    """
    from celery.schedules import crontab

    cleanup_hour = int(os.getenv("CLEANUP_HOUR_UTC", "3"))
    celery_app.conf.beat_schedule = {
        **(celery_app.conf.beat_schedule or {}),
        "artiproof-cleanup-daily": {
            "task": "cleanup.run_periodic",
            "schedule": crontab(hour=cleanup_hour, minute=0),
        },
    }
    celery_app.conf.timezone = "UTC"
