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
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TIER_LIMITS
from app.database import get_db
from app.models.celery_dlq import CeleryDLQ
from app.models.celery_run_log import CeleryRunLog
from app.models.llm_metric import LLMMetric as GeminiMetric  # back-compat alias
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.services.llm import estimate_cost_usd
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
    deactivate: Optional[bool] = Field(
        default=None,
        description=(
            "If true, set deactivated_at to now. The user can still self-"
            "reactivate via /api/auth/reactivate. get_current_user 403s "
            "on deactivated users in the meantime."
        ),
    )
    delete: Optional[bool] = Field(
        default=None,
        description=(
            "If true, soft-delete by setting deleted_at to now. The cleanup "
            "task hard-deletes 30 days later. Use 'restore' before that "
            "window to undo."
        ),
    )
    force_signout: Optional[bool] = Field(
        default=None,
        description=(
            "If true, revoke every session + refresh token for this user. "
            "On their next request the JWT still works until expiry; pair "
            "with 'deactivate' to force them off immediately."
        ),
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


# ─── Telemetry schemas (Phase E) ───────────────────────────────────────────


class GeminiCostByOperation(BaseModel):
    operation: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class GeminiCostByUser(BaseModel):
    user_id: str
    email: Optional[str] = None
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMCostByProvider(BaseModel):
    """Per-provider rollup so finance reports can attribute spend across
    Gemini / OpenAI / Anthropic. Added in Phase 9."""

    provider: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class GeminiCostSummary(BaseModel):
    """Aggregate LLM spend over a window.

    Despite the legacy class name (kept for API back-compat), this now
    sums across every LLM provider. Cost is computed from raw tokens ×
    the per-provider pricing table in ``app.services.llm.factory`` —
    refreshes automatically when vendors revise pricing.
    """

    window_days: int
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    error_rate: float  # share of calls with non-null error_class
    by_operation: list[GeminiCostByOperation]
    top_users: list[GeminiCostByUser]
    # Phase 9: per-provider breakdown. Empty list when no Phase 9
    # rows exist yet (the column defaults to "gemini" so even
    # pre-Phase-9 rows attribute correctly here).
    by_provider: list[LLMCostByProvider] = []


class CeleryRunRow(BaseModel):
    id: str
    task_name: str
    task_id: str
    status: str
    duration_ms: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    exception_class: Optional[str] = None

    model_config = {"from_attributes": True}


class CeleryDLQRow(BaseModel):
    id: str
    task_name: str
    task_id: str
    args: list
    kwargs: dict
    exception_class: str
    exception_message: Optional[str] = None
    retry_count: int
    failed_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[str] = None

    model_config = {"from_attributes": True}


class CeleryDLQRetryResponse(BaseModel):
    """Result of /api/admin/celery/dlq/{id}/retry. ``enqueued=true`` when
    Celery was reachable; ``false`` falls back to "marked resolved without
    retry" — operator should investigate manually."""

    dlq_id: str
    enqueued: bool
    new_task_id: Optional[str] = None


# ─── LLM provider status (Phase 9) ─────────────────────────────────────────


class LLMProviderStatusRow(BaseModel):
    """Per-provider row used by the operator-facing /llm/providers endpoint."""

    name: str  # "gemini" | "openai" | "anthropic"
    configured: bool  # True when the API key is set
    default_model: str
    is_primary: bool
    is_fallback: bool
    is_degraded: bool  # >=3 consecutive failures within the cooldown
    consecutive_failures: int


class LLMProviderStatus(BaseModel):
    """Operator-facing view of which LLM provider is serving analysis traffic.

    The admin Operations panel reads this to answer "which LLM is
    actually generating my reports?" without combing logs.
    """

    primary: str
    fallback: Optional[str]
    providers: list[LLMProviderStatusRow]


# ─── Internal helpers ──────────────────────────────────────────────────────


async def _force_signout_user(db: AsyncSession, user_id: str) -> int:
    """Revoke every session + auth_token belonging to ``user_id``.

    Returns the number of rows touched (sessions + tokens). Used by
    the admin force-signout action and by the delete path (deleting a
    user without dropping their sessions leaves orphaned rows that
    would fail FK cascade on the next session-cleanup sweep).
    """
    from sqlalchemy import delete as sa_delete

    from app.models.auth_token import AuthToken
    from app.models.session import Session as UserSession

    sess_q = await db.execute(
        sa_delete(UserSession).where(UserSession.user_id == user_id)
    )
    tok_q = await db.execute(
        sa_delete(AuthToken).where(AuthToken.user_id == user_id)
    )
    # rowcount is None on some backends / absent on test fakes — coerce to 0.
    sess_rows = getattr(sess_q, "rowcount", 0) or 0
    tok_rows = getattr(tok_q, "rowcount", 0) or 0
    return int(sess_rows) + int(tok_rows)


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

    # Check before billing/role mutations: reject the entire patch, not just
    # the pointer field. Enrollment requires verified recipient acceptance;
    # removal goes through the organization membership endpoint.
    if (data.organization_id is not None
            and (data.organization_id or None) != target.organization_id):
        raise HTTPException(status_code=400, detail="Use organization invitations and membership endpoints to change enrollment")

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
    if data.restore and target.deleted_at is not None:
        actions.append("restore")
        target.deleted_at = None
    if data.reactivate and target.deactivated_at is not None:
        actions.append("reactivate")
        target.deactivated_at = None

    # Destructive / forceful actions — opt-in via the new flags. Each
    # one is logged + emits an audit line.
    now_utc = datetime.now(timezone.utc)

    if data.deactivate and target.deactivated_at is None:
        # Safety: refuse to deactivate the last active admin (mirrors the
        # demote-last-admin guard above). Operators can still delete
        # themselves via the self-service /api/auth/me path with a
        # password — admin force-deactivate isn't a way to lock out the
        # whole org.
        if target.role == "admin":
            remaining_q = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "admin",
                    User.id != target.id,
                    User.deleted_at.is_(None),
                    User.deactivated_at.is_(None),
                )
            )
            if int(remaining_q.scalar() or 0) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate the last remaining admin",
                )
        actions.append("deactivate")
        target.deactivated_at = now_utc

    if data.delete and target.deleted_at is None:
        # Same last-admin guard for delete.
        if target.role == "admin":
            remaining_q = await db.execute(
                select(func.count(User.id)).where(
                    User.role == "admin",
                    User.id != target.id,
                    User.deleted_at.is_(None),
                )
            )
            if int(remaining_q.scalar() or 0) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the last remaining admin",
                )
        actions.append("delete")
        target.deleted_at = now_utc
        # Self-deletion equivalent — also wipe sessions so the user is
        # signed out across devices.
        await _force_signout_user(db, target.id)

    if data.force_signout:
        # Revoke every session + refresh token for this user. The JWT
        # in their browser is still valid until expiry (HS256 doesn't
        # support revocation), but it can no longer be exchanged for
        # a refresh token, so the next access-token refresh fails and
        # the user is bounced to /login.
        deleted = await _force_signout_user(db, target.id)
        actions.append(f"force_signout (revoked={deleted})")

    if not actions:
        # No-op PATCH still returns the row — clients can use this for
        # "show me the canonical state". But don't bump updated_at.
        return AdminUserRow.model_validate(target)

    target.updated_at = now_utc
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


