"""Organization-scoped endpoints — branding + member management.

Two surfaces:

- ``GET /branding`` / ``PUT /branding`` — white-label colors + logo
  for generated reports. Any member can read; admin to write.

- ``GET|POST|PATCH|DELETE /members`` — org membership management.
  All gated on the new ``require_org_admin`` (writes) /
  ``require_org_member`` (reads) deps from ``app.deps.org``.

Membership semantics (decided in Phase C migration 0013):

- ``organization_members`` is the source of truth for "is X in org Y"
  and "what role does X have in Y".
- ``users.organization_id`` is kept in sync as a denormalised pointer
  to the user's primary org. Updated transactionally with every
  add/remove here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import EmailStr
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps.org import require_org_admin, require_org_member
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.schemas.org_member import (
    OrgMemberInvite,
    OrgMemberInviteResponse,
    OrgMemberItem,
    OrgMemberListResponse,
    OrgMemberRoleUpdate,
)
from app.schemas.report import OrganizationBranding, OrganizationBrandingResponse
from app.services.email import render_org_invite, send_email
from app.utils.auth import create_invite_token, get_current_user
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


# ─── Branding ──────────────────────────────────────────────────────────────


def _branding_response(o: Organization) -> OrganizationBrandingResponse:
    return OrganizationBrandingResponse(
        id=o.id,
        name=o.name,
        logo_url=o.logo_url,
        primary_color=o.primary_color,
        secondary_color=o.secondary_color,
    )


@router.get("/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def get_org_branding(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_member),
):
    """Any member can read the org branding."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _branding_response(org)


@router.put("/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def update_org_branding(
    org_id: str,
    data: OrganizationBranding,
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_admin),
):
    """Only org admins can edit branding (was: any team-tier member —
    Phase C tightens this to admin since the org now has a real role)."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.logo_url = data.logo_url
    org.primary_color = data.primary_color
    org.secondary_color = data.secondary_color
    await db.commit()
    await db.refresh(org)
    return _branding_response(org)


# ─── Member helpers ────────────────────────────────────────────────────────


def _month_start_utc() -> datetime:
    """First instant of the current calendar month in UTC. Used to gate
    MTD usage counts."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _usage_for_member(
    *, db: AsyncSession, user_id: str, month_start: datetime
) -> tuple[int, int, int]:
    """Return ``(source_checks, researcher_analyses, reports)`` created
    by ``user_id`` in the current calendar month, LIVE rows only.

    Three independent COUNTs because the tables are unrelated. Acceptable
    cost while orgs stay small (< few hundred members); denormalise to a
    monthly sweep if the org grows past that.
    """
    sc_q = await db.execute(
        select(func.count(SourceCheck.id)).where(
            and_(
                SourceCheck.user_id == user_id,
                SourceCheck.deleted_at.is_(None),
                SourceCheck.created_at >= month_start,
            )
        )
    )
    rp_q = await db.execute(
        select(func.count(ResearcherProfile.id)).where(
            and_(
                ResearcherProfile.user_id == user_id,
                ResearcherProfile.deleted_at.is_(None),
                ResearcherProfile.created_at >= month_start,
            )
        )
    )
    rpt_q = await db.execute(
        select(func.count(Report.id)).where(
            and_(
                Report.user_id == user_id,
                Report.deleted_at.is_(None),
                Report.created_at >= month_start,
            )
        )
    )
    return sc_q.scalar() or 0, rp_q.scalar() or 0, rpt_q.scalar() or 0


# ─── Members: list / invite / patch / remove ──────────────────────────────


@router.get("/{org_id}/members", response_model=OrgMemberListResponse)
async def list_org_members(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_member),
):
    """List every member of the org with their role + MTD usage.

    Available to any member, not just admins — the team-tier value
    proposition is shared visibility, so a regular member can see what
    their colleagues have been doing this month.
    """
    rows_q = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .where(User.deleted_at.is_(None))
        .order_by(OrganizationMember.joined_at.asc())
    )
    rows = list(rows_q.all())
    month_start = _month_start_utc()

    items: list[OrgMemberItem] = []
    for member, user in rows:
        sc, ra, rpt = await _usage_for_member(
            db=db, user_id=user.id, month_start=month_start
        )
        items.append(
            OrgMemberItem(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=member.role,
                joined_at=member.joined_at,
                invited_by=member.invited_by,
                source_checks_mtd=sc,
                researcher_analyses_mtd=ra,
                reports_mtd=rpt,
            )
        )

    return OrgMemberListResponse(items=items, total=len(items))


