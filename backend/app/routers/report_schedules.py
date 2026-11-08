"""Recurring report schedules — `/api/me/report-schedules/*`.

A daily Celery beat sweep walks the report_schedules table for active
schedules with `next_run_at <= now()`, generates a report (defaulting to
executive_summary template, all of the user's source checks since the
previous run), and advances next_run_at by frequency. Email delivery is
gated on SMTP infrastructure that's not wired yet — generated reports
just appear in the user's /reports list.
"""

from datetime import datetime, time, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report_schedule import ReportSchedule
from app.models.user import User
from app.schemas.report import (
    ReportScheduleCreate,
    ReportScheduleResponse,
    ReportScheduleUpdate,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/me/report-schedules", tags=["Reports"])


_REPORT_DELIVERY_HOUR_UTC = 9


def _next_run(frequency: str, base: datetime | None = None) -> datetime:
    """Compute next-run timestamp from a base time + frequency.

    Always aligns to 09:00 UTC on the target day so deliveries arrive
    at a predictable time rather than whenever the user happened to
    create the schedule. The earliest valid result is at least
    `frequency`-many days after `base` — if 09:00 on `base + delta`
    is in the past relative to that point, we bump one day.
    """
    base = base or datetime.now(timezone.utc)
    if frequency == "weekly":
        delta = timedelta(days=7)
    elif frequency == "monthly":
        delta = timedelta(days=30)
    else:
        raise ValueError(f"Unknown frequency: {frequency}")

    target_after = base + delta
    candidate = datetime.combine(
        target_after.date(),
        time(hour=_REPORT_DELIVERY_HOUR_UTC),
        tzinfo=timezone.utc,
    )
    # If the 09:00-snap puts us *before* the earliest-allowed instant
    # (e.g. base was 14:00, so target_after is 14:00 a week later, but
    # 09:00 that same day is too early), push to the next morning.
    if candidate < target_after:
        candidate += timedelta(days=1)
    return candidate


def _response(s: ReportSchedule) -> ReportScheduleResponse:
    return ReportScheduleResponse(
        id=s.id,
        user_id=s.user_id,
        frequency=s.frequency,
        template=s.template,
        active=s.active,
        last_run_at=s.last_run_at,
        next_run_at=s.next_run_at,
        created_at=s.created_at,
    )


@router.get("/", response_model=List[ReportScheduleResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReportSchedule)
        .where(ReportSchedule.user_id == current_user.id)
        .order_by(ReportSchedule.created_at.desc())
    )
    return [_response(s) for s in result.scalars().all()]


@router.post("/", response_model=ReportScheduleResponse, status_code=201)
async def create_schedule(
    data: ReportScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new schedule. We cap at 5 active schedules per user to
    keep the daily sweep predictable."""
    # Schedule template can't be a multi-record one — those need explicit
    # ids that don't exist at sweep time.
    if data.template in ("comparison", "institutional_audit"):
        raise HTTPException(
            status_code=400,
            detail="Multi-record templates aren't valid for scheduled reports",
        )
    count_q = await db.execute(
        select(ReportSchedule).where(ReportSchedule.user_id == current_user.id)
    )
    if len(count_q.scalars().all()) >= 5:
        raise HTTPException(status_code=400, detail="Maximum of 5 schedules per user")

    schedule = ReportSchedule(
        user_id=current_user.id,
        frequency=data.frequency,
        template=data.template,
        active=True,
        next_run_at=_next_run(data.frequency),
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return _response(schedule)


@router.patch("/{schedule_id}", response_model=ReportScheduleResponse)
async def update_schedule(
    schedule_id: str,
    data: ReportScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReportSchedule).where(ReportSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if data.active is not None:
        schedule.active = data.active
    if data.template is not None:
        if data.template in ("comparison", "institutional_audit"):
            raise HTTPException(
                status_code=400,
                detail="Multi-record templates aren't valid for scheduled reports",
            )
        schedule.template = data.template
    if data.frequency is not None and data.frequency != schedule.frequency:
        schedule.frequency = data.frequency
        # Re-anchor next_run from now so the change feels responsive.
        schedule.next_run_at = _next_run(data.frequency)

    await db.commit()
    await db.refresh(schedule)
    return _response(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReportSchedule).where(ReportSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.commit()
    return None
