"""Dashboard analytics — score distribution, top issues, team activity.

These endpoints compute aggregates on-the-fly. None of them write state.
For users with a lot of data we may want to cache or denormalize later;
counts are fast on the indexed user_id columns today.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    AI_CONTENT_FLAG_THRESHOLD,
    SCORE_HIGH_MIN,
    SCORE_MEDIUM_MIN,
    TEAM_ACTIVITY_LOOKBACK_DAYS,
    TEAM_ACTIVITY_MAX_ITEMS,
)
from app.database import get_db
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import CitationCheck, SourceCheck
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ─── Score distribution ──────────────────────────────────────────────────


@router.get("/score-distribution")
async def get_score_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bucket the user's source-check credibility scores into High/Medium/Low.

    Buckets follow the convention used everywhere else in the app
    (lib/colors.ts, scoreColor()): >=70 high, >=40 medium, <40 low.
    Unscored / failed checks are excluded — they have no signal.
    """
    user_id = current_user.id
    score_col = SourceCheck.overall_credibility_score

    bucket = case(
        (score_col >= SCORE_HIGH_MIN, "high"),
        (score_col >= SCORE_MEDIUM_MIN, "medium"),
        else_="low",
    ).label("bucket")

    result = await db.execute(
        select(bucket, func.count(SourceCheck.id))
        .where(
            SourceCheck.user_id == user_id,
            SourceCheck.deleted_at.is_(None),
            score_col.isnot(None),
        )
        .group_by(bucket)
    )
    counts = {"high": 0, "medium": 0, "low": 0}
    for b, count in result.all():
        counts[b] = count
    counts["total"] = counts["high"] + counts["medium"] + counts["low"]
    return counts


# ─── Top flagged issues ──────────────────────────────────────────────────