# ─── Telemetry endpoints (Phase E) ─────────────────────────────────────────


@router.get("/gemini/cost-summary", response_model=GeminiCostSummary)
async def gemini_cost_summary(
    days: int = Query(30, ge=1, le=365),
    top_n_users: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Aggregate Gemini spend over the trailing ``days`` window.

    Cost is computed at read-time from raw tokens × the pricing table in
    ``app.services.gemini.client`` — when prices change, refreshing this
    endpoint reprices the whole window.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Overall totals.
    totals_q = await db.execute(
        select(
            func.count(GeminiMetric.id),
            func.coalesce(func.sum(GeminiMetric.input_tokens), 0),
            func.coalesce(func.sum(GeminiMetric.output_tokens), 0),
            func.sum(
                # Counting non-NULL error_class rows.
                case((GeminiMetric.error_class.isnot(None), 1), else_=0)
            ),
        ).where(GeminiMetric.created_at >= since)
    )
    total_calls, total_in, total_out, total_errors = totals_q.one()
    total_calls = int(total_calls or 0)
    total_in = int(total_in or 0)
    total_out = int(total_out or 0)
    total_errors = int(total_errors or 0)
    error_rate = round(total_errors / total_calls, 4) if total_calls else 0.0

    # Per-operation rollup. Group by (provider, operation, model) so a
    # model OR provider change inside an operation doesn't smear pricing.
    by_op_q = await db.execute(
        select(
            GeminiMetric.operation,
            GeminiMetric.provider,
            GeminiMetric.model,
            func.count(GeminiMetric.id),
            func.coalesce(func.sum(GeminiMetric.input_tokens), 0),
            func.coalesce(func.sum(GeminiMetric.output_tokens), 0),
        )
        .where(GeminiMetric.created_at >= since)
        .group_by(GeminiMetric.operation, GeminiMetric.provider, GeminiMetric.model)
        .order_by(func.count(GeminiMetric.id).desc())
    )
    # Merge per-(provider,model) rows back into one row per operation,
    # summing cost using each row's own provider+model pricing.
    op_acc: dict[str, dict[str, float]] = {}
    for op, provider, model, calls, in_t, out_t in by_op_q.all():
        bucket = op_acc.setdefault(
            op or "unknown",
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        )
        bucket["calls"] += int(calls or 0)
        bucket["input_tokens"] += int(in_t or 0)
        bucket["output_tokens"] += int(out_t or 0)
        bucket["cost_usd"] += estimate_cost_usd(
            input_tokens=int(in_t or 0),
            output_tokens=int(out_t or 0),
            model=model or "",
            provider=provider or "gemini",
        )
    by_operation = sorted(
        [GeminiCostByOperation(operation=op, **v) for op, v in op_acc.items()],
        key=lambda r: r.cost_usd,
        reverse=True,
    )

    # Per-provider rollup — added in Phase 9 so finance reports can
    # attribute spend across Gemini / OpenAI / Anthropic.
    by_provider_q = await db.execute(
        select(
            GeminiMetric.provider,
            GeminiMetric.model,
            func.count(GeminiMetric.id),
            func.coalesce(func.sum(GeminiMetric.input_tokens), 0),
            func.coalesce(func.sum(GeminiMetric.output_tokens), 0),
        )
        .where(GeminiMetric.created_at >= since)
        .group_by(GeminiMetric.provider, GeminiMetric.model)
    )
    prov_acc: dict[str, dict[str, float]] = {}
    for provider, model, calls, in_t, out_t in by_provider_q.all():
        bucket = prov_acc.setdefault(
            provider or "gemini",
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        )
        bucket["calls"] += int(calls or 0)
        bucket["input_tokens"] += int(in_t or 0)
        bucket["output_tokens"] += int(out_t or 0)
        bucket["cost_usd"] += estimate_cost_usd(
            input_tokens=int(in_t or 0),
            output_tokens=int(out_t or 0),
            model=model or "",
            provider=provider or "gemini",
        )
    by_provider = sorted(
        [LLMCostByProvider(provider=p, **v) for p, v in prov_acc.items()],
        key=lambda r: r.cost_usd,
        reverse=True,
    )

    # Top-N users by tokens. Joined with users.email so the operator can
    # see which account is racking up cost. Group by provider+model so
    # the per-row pricing lookup is accurate across providers.
    by_user_q = await db.execute(
        select(
            GeminiMetric.user_id,
            User.email,
            GeminiMetric.provider,
            GeminiMetric.model,
            func.count(GeminiMetric.id),
            func.coalesce(func.sum(GeminiMetric.input_tokens), 0),
            func.coalesce(func.sum(GeminiMetric.output_tokens), 0),
        )
        .join(User, User.id == GeminiMetric.user_id, isouter=True)
        .where(
            GeminiMetric.created_at >= since,
            GeminiMetric.user_id.isnot(None),
        )
        .group_by(
            GeminiMetric.user_id,
            User.email,
            GeminiMetric.provider,
            GeminiMetric.model,
        )
    )
    user_acc: dict[str, dict] = {}
    for uid, email, provider, model, calls, in_t, out_t in by_user_q.all():
        bucket = user_acc.setdefault(
            uid,
            {
                "user_id": uid,
                "email": email,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            },
        )
        bucket["calls"] += int(calls or 0)
        bucket["input_tokens"] += int(in_t or 0)
        bucket["output_tokens"] += int(out_t or 0)
        bucket["cost_usd"] += estimate_cost_usd(
            input_tokens=int(in_t or 0),
            output_tokens=int(out_t or 0),
            model=model or "",
            provider=provider or "gemini",
        )
    top_users = sorted(
        [GeminiCostByUser(**v) for v in user_acc.values()],
        key=lambda r: r.cost_usd,
        reverse=True,
    )[:top_n_users]

    total_cost = round(sum(r.cost_usd for r in by_operation), 4)

    return GeminiCostSummary(
        window_days=days,
        total_calls=total_calls,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cost_usd=total_cost,
        error_rate=error_rate,
        by_operation=by_operation,
        top_users=top_users,
        by_provider=by_provider,
    )


@router.get("/celery/runs", response_model=list[CeleryRunRow])
async def celery_runs(
    hours: int = Query(24, ge=1, le=720),
    status: Optional[str] = Query(
        None,
        description='Filter by status: "success" | "failed" | "retry".',
    ),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Recent Celery task executions across all workers. Used by the
    Operations tab of the admin panel."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = select(CeleryRunLog).where(CeleryRunLog.started_at >= since)
    if status:
        q = q.where(CeleryRunLog.status == status)
    q = q.order_by(CeleryRunLog.started_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [CeleryRunRow.model_validate(r) for r in rows]


@router.get("/celery/dlq", response_model=list[CeleryDLQRow])
async def celery_dlq(
    resolved: bool = Query(
        False, description="false = active backlog only, true = history"
    ),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Dead-letter queue contents. Default to active (unresolved) rows."""
    q = select(CeleryDLQ)
    if resolved:
        q = q.where(CeleryDLQ.resolved_at.isnot(None))
    else:
        q = q.where(CeleryDLQ.resolved_at.is_(None))
    q = q.order_by(CeleryDLQ.failed_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [CeleryDLQRow.model_validate(r) for r in rows]


@router.post("/celery/dlq/{dlq_id}/retry", response_model=CeleryDLQRetryResponse)
async def celery_dlq_retry(
    dlq_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Re-enqueue the original task. Marks the DLQ row resolved either way
    — operator can re-mark it active by clearing ``resolved_at`` in SQL
    if the retry itself fails permanently."""
    row = await db.get(CeleryDLQ, dlq_id)
    if row is None:
        raise HTTPException(status_code=404, detail="DLQ entry not found")
    if row.resolved_at is not None:
        raise HTTPException(
            status_code=409, detail="DLQ entry already resolved"
        )

    new_task_id: Optional[str] = None
    enqueued = False
    try:
        from app.tasks import celery_app

        if celery_app is not None:
            async_result = celery_app.send_task(
                row.task_name,
                args=list(row.args or []),
                kwargs=dict(row.kwargs or {}),
            )
            new_task_id = async_result.id
            enqueued = True
    except Exception:
        logger.exception("DLQ retry send_task failed for %s", dlq_id)
        enqueued = False

    row.resolved_at = datetime.now(timezone.utc)
    row.resolved_by_user_id = admin.id
    await db.commit()

    logger.info(
        "admin DLQ retry by=%s dlq_id=%s task=%s enqueued=%s",
        admin.id,
        dlq_id,
        row.task_name,
        enqueued,
    )

    return CeleryDLQRetryResponse(
        dlq_id=dlq_id, enqueued=enqueued, new_task_id=new_task_id
    )


# ─── LLM provider status endpoint (Phase 9) ───────────────────────────────


@router.get("/llm/providers", response_model=LLMProviderStatus)
async def llm_provider_status(
    _admin: User = Depends(require_admin),
):
    """Surface which LLM provider is the primary, which (if any) is the
    fallback, and the configuration/health status of each registered
    provider. Used by the admin Operations panel so support can answer
    "what's actually generating my analyses?" without grepping logs.
    """
    from app.config import settings as _settings
    from app.services.llm.factory import (
        _PROVIDERS,
        _failure_counts,
        _is_degraded,
    )

    primary_name = (_settings.LLM_PROVIDER or "gemini").lower()
    fallback_name = (_settings.LLM_FALLBACK_PROVIDER or "").lower() or None

    rows: list[LLMProviderStatusRow] = []
    for name, provider in sorted(_PROVIDERS.items()):
        rows.append(
            LLMProviderStatusRow(
                name=name,
                configured=provider.is_configured(),
                default_model=provider.default_model,
                is_primary=(name == primary_name),
                is_fallback=(name == fallback_name),
                is_degraded=_is_degraded(name),
                consecutive_failures=_failure_counts.get(name, 0),
            )
        )

    return LLMProviderStatus(
        primary=primary_name,
        fallback=fallback_name,
        providers=rows,
    )
