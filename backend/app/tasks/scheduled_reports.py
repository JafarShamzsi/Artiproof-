"""Daily sweep that fires due `ReportSchedule` rows.

Approach:

1. Walk active schedules where `next_run_at <= now()`.
2. For each, generate an executive-summary report covering the user's
   most recent source-check activity (within the schedule's window —
   weekly = last 7 days, monthly = last 30).
3. Persist as a normal `Report` row so it shows up in `/reports`.
4. Update `last_run_at` + advance `next_run_at` by frequency.

Email delivery is deferred — SMTP infra isn't wired yet. The user sees
the generated report in their /reports list at the next sign-in, same as
manually-generated ones.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, ReportSchedule, SourceCheck, User
from app.services.report_engine.html_template import (
    render_executive_summary_report,
    render_source_check_report,
)
from app.services.report_engine.pdf_generator import html_to_pdf, save_pdf

logger = logging.getLogger(__name__)


def _next_run_after(frequency: str, base: datetime) -> datetime:
    if frequency == "weekly":
        return base + timedelta(days=7)
    if frequency == "monthly":
        return base + timedelta(days=30)
    raise ValueError(f"Unknown frequency: {frequency}")


def _window_start(frequency: str, now: datetime) -> datetime:
    return now - (
        timedelta(days=7) if frequency == "weekly" else timedelta(days=30)
    )


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
        "logo_url": org.logo_url,
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
            "overall_credibility_score": 0,
            "ai_content_percentage": 0,
            "misinfo_claims_found": 0,
            "claims": [],
            "citations": [],
        }
    avg_score = sum((c.overall_credibility_score or 0) for c in checks) / len(checks)
    total_misinfo = sum((c.misinfo_claims_found or 0) for c in checks)
    avg_ai = sum((c.ai_content_percentage or 0) for c in checks) / len(checks)
    return {
        "input_title": f"{len(checks)} sources analyzed",
        "input_type": "summary",
        "overall_credibility_score": round(avg_score, 1),
        "ai_content_percentage": round(avg_ai, 1),
        "misinfo_claims_found": total_misinfo,
        "claims": [],
        "citations": [],
    }


async def run_due_schedules(db: AsyncSession) -> int:
    """Fire all due schedules. Returns count of reports generated."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ReportSchedule).where(
            ReportSchedule.active.is_(True),
            ReportSchedule.next_run_at <= now,
        )
    )
    schedules = list(result.scalars().all())
    if not schedules:
        return 0

    generated = 0
    for schedule in schedules:
        try:
            window_start = _window_start(schedule.frequency, now)
            checks_q = await db.execute(
                select(SourceCheck)
                .where(
                    SourceCheck.user_id == schedule.user_id,
                    SourceCheck.created_at >= window_start,
                    SourceCheck.deleted_at.is_(None),
                )
                .order_by(SourceCheck.created_at.desc())
                .limit(20)
            )
            checks = list(checks_q.scalars().all())

            user_q = await db.execute(select(User).where(User.id == schedule.user_id))
            user = user_q.scalar_one_or_none()
            if not user or user.deactivated_at is not None or user.deleted_at is not None:
                # Owner gone — keep the schedule row for audit but advance it
                # so we don't keep retrying on the next sweep.
                schedule.last_run_at = now
                schedule.next_run_at = _next_run_after(schedule.frequency, now)
                continue

            branding = await _branding_for_user(user, db)
            check_data = await _summary_check_data(checks)
            window_label = "weekly" if schedule.frequency == "weekly" else "monthly"
            narrative = (
                f"Activity summary for the past {window_label} window. "
                f"{len(checks)} source check"
                f"{'s' if len(checks) != 1 else ''} ran. "
                f"Average credibility score: {check_data['overall_credibility_score']:.0f}. "
                f"Total misinformation claims flagged: {check_data['misinfo_claims_found']}."
            )

            template = schedule.template or "executive_summary"
            # `comparison`/`institutional_audit` are validated out at create
            # time, but defensively fall back if a legacy row slips through.
            if template not in ("full", "executive_summary"):
                template = "executive_summary"
            if template == "full":
                html = render_source_check_report(check_data, narrative, branding=branding)
            else:
                html = render_executive_summary_report(check_data, narrative, branding=branding)
            try:
                pdf_bytes = html_to_pdf(html)
                pdf_path = save_pdf(pdf_bytes)
            except Exception:
                logger.exception("PDF generation failed for schedule %s", schedule.id)
                pdf_path = None

            report = Report(
                user_id=schedule.user_id,
                report_type="scheduled_summary",
                template=template,
                title=f"{window_label.title()} Activity Summary",
                summary=narrative[:2000],
                pdf_path=pdf_path,
            )
            db.add(report)

            schedule.last_run_at = now
            schedule.next_run_at = _next_run_after(schedule.frequency, now)
            generated += 1
        except Exception:
            logger.exception("Failed to fire schedule %s", schedule.id)
            continue

    await db.commit()
    if generated:
        logger.info("Generated %d scheduled report(s)", generated)
    return generated


# ─── Celery wiring ────────────────────────────────────────────────────────


try:
    from app.tasks import celery_app  # type: ignore

    if celery_app is None:
        raise ImportError("Celery not installed")

    @celery_app.task(name="scheduled_reports.run_due")
    def run_due_scheduled_reports_task() -> dict[str, int]:
        import asyncio

        async def _run() -> int:
            from app.database import async_session

            async with async_session() as session:
                return await run_due_schedules(session)

        try:
            count = asyncio.run(_run())
        except RuntimeError:
            logger.warning("Skipping scheduled-reports sweep — event loop already running")
            count = 0
        return {"generated": count}
except (ImportError, AttributeError):
    logger.debug("Celery not configured; scheduled report sweep not registered")


def schedule_beat(celery_app) -> None:
    """Register the daily scheduled-reports sweep on Celery beat.

    Runs at 09:00 UTC by default — slightly later than the cleanup task so
    the two don't compete for DB connections."""
    import os

    from celery.schedules import crontab

    sweep_hour = int(os.getenv("REPORT_SWEEP_HOUR_UTC", "9"))
    celery_app.conf.beat_schedule = {
        **(celery_app.conf.beat_schedule or {}),
        "artiproof-scheduled-reports-daily": {
            "task": "scheduled_reports.run_due",
            "schedule": crontab(hour=sweep_hour, minute=0),
        },
    }
    celery_app.conf.timezone = "UTC"
