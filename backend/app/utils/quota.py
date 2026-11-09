"""Tier quota enforcement.

`constants.TIER_LIMITS` defines how many source checks, researcher
analyses, and reports each tier may create per calendar month. The
limits are surfaced read-only by ``/api/dashboard/usage``; this module
adds the missing piece — actually rejecting requests that would push a
user over their tier limit.

Two entry points:

  * ``enforce_quota("source_checks")`` — FastAPI dependency. Replaces
    ``Depends(get_current_user)`` on single-unit endpoints (POST /,
    POST /upload, POST /{id}/rerun). Returns the same ``User`` after
    the check passes, so route handlers don't change shape.

  * ``assert_quota(db, user, kind, units=N)`` — explicit call for bulk
    endpoints that consume more than one unit per request. The bulk
    handler computes N from the payload first, then calls this before
    persisting anything.

The check is *advisory race-safe enough* for current scale: two
concurrent requests can both pass while in flight, technically taking
the user one over. At a 10-or-100/mo budget this is not a billing
risk. A strict implementation would do the count + insert in a single
transaction with row-level locking — punt until usage demands it.

402 Payment Required is the right status here (RFC 7231 §6.5.2). Body
shape is JSON with enough context for the UI to render a useful
upgrade prompt instead of a generic toast.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import TIER_LIMITS
from app.database import get_db
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.utils.auth import get_current_user

QuotaKind = Literal["source_checks", "researcher_analyses", "reports"]


# Maps the dependency's kind string to the model + limit-key. Kept inline
# so a new resource is one-line addition; the dict is intentionally small.
_KIND_CONFIG: dict[str, tuple[type, str]] = {
    "source_checks": (SourceCheck, "source_checks_per_month"),
    "researcher_analyses": (ResearcherProfile, "researcher_analyses_per_month"),
    "reports": (Report, "reports_per_month"),
}


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _count_mtd(db: AsyncSession, user_id: str, kind: QuotaKind) -> int:
    model, _ = _KIND_CONFIG[kind]
    period_start = _month_start()
    q = await db.execute(
        select(func.count(model.id)).where(
            model.user_id == user_id,
            model.deleted_at.is_(None),
            model.created_at >= period_start,
        )
    )
    return int(q.scalar() or 0)


def _quota_exceeded_response(
    *, kind: QuotaKind, used: int, limit: int, requested: int, tier: str
) -> HTTPException:
    """Build the 402 with a uniform payload shape the frontend can render."""
    return HTTPException(
        status_code=402,
        detail={
            "error": "quota_exceeded",
            "kind": kind,
            "tier": tier,
            "used": used,
            "limit": limit,
            "requested": requested,
            "remaining": max(0, limit - used),
            "upgrade_url": f"{settings.APP_URL}/pricing",
            "message": (
                f"You've used {used} of {limit} {kind.replace('_', ' ')} this month "
                f"on the {tier} tier. Upgrade to continue."
            ),
        },
    )


async def assert_quota(
    db: AsyncSession,
    user: User,
    kind: QuotaKind,
    units: int = 1,
) -> None:
    """Raise 402 when ``used + units > limit``. No-op when unlimited.

    Use this in bulk handlers where the unit count comes from the payload.
    For single-unit endpoints prefer the ``enforce_quota(kind)`` dependency.
    """
    tier = user.tier or "free"
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    _, limit_key = _KIND_CONFIG[kind]
    limit = limits.get(limit_key)
    if limit is None:
        return  # unlimited tier (e.g. team)
    if units <= 0:
        return  # nothing to consume
    used = await _count_mtd(db, user.id, kind)
    if used + units > limit:
        raise _quota_exceeded_response(
            kind=kind, used=used, limit=limit, requested=units, tier=tier
        )


def enforce_quota(kind: QuotaKind):
    """FastAPI dependency that gates a single-unit endpoint by tier quota.

    Replace ``current_user: User = Depends(get_current_user)`` with
    ``current_user: User = Depends(enforce_quota("source_checks"))``;
    the dependency still resolves the user, so the rest of the handler
    is unchanged.
    """

    async def _dep(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        await assert_quota(db, current_user, kind, units=1)
        return current_user

    return _dep