@router.get("/top-issues")
async def get_top_issues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cross-cutting summary of flagged findings across the user's data.

    Shape:
      {
        "ai_content_checks": N,        # checks where ai_content_percentage >= threshold
        "low_credibility_checks": N,   # checks scoring < SCORE_MEDIUM_MIN
        "retracted_citations": N,      # CitationCheck rows is_retracted=true
        "broken_citations": N,         # is_accessible=false (live + checked)
        "citation_rings_flagged": N,   # ResearcherProfile rows where citation_ring_flags.rings is non-empty
      }

    All counts scoped to the current user, exclude soft-deleted rows.
    """
    user_id = current_user.id

    # Source-check level aggregates — done in one round trip.
    sc_aggregates = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (SourceCheck.ai_content_percentage >= AI_CONTENT_FLAG_THRESHOLD, 1),
                        else_=0,
                    )
                ),
                0,
            ).label("ai_content_checks"),
            func.coalesce(
                func.sum(
                    case(
                        (SourceCheck.overall_credibility_score < SCORE_MEDIUM_MIN, 1),
                        else_=0,
                    )
                ),
                0,
            ).label("low_credibility_checks"),
        ).where(
            SourceCheck.user_id == user_id,
            SourceCheck.deleted_at.is_(None),
        )
    )
    sc_row = sc_aggregates.one()

    # Citation aggregates — join through SourceCheck for ownership.
    cit_aggregates = await db.execute(
        select(
            func.coalesce(
                func.sum(case((CitationCheck.is_retracted.is_(True), 1), else_=0)),
                0,
            ).label("retracted"),
            func.coalesce(
                func.sum(case((CitationCheck.is_accessible.is_(False), 1), else_=0)),
                0,
            ).label("broken"),
        )
        .select_from(CitationCheck)
        .join(SourceCheck, SourceCheck.id == CitationCheck.source_check_id)
        .where(
            SourceCheck.user_id == user_id,
            SourceCheck.deleted_at.is_(None),
        )
    )
    cit_row = cit_aggregates.one()

    # Citation rings on researcher profiles — JSON shape so we count rows
    # whose `citation_ring_flags.rings` is non-empty by fetching the column
    # and inspecting in Python. Number of profiles per user is small (10s).
    rp_q = await db.execute(
        select(ResearcherProfile.citation_ring_flags).where(
            ResearcherProfile.user_id == user_id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    rings_count = 0
    for (flags,) in rp_q.all():
        if isinstance(flags, dict):
            rings = flags.get("rings") or []
            if rings:
                rings_count += 1

    return {
        "ai_content_checks": int(sc_row.ai_content_checks or 0),
        "low_credibility_checks": int(sc_row.low_credibility_checks or 0),
        "retracted_citations": int(cit_row.retracted or 0),
        "broken_citations": int(cit_row.broken or 0),
        "citation_rings_flagged": rings_count,
    }


# ─── Team activity ───────────────────────────────────────────────────────


@router.get("/team-activity")
async def get_team_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent activity from the user's organization, last 30 days.

    Filters out members who opted out via share_activity_with_team=false.
    Only available to tier='team' users with a non-null organization_id.
    Returns 403 for everyone else so the frontend can hide the panel.
    """
    if current_user.tier != "team":
        raise HTTPException(
            status_code=403, detail="Team activity is a team-tier feature."
        )
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Your account is on the team tier but isn't linked to an "
                "organization yet. Contact support to get set up."
            ),
        )

    # Members of the same org who chose to share. The current user always
    # appears in their own org list — they see their own activity too.
    members_q = await db.execute(
        select(User.id, User.full_name, User.email).where(
            User.organization_id == current_user.organization_id,
            User.deleted_at.is_(None),
            User.share_activity_with_team.is_(True),
        )
    )
    members = {
        uid: {"id": uid, "full_name": full_name, "email": email}
        for uid, full_name, email in members_q.all()
    }
    if not members:
        return {"items": []}

    cutoff = datetime.now(timezone.utc) - timedelta(days=TEAM_ACTIVITY_LOOKBACK_DAYS)
    member_ids = list(members.keys())

    # Three queries (source checks, researcher profiles, reports) merged + sorted.
    sc_q = await db.execute(
        select(
            SourceCheck.id,
            SourceCheck.user_id,
            SourceCheck.input_title,
            SourceCheck.input_type,
            SourceCheck.overall_credibility_score,
            SourceCheck.created_at,
        ).where(
            SourceCheck.user_id.in_(member_ids),
            SourceCheck.deleted_at.is_(None),
            SourceCheck.created_at >= cutoff,
        )
    )
    rp_q = await db.execute(
        select(
            ResearcherProfile.id,
            ResearcherProfile.user_id,
            ResearcherProfile.researcher_name,
            ResearcherProfile.integrity_score,
            ResearcherProfile.created_at,
        ).where(
            ResearcherProfile.user_id.in_(member_ids),
            ResearcherProfile.deleted_at.is_(None),
            ResearcherProfile.created_at >= cutoff,
        )
    )
    rpt_q = await db.execute(
        select(
            Report.id, Report.user_id, Report.title, Report.report_type, Report.created_at
        ).where(
            Report.user_id.in_(member_ids),
            Report.deleted_at.is_(None),
            Report.created_at >= cutoff,
        )
    )

    items: list[dict] = []
    for row in sc_q.all():
        items.append({
            "id": row.id,
            "kind": "source_check",
            "title": row.input_title or f"Source check ({row.input_type})",
            "score": row.overall_credibility_score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "actor": members.get(row.user_id),
        })
    for row in rp_q.all():
        items.append({
            "id": row.id,
            "kind": "researcher",
            "title": f"Researcher: {row.researcher_name}",
            "score": row.integrity_score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "actor": members.get(row.user_id),
        })
    for row in rpt_q.all():
        items.append({
            "id": row.id,
            "kind": "report",
            "title": row.title,
            "score": None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "actor": members.get(row.user_id),
        })

    items.sort(key=lambda i: i["created_at"] or "", reverse=True)
    return {"items": items[:TEAM_ACTIVITY_MAX_ITEMS]}
