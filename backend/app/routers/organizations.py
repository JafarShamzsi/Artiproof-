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
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import EmailStr
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import settings
from app.database import get_db
from app.deps.org import lock_and_require_org_admin, require_org_admin, require_org_member
from app.models.organization import Organization
from app.models.organization_audit_log import OrganizationAuditLog
from app.models.organization_invite import OrganizationInvite
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
    OrgInviteAccept,
)
from app.schemas.organization import (
    OrgAuditLogItem,
    OrgAuditLogResponse,
    OrgCreateRequest,
    OrgDetailResponse,
    OrgInviteItem,
    OrgInviteListResponse,
    OrgSettingsUpdate,
)
from app.schemas.report import OrganizationBranding, OrganizationBrandingResponse
from app.services.email import render_org_invite, send_email
from app.services.org_audit import record_org_action
from app.services.team_invites import accept_invite, lock_org, lock_user, validate_invite
from app.utils.auth import create_invite_token, decode_invite_token, get_current_user
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


# Self-serve trial duration. Matches the public copy on /pricing#team.
_TRIAL_DAYS = 14
# Default seat cap for the Team Starter bracket (matches /pricing#team).
_DEFAULT_SEAT_LIMIT = 10
# Invite token TTL — matches `_INVITE_TOKEN_TTL_DAYS` in auth.py so the
# stored row's `expires_at` agrees with the JWT's `exp`.
_INVITE_TTL_DAYS = 7

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Best-effort slug from a display name. Lowercase, hyphenated, no
    repeated separators. Falls back to a uuid suffix when the name is
    all-symbols and yields an empty slug."""
    base = _SLUG_RE.sub("-", name.lower()).strip("-")
    if not base:
        base = "team"
    return base[:48]


# ─── Org create / detail / settings ───────────────────────────────────────


@router.post("/invites/preview")
@limiter.limit("20/hour")
async def preview_org_invite(
    request: Request,
    data: OrgInviteAccept,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Show the recipient what they would join. Never accepts or commits."""
    payload = decode_invite_token(data.token)
    if payload["email"].lower() != current_user.email.lower():
        raise HTTPException(status_code=400, detail="Invalid or unavailable invitation")
    org = await lock_org(db, payload["org_id"])
    invite = await validate_invite(db, data.token, current_user.email, org.id, allow_accepted=True)
    return {"organization_id": org.id, "name": org.name, "role": invite.role}


async def _seat_used(db: AsyncSession, org_id: str) -> int:
    """Live count of members in the org. Used everywhere we need to
    enforce or display the seat cap. One COUNT — cheap enough that we
    don't memoize."""
    q = await db.execute(
        select(func.count(OrganizationMember.user_id)).where(
            OrganizationMember.organization_id == org_id,
        )
    )
    return q.scalar() or 0


async def _build_detail(
    *,
    db: AsyncSession,
    org: Organization,
    current_user_role: str,
) -> OrgDetailResponse:
    used = await _seat_used(db, org.id)
    return OrgDetailResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        contact_email=org.contact_email,
        seat_limit=org.seat_limit,
        seat_used=used,
        seat_remaining=max(0, org.seat_limit - used),
        is_trial=org.is_trial,
        trial_ends_at=org.trial_ends_at,
        created_at=org.created_at,
        current_user_role=current_user_role,  # type: ignore[arg-type]
    )


