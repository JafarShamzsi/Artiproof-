"""Periodic cleanup of soft-deleted rows and orphan files.

Two scopes:

1. **Soft-deleted rows** — `SourceCheck` / `ResearcherProfile` / `Report`
   rows marked with `deleted_at` get hard-deleted (and CASCADE children
   along with them) once they're older than ``SOFT_DELETE_GRACE_DAYS``. The
   grace period lets users ask for a restore.

2. **Orphan files** — uploaded PDFs and annotated PDFs whose mtime is older
   than ``ORPHAN_FILE_GRACE_HOURS`` AND whose path is NOT referenced by any
   live row in `SourceCheck.original_pdf_path` /
   `SourceCheck.annotated_pdf_path` / `Report.pdf_path`. The DB-membership
   check is mandatory — pure age-based deletion would silently delete
   live users' uploads after the grace window.

Wired into Celery beat by the consolidated celery_app in `app/tasks/__init__.py`.
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


async def _collect_referenced_paths(db) -> set[str]:
    """All file paths still referenced by a row (live OR soft-deleted within grace).

    Soft-deleted rows count as "still referenced" until ``hard_delete_expired_soft_deletes``
    actually removes them — otherwise we'd delete the file before the row can be restored.
    """
    referenced: set[str] = set()

    sc_q = await db.execute(
        select(SourceCheck.original_pdf_path, SourceCheck.annotated_pdf_path)
    )
    for orig, annotated in sc_q.all():
        if orig:
            referenced.add(_normalize_path(orig))
        if annotated:
            referenced.add(_normalize_path(annotated))

    rp_q = await db.execute(select(Report.pdf_path))
    for (pdf_path,) in rp_q.all():
        if pdf_path:
            referenced.add(_normalize_path(pdf_path))

    return referenced


def _normalize_path(p: str) -> str:
    """Resolve to an absolute string so we can do set-membership against rglob output."""
    if p.startswith("artifact://"):
        return p
    try:
        return str(Path(p).resolve())
    except OSError:
        return p


async def remove_orphan_files(db) -> int:
    """Unlink files in upload dirs that are old AND not referenced by any DB row.

    Pure age-based deletion would nuke live uploads after the grace window, so we
    intersect against the set of paths currently stored in `SourceCheck` /
    `Report`. Files referenced by *soft-deleted* rows are also retained — the
    file is removed only after `hard_delete_expired_soft_deletes` removes the row.
    """
    from app.config import settings

    hold = settings.ARTIFACT_CLEANUP_HOLD_UNTIL
    if hold is not None:
        if hold.tzinfo is None:
            hold = hold.replace(tzinfo=timezone.utc)
        if hold > datetime.now(timezone.utc):
            logger.info("Artifact orphan cleanup held until %s", hold.isoformat())
            return 0
    referenced = await _collect_referenced_paths(db)

    from app.services.artifact_storage import old_artifacts, delete_pdf
    import asyncio

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_FILE_GRACE_HOURS)
    artifact_removed = 0
    for reference in await asyncio.to_thread(old_artifacts, cutoff, referenced=referenced):
        if reference not in referenced:
            await asyncio.to_thread(delete_pdf, reference)
            artifact_removed += 1

    now = time.time()
    cutoff_seconds = ORPHAN_FILE_GRACE_HOURS * 3600
    removed = artifact_removed

    for base in UPLOAD_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            try:
                if not path.is_file():
                    continue
                if (now - path.stat().st_mtime) <= cutoff_seconds:
                    continue
                if _normalize_path(str(path)) in referenced:
                    continue
                path.unlink()
                removed += 1
            except OSError as e:
                logger.warning("Failed to remove %s: %s", path, e)

    if removed:
        logger.info("Removed %d orphan upload files", removed)
    return removed


# ─── Celery wiring ─────────────────────────────────────────────────────────
# Lazy import so the helpers above remain testable without Celery installed.
# We pull from the shared app.tasks package — every pipeline registers
# against the same celery_app there.

try:
    from app.tasks import celery_app  # type: ignore

    if celery_app is None:
        raise ImportError("Celery not installed")

    @celery_app.task(name="cleanup.run_periodic")
    def run_periodic_cleanup() -> dict[str, object]:
        """Sync entrypoint Celery can schedule.

        Wraps the async helpers because Celery tasks don't accept coroutines.
        Hard-delete must run before the orphan-file sweep so that files
        referenced only by just-deleted rows can be removed in this same pass.
        """
        import asyncio

        async def _run_all() -> tuple[dict[str, int], int]:
            from app.database import async_session

            async with async_session() as session:
                soft = await hard_delete_expired_soft_deletes(session)
                files = await remove_orphan_files(session)
                return soft, files

        try:
            soft, files = asyncio.run(_run_all())
        except RuntimeError:
            # Already inside an event loop (e.g. pytest-asyncio). Skip both
            # async DB steps gracefully so the worker doesn't crash.
            logger.warning("Skipping cleanup — event loop already running")
            soft, files = {}, 0

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
