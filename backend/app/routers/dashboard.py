from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date

from app.constants import TIER_LIMITS
from app.database import get_db
from app.models.report import Report
from app.models.source_check import SourceCheck
from app.models.researcher import ResearcherProfile
from app.models.user import User
from app.schemas.dashboard import (
    DashboardStats,
    DashboardOverview,
    TrendResponse,
    TrendPoint,
    RecentActivityItem,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Maps the frontend date-range selector to a day count. None = "all time".
RANGE_DAYS: dict[str, int | None] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User's overall stats."""
    user_id = current_user.id

    sc_count_q = await db.execute(
        select(func.count(SourceCheck.id)).where(
            SourceCheck.user_id == user_id, SourceCheck.deleted_at.is_(None)
        )
    )
    total_source_checks = sc_count_q.scalar() or 0

    avg_q = await db.execute(
        select(func.avg(SourceCheck.overall_credibility_score)).where(
            SourceCheck.user_id == user_id,
            SourceCheck.deleted_at.is_(None),
            SourceCheck.overall_credibility_score.isnot(None),
        )
    )
    avg_credibility = avg_q.scalar() or 0.0

    ra_count_q = await db.execute(
        select(func.count(ResearcherProfile.id)).where(
            ResearcherProfile.user_id == user_id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    total_researcher = ra_count_q.scalar() or 0

    alerts_q = await db.execute(
        select(func.count(SourceCheck.id)).where(
            SourceCheck.user_id == user_id,
            SourceCheck.deleted_at.is_(None),
            SourceCheck.overall_credibility_score < 40,
        )
    )
    recent_alerts = alerts_q.scalar() or 0

    return DashboardStats(
        total_source_checks=total_source_checks,
        avg_credibility_score=round(float(avg_credibility), 1),
        total_researcher_analyses=total_researcher,
        recent_alerts=recent_alerts,
    )


@router.get("/recent-activity", response_model=list[RecentActivityItem])
async def get_recent_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent source checks and researcher analyses."""
    user_id = current_user.id

    sc_q = await db.execute(
        select(SourceCheck)
        .where(SourceCheck.user_id == user_id, SourceCheck.deleted_at.is_(None))
        .order_by(SourceCheck.created_at.desc())
        .limit(5)
    )
    source_checks = sc_q.scalars().all()

    ra_q = await db.execute(
        select(ResearcherProfile)
        .where(
            ResearcherProfile.user_id == user_id,
            ResearcherProfile.deleted_at.is_(None),
        )
        .order_by(ResearcherProfile.created_at.desc())
        .limit(5)
    )
    researcher_profiles = ra_q.scalars().all()

    items: list[RecentActivityItem] = []

    for sc in source_checks:
        items.append(RecentActivityItem(
            id=sc.id,
            type="source_check",
            title=sc.input_title or f"Source check ({sc.input_type})",
            status=sc.status,
            score=sc.overall_credibility_score,
            created_at=sc.created_at,
        ))

    for rp in researcher_profiles:
        items.append(RecentActivityItem(
            id=rp.id,
            type="researcher_analysis",
            title=f"Researcher: {rp.researcher_name}",
            status=rp.analysis_status,
            score=rp.integrity_score,
            created_at=rp.created_at,
        ))

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:10]


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    range: Literal["7d", "30d", "90d", "all"] = Query("30d"),
):
    """Credibility trends over time, bucketed daily.

    `range`: 7d | 30d | 90d | all. The previous behavior was hardcoded to
    the most recent 30 days; passing 'all' returns every day with at least
    one scored check.
    """
    user_id = current_user.id

    where_clauses = [
        SourceCheck.user_id == user_id,
        SourceCheck.deleted_at.is_(None),
        SourceCheck.overall_credibility_score.isnot(None),
    ]
    days = RANGE_DAYS.get(range, 30)
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        where_clauses.append(SourceCheck.created_at >= cutoff)

    result = await db.execute(
        select(
            cast(SourceCheck.created_at, Date).label("date"),
            func.avg(SourceCheck.overall_credibility_score).label("avg_score"),
            func.count(SourceCheck.id).label("count"),
        )
        .where(*where_clauses)
        .group_by(cast(SourceCheck.created_at, Date))
        .order_by(cast(SourceCheck.created_at, Date))
    )
    rows = result.all()

    return TrendResponse(
        data=[
            TrendPoint(
                date=str(row.date),
                score=round(float(row.avg_score), 1),
                count=row.count,
            )
            for row in rows
        ]
    )


@router.get("/usage")
async def get_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Month-to-date counts vs the user's tier limits.

    Returns:
      {
        "tier": "free" | "pro" | "team",
        "period_start": ISO,
        "period_end": ISO,
        "usage": {
          "source_checks": {"used": N, "limit": M | null, "percent": 0..100 | null},
          "researcher_analyses": {"used": N, "limit": M | null, "percent": ...},
          "reports": {"used": N, "limit": M | null, "percent": ...}
        }
      }

    `limit: null` and `percent: null` mean unlimited (team tier).
    """
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    user_id = current_user.id
    tier = current_user.tier or "free"
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])

    sc_count = (
        await db.execute(
            select(func.count(SourceCheck.id)).where(
                SourceCheck.user_id == user_id,
                SourceCheck.deleted_at.is_(None),
                SourceCheck.created_at >= period_start,
            )
        )
    ).scalar() or 0

    rp_count = (
        await db.execute(
            select(func.count(ResearcherProfile.id)).where(
                ResearcherProfile.user_id == user_id,
                ResearcherProfile.deleted_at.is_(None),
                ResearcherProfile.created_at >= period_start,
            )
        )
    ).scalar() or 0

    rpt_count = (
        await db.execute(
            select(func.count(Report.id)).where(
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
                Report.created_at >= period_start,
            )
        )
    ).scalar() or 0

    def _bucket(used: int, limit: int | None) -> dict:
        if limit is None:
            return {"used": used, "limit": None, "percent": None}
        return {
            "used": used,
            "limit": limit,
            "percent": min(100, round((used / limit) * 100)) if limit > 0 else 0,
        }

    return {
        "tier": tier,
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "usage": {
            "source_checks": _bucket(sc_count, limits["source_checks_per_month"]),
            "researcher_analyses": _bucket(
                rp_count, limits["researcher_analyses_per_month"]
            ),
            "reports": _bucket(rpt_count, limits["reports_per_month"]),
        },
    }
