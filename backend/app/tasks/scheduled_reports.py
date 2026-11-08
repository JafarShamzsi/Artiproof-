"""Daily sweep that fires due `ReportSchedule` rows.

Approach:

1. Walk active schedules where `next_run_at <= now()`.
2. For each, generate an executive-summary report covering the user's
   most recent source-check activity (within the schedule's window —
   weekly = last 7 days, monthly = last 30).
3. Persist as a normal `Report` row so it shows up in `/reports`.
4. Email the user with a deep link to the report (when Resend is wired).
5. Update `last_run_at` + advance `next_run_at` by frequency.

When email is unconfigured the report still lands in the user's /reports
list at next sign-in — so a misconfigured prod doesn't silently drop the
generated artifact.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Report, ReportSchedule, SourceCheck, User
from app.services.email import render_scheduled_report_ready, send_email
from app.services.report_engine.html_template import (
    render_executive_summary_report,
    render_source_check_report,
)
from app.services.report_engine.pdf_generator import html_to_pdf, save_pdf

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
        # Per-schedule commit: the previous version committed once at the
        # end of the loop, so a single failing schedule's exception
        # rolled back every successful one before it. Each iteration is
        # now independently durable; on failure we rollback only the
        # in-flight schedule's writes.
        try:
            window_start = _window_start(schedule.frequency, now)
            checks_q = await db.execute(
                select(SourceCheck)
                .where(
                    SourceCheck.user_id == schedule.user_id,
                    SourceCheck.created_at >= window_start,
                    SourceCheck.status == "completed",
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
                await db.commit()
                continue

            branding = await _branding_for_user(user, db)
            check_data = await _summary_check_data(checks)
            score = check_data["overall_credibility_score"]
            score_text = f"{score:.0f}" if score is not None else "unavailable"
            misinfo = check_data["misinfo_claims_found"]
            misinfo_text = str(misinfo) if misinfo is not None else "not assessed"
            window_label = "weekly" if schedule.frequency == "weekly" else "monthly"
            narrative = (
                f"Activity summary for the past {window_label} window. "
                f"This report samples the latest {len(checks)} completed source checks "
                f"(up to 20) in that window. "
                f"Average credibility score: {score_text} "
                f"from {check_data['scored_checks']} scored checks. "
                f"Total misinformation claims flagged in assessed checks: {misinfo_text}."
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
                # html_to_pdf returns (bytes, renderer_label) — for the
                # scheduled-summary path we only need the bytes; the
                # renderer label is meaningful for interactive downloads
                # only (the route adds an X-Report-Renderer header so
                # the UI can toast). Drop the label here.
                pdf_bytes, _renderer = html_to_pdf(html)
                pdf_path = save_pdf(pdf_bytes)
            except Exception:
                logger.exception("PDF generation failed for schedule %s", schedule.id)
                pdf_path = None

            report = Report(
                user_id=schedule.user_id,
                organization_id=getattr(user, "organization_id", None),
                report_type="scheduled_summary",
                template=template,
                title=f"{window_label.title()} Activity Summary",
                summary=narrative[:2000],
                pdf_path=pdf_path,
            )
            db.add(report)

            schedule.last_run_at = now
            schedule.next_run_at = _next_run_after(schedule.frequency, now)
            await db.commit()
            await db.refresh(report)

            # Honor the user's notification preference. Both weekly and
            # monthly schedules share the same toggle for now — the
            # NotificationPreferences shape doesn't split them, and adding
            # a separate key is a UX decision the Settings page hasn't
            # asked for yet.
            #
            # ``getattr`` defaults guard against test stubs that omit
            # these columns; the real User model always populates them.
            prefs = getattr(user, "notification_preferences", None) or {}
            if prefs.get("email_weekly_digest", False):
                try:
                    report_url = f"{settings.APP_URL}/reports/{report.id}"
                    subject, html, text = render_scheduled_report_ready(
                        name=getattr(user, "full_name", "") or "",
                        report_title=report.title,
                        report_url=report_url,
                        window_label=window_label,
                    )
                    await send_email(
                        to=getattr(user, "email", ""),
                        subject=subject,
                        html=html,
                        text=text,
                    )
                except Exception:
                    logger.exception(
                        "Scheduled-report email failed for user %s report %s",
                        user.id, report.id,
                    )
            generated += 1
        except Exception:
            logger.exception("Failed to fire schedule %s", schedule.id)
            try:
                await db.rollback()
            except Exception:
                logger.debug("rollback for failed schedule %s also raised", schedule.id)
            continue

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
