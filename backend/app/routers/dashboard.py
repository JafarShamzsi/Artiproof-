from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date

from app.database import get_db
from app.models.source_check import SourceCheck
from app.models.researcher import ResearcherProfile
from app.models.user import User
from app.schemas.dashboard import DashboardStats, DashboardOverview, TrendResponse, TrendPoint, RecentActivityItem
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User's overall stats."""
    user_id = current_user.id

    # Total source checks
    sc_count_q = await db.execute(
        select(func.count(SourceCheck.id)).where(SourceCheck.user_id == user_id)
    )
    total_source_checks = sc_count_q.scalar() or 0

    # Average credibility score
    avg_q = await db.execute(
        select(func.avg(SourceCheck.overall_credibility_score)).where(
            SourceCheck.user_id == user_id,
            SourceCheck.overall_credibility_score.isnot(None),
        )
    )
    avg_credibility = avg_q.scalar() or 0.0

    # Total researcher analyses
    ra_count_q = await db.execute(
        select(func.count(ResearcherProfile.id)).where(ResearcherProfile.user_id == user_id)
    )
    total_researcher = ra_count_q.scalar() or 0

    # Recent alerts = source checks with low credibility or researchers with low integrity
    alerts_q = await db.execute(
        select(func.count(SourceCheck.id)).where(
            SourceCheck.user_id == user_id,
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

    # Recent source checks
    sc_q = await db.execute(
        select(SourceCheck)
        .where(SourceCheck.user_id == user_id)
        .order_by(SourceCheck.created_at.desc())
        .limit(5)
    )
    source_checks = sc_q.scalars().all()

    # Recent researcher analyses
    ra_q = await db.execute(
        select(ResearcherProfile)
        .where(ResearcherProfile.user_id == user_id)
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
):
    """Credibility trends over time."""
    user_id = current_user.id

    result = await db.execute(
        select(
            cast(SourceCheck.created_at, Date).label("date"),
            func.avg(SourceCheck.overall_credibility_score).label("avg_score"),
            func.count(SourceCheck.id).label("count"),
        )
        .where(
            SourceCheck.user_id == user_id,
            SourceCheck.overall_credibility_score.isnot(None),
        )
        .group_by(cast(SourceCheck.created_at, Date))
        .order_by(cast(SourceCheck.created_at, Date))
        .limit(30)
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
