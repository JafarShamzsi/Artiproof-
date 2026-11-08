"""Admin-only operational endpoints.

Surfaces the day-2 work an operator needs without dropping to SQL:

  * GET /api/admin/users — paginated user list with search + tier filter
  * PATCH /api/admin/users/{user_id} — change tier / role / soft-undelete
  * GET /api/admin/pipelines/failed — failed source checks + researcher
    analyses across all users (the 3am queue inspection)
  * GET /api/admin/stats — counts by tier, by status, recent failures

The router is gated by ``require_admin`` — a thin wrapper on
``get_current_user`` that 403s anyone whose ``role != "admin"``. The
existing seed endpoint pattern (env gating) doesn't apply here because
admins are real users with elevated roles; they exist in every env.

All mutations log the actor (admin user id) and the target — basic audit
trail until a dedicated AdminAuditLog table is introduced.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TIER_LIMITS
from app.database import get_db
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ─── Dependency: admin gate ────────────────────────────────────────────────


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """403 anyone whose role isn't admin. Returns the admin user when ok
    so handlers can log who took the action."""
    if (current_user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


# ─── Schemas ───────────────────────────────────────────────────────────────


_TIERS = tuple(TIER_LIMITS.keys())  # ("free", "pro", "team")
TierStr = Literal["free", "pro", "team"]
RoleStr = Literal["researcher", "faculty", "admin"]


class AdminUserRow(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tier: str
    organization_id: Optional[str] = None
    deactivated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    email_verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int


class AdminUserUpdateRequest(BaseModel):
    """Every field optional — PATCH semantics. Each set field is an
    explicit admin action that gets logged."""

    tier: Optional[TierStr] = None
    role: Optional[RoleStr] = None
    organization_id: Optional[str] = Field(
        default=None,
        description="Pass empty string to clear the user's org assignment.",
    )
    restore: Optional[bool] = Field(
        default=None,
        description="If true, clear deleted_at (un-soft-delete).",
    )
    reactivate: Optional[bool] = Field(
        default=None,
        description="If true, clear deactivated_at.",
    )


class FailedPipelineRow(BaseModel):
    kind: str  # "source_check" | "researcher_analysis"
    id: str
    user_id: str
    user_email: Optional[str] = None
    title: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminStatsResponse(BaseModel):
    users_total: int
    users_by_tier: dict[str, int]
    users_by_role: dict[str, int]
    source_checks_last_24h: int
    source_check_failures_last_24h: int
    researcher_analyses_last_24h: int
    researcher_failures_last_24h: int
    reports_last_24h: int


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=200, description="Email/name substring"),
    tier: Optional[TierStr] = Query(None),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Search users for support / billing investigation.

    ``q`` substring-matches email and full_name (ILIKE). Tier filter is
    exact. Deleted users hidden by default — opt in with
    ``include_deleted=true`` for permanent-delete sweeps.
    """
    where = []
    if not include_deleted:
        where.append(User.deleted_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        where.append(
            or_(
                func.lower(User.email).like(like),
                func.lower(User.full_name).like(like),
            )
        )
    if tier:
        where.append(User.tier == tier)

    total_q = await db.execute(
        select(func.count(User.id)).where(and_(*where)) if where else select(func.count(User.id))
    )
    total = int(total_q.scalar() or 0)

    rows_q = await db.execute(
        select(User)
        .where(and_(*where) if where else True)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AdminUserListResponse(
        items=[AdminUserRow.model_validate(u) for u in rows_q.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}", response_model=AdminUserRow)
async def update_user(
    user_id: str,
    data: AdminUserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Mutate a user record. Each set field is logged with the admin id
    so the audit trail is at least grep-able until a dedicated audit
    table lands."""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    actions: list[str] = []

    if data.tier is not None and data.tier != target.tier:
        actions.append(f"tier={target.tier}→{data.tier}")
        # Route through the billing chokepoint so a tier_change_audits
        # row lands automatically. Caller commits below as part of the
        # combined patch transaction.
        from app.services.billing import apply_tier_change
        from app.services.billing.tier_change import UnknownTierError

        try:
            await apply_tier_change(
                db,
                target,
                data.tier,
                reason="admin_panel",
                actor=admin,
            )
        except UnknownTierError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if data.role is not None and data.role != target.role:
        # Guard against demoting the LAST admin in the system — if this is
        # the only admin row, refuse rather than lock everyone out.
        if target.role == "admin" and data.role != "admin":
            remaining_q = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "admin",
                    User.id != target.id,
                    User.deleted_at.is_(None),
                )
            )
            remaining = int(remaining_q.scalar() or 0)
            if remaining == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote the last remaining admin",
                )
        actions.append(f"role={target.role}→{data.role}")
        target.role = data.role
    if data.organization_id is not None:
        new_org = data.organization_id or None  # empty string → null
        if new_org != target.organization_id:
            actions.append(f"org_id={target.organization_id}→{new_org}")
            target.organization_id = new_org
    if data.restore and target.deleted_at is not None:
        actions.append("restore")
        target.deleted_at = None
    if data.reactivate and target.deactivated_at is not None:
        actions.append("reactivate")
        target.deactivated_at = None

    if not actions:
        # No-op PATCH still returns the row — clients can use this for
        # "show me the canonical state". But don't bump updated_at.
        return AdminUserRow.model_validate(target)

    target.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(target)

    logger.info(
        "admin action by=%s target_user=%s actions=%s",
        admin.id,
        target.id,
        ", ".join(actions),
    )
    return AdminUserRow.model_validate(target)


@router.get("/pipelines/failed", response_model=list[FailedPipelineRow])
async def list_failed_pipelines(
    hours: int = Query(72, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Cross-table view of recent pipeline failures.

    The dashboard's per-user view only shows that user's failures; an
    operator triaging a Gemini outage needs to see all of them across
    the system. Filters to the trailing ``hours`` window so the result
    set stays small.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    sc_q = await db.execute(
        select(SourceCheck, User.email)
        .join(User, User.id == SourceCheck.user_id, isouter=True)
        .where(
            SourceCheck.status == "failed",
            SourceCheck.created_at >= since,
            SourceCheck.deleted_at.is_(None),
        )
        .order_by(SourceCheck.created_at.desc())
        .limit(limit)
    )
    rp_q = await db.execute(
        select(ResearcherProfile, User.email)
        .join(User, User.id == ResearcherProfile.user_id, isouter=True)
        .where(
            ResearcherProfile.analysis_status == "failed",
            ResearcherProfile.created_at >= since,
            ResearcherProfile.deleted_at.is_(None),
        )
        .order_by(ResearcherProfile.created_at.desc())
        .limit(limit)
    )

    rows: list[FailedPipelineRow] = []
    for sc, email in sc_q.all():
        rows.append(
            FailedPipelineRow(
                kind="source_check",
                id=sc.id,
                user_id=sc.user_id,
                user_email=email,
                title=sc.input_title or sc.input_content[:60],
                status=str(sc.status),
                created_at=sc.created_at,
                updated_at=sc.completed_at,
            )
        )
    for rp, email in rp_q.all():
        rows.append(
            FailedPipelineRow(
                kind="researcher_analysis",
                id=rp.id,
                user_id=rp.user_id,
                user_email=email,
                title=rp.researcher_name,
                status=str(rp.analysis_status),
                created_at=rp.created_at,
                updated_at=rp.last_analyzed_at,
            )
        )

    # Mix-merge by created_at desc, take the most recent `limit`.
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows[:limit]


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Single-shot stats for the admin dashboard cards."""
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    # Per-tier user counts. Includes deleted=false to mirror the "live"
    # user base; a separate query could expose the deleted backlog if the
    # operator needs it.
    tier_q = await db.execute(
        select(User.tier, func.count(User.id))
        .where(User.deleted_at.is_(None))
        .group_by(User.tier)
    )
    users_by_tier = {tier: 0 for tier in _TIERS}
    for tier, count in tier_q.all():
        users_by_tier[str(tier)] = int(count)

    role_q = await db.execute(
        select(User.role, func.count(User.id))
        .where(User.deleted_at.is_(None))
        .group_by(User.role)
    )
    users_by_role = {str(role): int(count) for role, count in role_q.all()}

    users_total = int(
        (await db.execute(
            select(func.count(User.id)).where(User.deleted_at.is_(None))
        )).scalar() or 0
    )

    sc_total = int(
        (await db.execute(
            select(func.count(SourceCheck.id)).where(
                SourceCheck.created_at >= since_24h,
                SourceCheck.deleted_at.is_(None),
            )
        )).scalar() or 0
    )
    sc_failures = int(
        (await db.execute(
            select(func.count(SourceCheck.id)).where(
                SourceCheck.created_at >= since_24h,
                SourceCheck.status == "failed",
                SourceCheck.deleted_at.is_(None),
            )
        )).scalar() or 0
    )
    rp_total = int(
        (await db.execute(
            select(func.count(ResearcherProfile.id)).where(
                ResearcherProfile.created_at >= since_24h,
                ResearcherProfile.deleted_at.is_(None),
            )
        )).scalar() or 0
    )
    rp_failures = int(
        (await db.execute(
            select(func.count(ResearcherProfile.id)).where(
                ResearcherProfile.created_at >= since_24h,
                ResearcherProfile.analysis_status == "failed",
                ResearcherProfile.deleted_at.is_(None),
            )
        )).scalar() or 0
    )
    rpt_total = int(
        (await db.execute(
            select(func.count(Report.id)).where(
                Report.created_at >= since_24h,
                Report.deleted_at.is_(None),
            )
        )).scalar() or 0
    )

    return AdminStatsResponse(
        users_total=users_total,
        users_by_tier=users_by_tier,
        users_by_role=users_by_role,
        source_checks_last_24h=sc_total,
        source_check_failures_last_24h=sc_failures,
        researcher_analyses_last_24h=rp_total,
        researcher_failures_last_24h=rp_failures,
        reports_last_24h=rpt_total,
    )