@router.post(
    "/{org_id}/members/invite",
    response_model=OrgMemberInviteResponse,
    status_code=201,
)
@limiter.limit("20/hour")
async def invite_org_member(
    request: Request,
    org_id: str,
    data: OrgMemberInvite,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Invite someone by email.

    If a User exists with that email, they're attached as a member
    immediately and (best-effort) emailed a notification. Otherwise an
    invite email goes out with a signed link that auto-attaches them
    on signup.

    The admin's user_id is stamped as ``invited_by`` so the audit trail
    survives even if the inviter later leaves the org.
    """
    email_lower = data.email.lower()
    org = await db.get(Organization, org_id)
    # require_org_admin already 404'd if the org didn't exist, but the
    # name is needed for the email and we still need a defensive guard
    # against a TOCTOU between the dep and this query.
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Existing user path — attach immediately.
    existing_q = await db.execute(select(User).where(func.lower(User.email) == email_lower))
    existing = existing_q.scalar_one_or_none()
    if existing is not None:
        if existing.deleted_at is not None:
            raise HTTPException(
                status_code=409,
                detail="That account has been deleted — they need to re-register.",
            )
        # Already in some org?
        if existing.organization_id is not None and existing.organization_id != org_id:
            raise HTTPException(
                status_code=409,
                detail="That user already belongs to another organization.",
            )
        # Already a member of this org?
        already_q = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == existing.id,
            )
        )
        if already_q.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail="Already a member of this organization."
            )
        member = OrganizationMember(
            organization_id=org_id,
            user_id=existing.id,
            role=data.role,
            invited_by=admin_membership.user_id,
        )
        db.add(member)
        # Sync the denormalised pointer.
        existing.organization_id = org_id
        await db.commit()

        # Best-effort welcome email. The "they're now in the team" email
        # uses the same invite template — the difference is purely the
        # link (lands on /login since they have an account).
        login_url = f"{settings.APP_URL}/login"
        subject, html, text = render_org_invite(
            org_name=org.name,
            inviter_name="",
            invite_url=login_url,
            ttl_days=7,
        )
        await send_email(to=existing.email, subject=subject, html=html, text=text)
        return OrgMemberInviteResponse(invited_email=existing.email, status="added")

    # No existing user — issue a signed invite + email it.
    token = create_invite_token(
        org_id=org_id,
        email=email_lower,
        role=data.role,
        invited_by=admin_membership.user_id,
    )
    invite_url = f"{settings.APP_URL}/register?invite={token}"
    inviter_q = await db.execute(select(User).where(User.id == admin_membership.user_id))
    inviter = inviter_q.scalar_one_or_none()
    subject, html, text = render_org_invite(
        org_name=org.name,
        inviter_name=inviter.full_name if inviter else "",
        invite_url=invite_url,
        ttl_days=7,
    )
    sent = await send_email(to=email_lower, subject=subject, html=html, text=text)
    if not sent:
        logger.warning(
            "org invite email failed to send for org=%s — token still valid",
            org_id,
        )
    return OrgMemberInviteResponse(invited_email=email_lower, status="invited")


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=OrgMemberItem,
)
async def update_org_member_role(
    org_id: str,
    user_id: str,
    data: OrgMemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_admin),
):
    """Promote / demote a member.

    Refuses to demote the **last** admin so the org never ends up with
    no admins (mirror of the admin router's last-admin guard).
    """
    mem_q = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = mem_q.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found in this org")

    if member.role == "admin" and data.role == "member":
        admin_count_q = await db.execute(
            select(func.count(OrganizationMember.user_id)).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "admin",
            )
        )
        if (admin_count_q.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last admin of an organization.",
            )

    member.role = data.role
    await db.commit()
    await db.refresh(member)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Member user not found")
    sc, ra, rpt = await _usage_for_member(
        db=db, user_id=user.id, month_start=_month_start_utc()
    )
    return OrgMemberItem(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        joined_at=member.joined_at,
        invited_by=member.invited_by,
        source_checks_mtd=sc,
        researcher_analyses_mtd=ra,
        reports_mtd=rpt,
    )


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_org_member(
    org_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Remove a member from the org.

    Same last-admin guard as the role-change endpoint: the last admin
    can't remove themselves either — they have to promote someone else
    first.
    """
    mem_q = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = mem_q.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found in this org")

    if member.role == "admin":
        admin_count_q = await db.execute(
            select(func.count(OrganizationMember.user_id)).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "admin",
            )
        )
        if (admin_count_q.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin of an organization.",
            )

    await db.delete(member)
    # Sync the denormalised pointer on the user.
    user = await db.get(User, user_id)
    if user is not None and user.organization_id == org_id:
        user.organization_id = None
    await db.commit()
    return None