@router.post("", response_model=OrgDetailResponse, status_code=201)
@limiter.limit("5/hour")
async def create_organization(
    request: Request,
    data: OrgCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-serve "Start a team" trial.

    Creates an Organization, promotes the calling user to ``tier="team"``
    + ``org_role="admin"``, stamps a 14-day trial expiry, and returns
    the full org detail so the frontend can immediately route to
    ``/team``.

    Rate-limited (5/hour/IP) so a bored user can't spawn a hundred orgs
    in a script. Fails if the user is already in an org — a user
    belongs to at most one org at a time by design.
    """
    if current_user.deleted_at is not None or current_user.deactivated_at is not None:
        # Defensive — the auth dep should already 401 these but a
        # short-circuited test could slip through.
        raise HTTPException(status_code=403, detail="Account not active")

    current_user = await lock_user(db, current_user.id)
    if current_user is None or current_user.deleted_at is not None or current_user.deactivated_at is not None:
        raise HTTPException(status_code=403, detail="Account not active")

    existing_memberships = (await db.execute(select(OrganizationMember).where(
        OrganizationMember.user_id == current_user.id))).scalars().all()

    if current_user.organization_id is not None or existing_memberships:
        raise HTTPException(
            status_code=409,
            detail="You already belong to an organization. Leave it before creating a new one.",
        )

    # Slug uniqueness — if the caller supplied one we honour it as-is;
    # otherwise we derive one and append a short suffix if collision.
    desired_slug = data.slug or _slugify(data.name)
    slug = desired_slug
    for attempt in range(5):
        existing_q = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if existing_q.scalar_one_or_none() is None:
            break
        if data.slug:
            # Caller asked for this exact slug — refuse rather than mangle.
            raise HTTPException(
                status_code=409,
                detail=f"Slug '{data.slug}' is already taken.",
            )
        slug = f"{desired_slug}-{uuid.uuid4().hex[:4]}"
    else:
        # Five collisions in a row — odds are negligible but bail safely.
        raise HTTPException(
            status_code=500, detail="Could not allocate a unique slug — try again."
        )

    now = datetime.now(timezone.utc)
    org = Organization(
        id=str(uuid.uuid4()),
        name=data.name.strip(),
        slug=slug,
        seat_limit=_DEFAULT_SEAT_LIMIT,
        is_trial=True,
        trial_ends_at=now + timedelta(days=_TRIAL_DAYS),
        contact_email=current_user.email,
        # Stamp timestamps explicitly so the response shape is correct
        # even in environments where the server-default isn't visible
        # until the row round-trips through the DB. In prod the DB also
        # sets these defaults; the explicit assignment makes the value
        # available to the same-request response without a re-fetch.
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    # Flush so org.id is queryable for the membership FK below — we don't
    # commit yet because we want the whole thing to roll back together if
    # the audit write blows up.
    await db.flush()

    # Promote the creator to admin of the new org.
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="admin",
        invited_by=None,  # self-created, no inviter
    )
    db.add(membership)
    # Pointer + tier flip. We deliberately do NOT route this through
    # services/billing/tier_change.py here — the user is "team" only as
    # long as the trial is live, and the canonical billing chokepoint
    # is for paid-tier transitions tied to BillingEvent rows. The trial
    # tier flip is a separate concept tracked in the audit log instead.
    current_user.organization_id = org.id
    current_user.tier = "team"

    await record_org_action(
        db=db,
        org_id=org.id,
        actor_user_id=current_user.id,
        action="org_created",
        payload={
            "is_trial": True,
            "trial_ends_at": org.trial_ends_at.isoformat(),
            "seat_limit": org.seat_limit,
        },
    )

    await db.commit()
    await db.refresh(org)
    return await _build_detail(db=db, org=org, current_user_role="admin")


@router.get("/{org_id}", response_model=OrgDetailResponse)
async def get_organization(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    membership: OrganizationMember = Depends(require_org_member),
):
    """Org detail — read by any member. Returns seat usage so the
    `/team` workspace can render the seat-cap meter without a second
    request."""
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return await _build_detail(db=db, org=org, current_user_role=membership.role)


@router.patch("/{org_id}", response_model=OrgDetailResponse)
async def update_organization(
    org_id: str,
    data: OrgSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Admin-only org-settings patch. Currently mutable: name +
    contact_email. The seat_limit field is intentionally NOT mutable
    from here — capacity changes go through the (future) billing
    upgrade path."""
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    fields_changed: list[str] = []
    if data.name is not None and data.name != org.name:
        org.name = data.name.strip()
        fields_changed.append("name")
    if data.contact_email is not None:
        # Empty string => clear it. EmailStr already validated non-empty
        # for any non-None input, so this branch only fires on a real
        # email value here. (For "clear" we'd accept None.)
        if org.contact_email != data.contact_email:
            org.contact_email = data.contact_email
            fields_changed.append("contact_email")

    if fields_changed:
        await record_org_action(
            db=db,
            org_id=org_id,
            actor_user_id=admin_membership.user_id,
            action="org_settings_changed",
            payload={"fields": fields_changed},
        )

    await db.commit()
    await db.refresh(org)
    return await _build_detail(
        db=db, org=org, current_user_role=admin_membership.role
    )


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
    *, db: AsyncSession, user_id: str, org_id: str, month_start: datetime
) -> tuple[int, int, int]:
    """Return ``(source_checks, researcher_analyses, reports)`` created
    by ``user_id`` owned by ``org_id`` in the current calendar month,
    LIVE rows only. Personal/previous-organization resources never count.

    Three independent COUNTs because the tables are unrelated. Acceptable
    cost while orgs stay small (< few hundred members); denormalise to a
    monthly sweep if the org grows past that.
    """
    sc_q = await db.execute(
        select(func.count(SourceCheck.id)).where(
            and_(
                SourceCheck.user_id == user_id,
                SourceCheck.organization_id == org_id,
                SourceCheck.deleted_at.is_(None),
                SourceCheck.created_at >= month_start,
            )
        )
    )
    rp_q = await db.execute(
        select(func.count(ResearcherProfile.id)).where(
            and_(
                ResearcherProfile.user_id == user_id,
                ResearcherProfile.organization_id == org_id,
                ResearcherProfile.deleted_at.is_(None),
                ResearcherProfile.created_at >= month_start,
            )
        )
    )
    rpt_q = await db.execute(
        select(func.count(Report.id)).where(
            and_(
                Report.user_id == user_id,
                Report.organization_id == org_id,
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
            db=db, user_id=user.id, org_id=org_id, month_start=month_start
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


async def _enforce_seat_capacity(
    *, db: AsyncSession, org: Organization, additions: int = 1
) -> None:
    """Refuse if adding ``additions`` more members would exceed the cap.

    Caller holds the organization row lock. Live pending invitations reserve
    seats; acceptance exchanges its own reservation for one membership."""
    used = await _seat_used(db, org.id)
    pending_q = await db.execute(
        select(func.count(OrganizationInvite.id)).where(
            OrganizationInvite.organization_id == org.id,
            OrganizationInvite.status == "pending",
            OrganizationInvite.revoked_at.is_(None),
            OrganizationInvite.expires_at > datetime.now(timezone.utc),
        )
    )
    pending = pending_q.scalar() or 0
    if used + pending + additions > org.seat_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Seat limit reached ({used + pending}/{org.seat_limit}). "
                "Upgrade your Team plan or remove pending invites to add more members."
            ),
        )


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
    """Reserve a pending invitation, regardless of whether an account exists.

    Only an authenticated, verified recipient's explicit POST can join.
    """
    email_lower = data.email.lower()
    org, admin_membership = await lock_and_require_org_admin(
        db=db, org_id=org_id, actor_user_id=admin_membership.user_id)
    # require_org_admin already 404'd if the org didn't exist, but the
    # name is needed for the email and we still need a defensive guard
    # against a TOCTOU between the dep and this query.
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Write a pending invite row + email the signed
    # link. Reject if there's already a live (status=pending) row for
    # this org+email so duplicate /invite clicks don't pile up rows.
    existing_invite_q = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.organization_id == org_id,
            func.lower(OrganizationInvite.email) == email_lower,
            OrganizationInvite.status == "pending",
            OrganizationInvite.revoked_at.is_(None),
            OrganizationInvite.expires_at > datetime.now(timezone.utc),
        )
    )
    if existing_invite_q.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="An invite for this email is already pending. Use Resend instead.",
        )

    # Seat cap — pending invites count toward the cap.
    await _enforce_seat_capacity(db=db, org=org, additions=1)

    token = create_invite_token(
        org_id=org_id,
        email=email_lower,
        role=data.role,
        invited_by=admin_membership.user_id,
    )
    now = datetime.now(timezone.utc)
    invite_row = OrganizationInvite(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        email=email_lower,
        role=data.role,
        token=token,
        status="pending",
        invited_by=admin_membership.user_id,
        created_at=now,
        expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.add(invite_row)

    await record_org_action(
        db=db,
        org_id=org_id,
        actor_user_id=admin_membership.user_id,
        action="invite_sent",
        payload={"email": email_lower, "role": data.role},
    )
    await db.commit()

    invite_url = f"{settings.APP_URL}/register?invite={token}"
    inviter_q = await db.execute(select(User).where(User.id == admin_membership.user_id))
    inviter = inviter_q.scalar_one_or_none()
    subject, html, text = render_org_invite(
        org_name=org.name,
        inviter_name=inviter.full_name if inviter else "",
        invite_url=invite_url,
        ttl_days=_INVITE_TTL_DAYS,
    )
    sent = await send_email(to=email_lower, subject=subject, html=html, text=text)
    if not sent:
        logger.warning(
            "org invite email failed to send for org=%s — token still valid",
            org_id,
        )
    return OrgMemberInviteResponse(invited_email=email_lower, status="invited")


@router.post("/{org_id}/invites/accept")
@limiter.limit("20/hour")
async def accept_org_invite(
    request: Request,
    org_id: str,
    data: OrgInviteAccept,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicit recipient consent; no membership is required before joining."""
    await accept_invite(db, user_id=current_user.id, org_id=org_id, token=data.token)
    await db.commit()
    return {"organization_id": org_id, "status": "accepted"}


# ─── Pending invites: list / resend / revoke ──────────────────────────────


@router.get(
    "/{org_id}/invites", response_model=OrgInviteListResponse
)
async def list_org_invites(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_admin),
):
    """List pending invites for the org. Admin only — non-admin members
    can already see the live member roster but not the pipeline of
    pending ones (intentionally less surface area for a leaver to
    snapshot)."""
    # Reads never mutate invitations: a stale GET must not overwrite an
    # acceptance/revocation committed by another transaction.
    now = datetime.now(timezone.utc)
    rows_q = await db.execute(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.status == "pending",
            OrganizationInvite.revoked_at.is_(None),
            OrganizationInvite.expires_at > now,
        )
        .order_by(OrganizationInvite.created_at.desc())
    )
    rows = list(rows_q.scalars())
    items = [
        OrgInviteItem(
            id=r.id,
            email=r.email,
            role=r.role,  # type: ignore[arg-type]
            status=r.status,  # type: ignore[arg-type]
            invited_by=r.invited_by,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in rows
    ]
    return OrgInviteListResponse(items=items, total=len(items))


@router.post("/{org_id}/invites/{invite_id}/resend", status_code=204)
@limiter.limit("20/hour")
async def resend_org_invite(
    request: Request,
    org_id: str,
    invite_id: str,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Re-mail an existing pending invite. The token is NOT re-issued —
    the URL in the original email keeps working — so the user doesn't
    end up with two competing links."""
    _, admin_membership = await lock_and_require_org_admin(
        db=db, org_id=org_id, actor_user_id=admin_membership.user_id)
    invite = await db.get(OrganizationInvite, invite_id, populate_existing=True, with_for_update=True)
    if invite is None or invite.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if (invite.status != "pending" or invite.revoked_at is not None
            or invite.expires_at <= datetime.now(timezone.utc)):
        raise HTTPException(
            status_code=400, detail=f"Cannot resend a {invite.status} invite"
        )

    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    inviter_q = await db.execute(
        select(User).where(User.id == admin_membership.user_id)
    )
    inviter = inviter_q.scalar_one_or_none()
    invite_url = f"{settings.APP_URL}/register?invite={invite.token}"
    subject, html, text = render_org_invite(
        org_name=org.name,
        inviter_name=inviter.full_name if inviter else "",
        invite_url=invite_url,
        ttl_days=_INVITE_TTL_DAYS,
    )
    sent = await send_email(to=invite.email, subject=subject, html=html, text=text)
    if not sent:
        logger.warning(
            "org invite resend failed for org=%s invite=%s", org_id, invite_id
        )

    await record_org_action(
        db=db,
        org_id=org_id,
        actor_user_id=admin_membership.user_id,
        action="invite_resent",
        payload={"email": invite.email},
    )
    await db.commit()
    return None


@router.delete("/{org_id}/invites/{invite_id}", status_code=204)
async def revoke_org_invite(
    org_id: str,
    invite_id: str,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Revoke a pending invite. Flips status to ``revoked`` and stamps
    ``revoked_at``. The signup flow refuses any token whose backing row
    is not ``pending``, so a stolen link goes dead immediately."""
    _, admin_membership = await lock_and_require_org_admin(
        db=db, org_id=org_id, actor_user_id=admin_membership.user_id)
    invite = await db.get(OrganizationInvite, invite_id, populate_existing=True, with_for_update=True)
    if invite is None or invite.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != "pending":
        # Idempotency: revoking an already-revoked or expired row is a
        # no-op success — clicking revoke twice shouldn't 500.
        return None

    invite.status = "revoked"
    invite.revoked_at = datetime.now(timezone.utc)
    await record_org_action(
        db=db,
        org_id=org_id,
        actor_user_id=admin_membership.user_id,
        action="invite_revoked",
        payload={"email": invite.email},
    )
    await db.commit()
    return None


# ─── Audit log ────────────────────────────────────────────────────────────


@router.get("/{org_id}/audit-log", response_model=OrgAuditLogResponse)
async def list_org_audit_log(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: OrganizationMember = Depends(require_org_admin),
):
    """Paginated audit log — admin only. Newest first.

    Joins actor + target user emails via separate aliases so a row whose
    actor was deleted still renders with the target email (and vice
    versa)."""
    total_q = await db.execute(
        select(func.count(OrganizationAuditLog.id)).where(
            OrganizationAuditLog.organization_id == org_id,
        )
    )
    total = total_q.scalar() or 0

    actor_alias = aliased(User)
    target_alias = aliased(User)
    offset = (page - 1) * page_size
    rows_q = await db.execute(
        select(OrganizationAuditLog, actor_alias, target_alias)
        .outerjoin(
            actor_alias, actor_alias.id == OrganizationAuditLog.actor_user_id
        )
        .outerjoin(
            target_alias, target_alias.id == OrganizationAuditLog.target_user_id
        )
        .where(OrganizationAuditLog.organization_id == org_id)
        .order_by(OrganizationAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items: list[OrgAuditLogItem] = []
    for log_row, actor, target in rows_q.all():
        items.append(
            OrgAuditLogItem(
                id=log_row.id,
                action=log_row.action,
                actor_user_id=log_row.actor_user_id,
                actor_email=actor.email if actor else None,
                target_user_id=log_row.target_user_id,
                target_email=target.email if target else None,
                payload=log_row.payload or {},
                created_at=log_row.created_at,
            )
        )
    return OrgAuditLogResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=OrgMemberItem,
)
async def update_org_member_role(
    org_id: str,
    user_id: str,
    data: OrgMemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin_membership: OrganizationMember = Depends(require_org_admin),
):
    """Promote / demote a member.

    Refuses to demote the **last** admin so the org never ends up with
    no admins (mirror of the admin router's last-admin guard).
    """
    _, admin_membership = await lock_and_require_org_admin(
        db=db, org_id=org_id, actor_user_id=admin_membership.user_id)
    mem_q = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        ).execution_options(populate_existing=True)
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

    prev_role = member.role
    member.role = data.role
    if prev_role != data.role:
        await record_org_action(
            db=db,
            org_id=org_id,
            actor_user_id=admin_membership.user_id,
            action="role_changed",
            target_user_id=user_id,
            payload={"from_role": prev_role, "to_role": data.role},
        )
    await db.commit()
    await db.refresh(member)

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Member user not found")
    sc, ra, rpt = await _usage_for_member(
        db=db, user_id=user.id, org_id=org_id, month_start=_month_start_utc()
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
    await lock_user(db, user_id)
    _, admin_membership = await lock_and_require_org_admin(
        db=db, org_id=org_id, actor_user_id=admin_membership.user_id)
    mem_q = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        ).execution_options(populate_existing=True)
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

    target_email: Optional[str] = None
    target_user = await db.get(User, user_id)
    if target_user is not None:
        target_email = target_user.email

    await db.delete(member)
    # Sync the denormalised pointer on the user.
    if target_user is not None and target_user.organization_id == org_id:
        target_user.organization_id = None

    await record_org_action(
        db=db,
        org_id=org_id,
        actor_user_id=admin_membership.user_id,
        action="member_removed",
        target_user_id=user_id,
        payload={"email": target_email} if target_email else {},
    )
    await db.commit()
    return None
