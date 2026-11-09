"""Scheduled reports fail closed until schedules have durable original scope.

No history selection, PDF generation, delivery, or run timestamp advancement
is permitted. Pure summary helpers remain for callers/tests, not execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceCheck, User

logger = logging.getLogger(__name__)


def _next_run_after(frequency: str, base: datetime) -> datetime:
    """Identical semantics to ``app.routers.report_schedules._next_run``
    — both pick the next 09:00 UTC at least one frequency-period after
    ``base``. Kept as a thin re-export so callers don't have to know the
    router module exists."""
    from app.routers.report_schedules import _next_run

    return _next_run(frequency, base)


def _window_start(frequency: str, now: datetime) -> datetime:
    return now - (
        timedelta(days=7) if frequency == "weekly" else timedelta(days=30)
    )


from app.services.report_engine.assets import embed_report_logo


async def _branding_for_user(user: User, db: AsyncSession) -> dict | None:
    if user.tier != "team" or not user.organization_id:
        return None
    from app.models.organization import Organization

    result = await db.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org or not (org.logo_url or org.primary_color):
        return None
    return {
        "name": org.name,
        "logo_url": await embed_report_logo(org.logo_url),
        "primary_color": org.primary_color,
        "tagline": "Research Integrity Platform",
    }


async def _summary_check_data(checks: List[SourceCheck]) -> dict:
    """Aggregate a list of recent source checks into the dict shape the
    executive_summary renderer accepts. We synthesize a summary record
    rather than picking one — the scheduled report represents *activity*
    over the window, not any single source."""
    if not checks:
        return {
            "input_title": "No activity in this window",
            "input_type": "summary",
            "overall_credibility_score": None,
            "ai_content_percentage": None,
            "misinfo_claims_found": None,
            "scored_checks": 0,
            "claims": [],
            "citations": [],
        }
    completed = [c for c in checks if c.status == "completed"]
    scores = [c.overall_credibility_score for c in completed if c.overall_credibility_score is not None]
    ai_scores = [c.ai_content_percentage for c in completed if c.ai_content_percentage is not None]
    misinfo = [c.misinfo_claims_found for c in completed if c.misinfo_claims_found is not None]
    return {
        "input_title": f"{len(completed)} completed source checks (latest 20)",
        "input_type": "summary",
        "overall_credibility_score": round(sum(scores) / len(scores), 1) if scores else None,
        "ai_content_percentage": round(sum(ai_scores) / len(ai_scores), 1) if ai_scores else None,
        "misinfo_claims_found": sum(misinfo) if misinfo else None,
        "scored_checks": len(scores),
        "claims": [],
        "citations": [],
    }


async def run_due_schedules(db: AsyncSession) -> int:
    """Raise explicitly, including for direct/manual callers of the old sweep."""
    from app.routers.report_schedules import SCHEDULING_DISABLED

    raise RuntimeError(SCHEDULING_DISABLED)


# ─── Celery wiring ────────────────────────────────────────────────────────


try:
    from app.tasks import celery_app  # type: ignore

    if celery_app is None:
        raise ImportError("Celery not installed")

    @celery_app.task(name="scheduled_reports.run_due")
    def run_due_scheduled_reports_task() -> dict:
        from app.routers.report_schedules import SCHEDULING_DISABLED

        logger.warning(SCHEDULING_DISABLED)
        return {"status": "disabled", "reason": SCHEDULING_DISABLED, "generated": 0, "sent": 0}
except (ImportError, AttributeError):
    logger.debug("Celery not configured; scheduled report sweep not registered")


def schedule_beat(celery_app) -> None:
    """Remove only this unsafe sweep; leave other beat entries untouched."""
    schedules = dict(celery_app.conf.beat_schedule or {})
    schedules.pop("artiproof-scheduled-reports-daily", None)
    celery_app.conf.beat_schedule = schedules
