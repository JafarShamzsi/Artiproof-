"""Recipient consent. Caller owns commit/rollback; no GET may call acceptance.

Membership writers lock user -> organization -> invite, in that order. User
and organization serialization uses FOR NO KEY UPDATE: exclusive against other
writers, but compatible with FK checks' KEY SHARE on these parent rows. Using
FOR UPDATE would let an org mutation's audit FK wait on a user whose creation
request is already waiting on that org, forming an implicit-lock deadlock.
These paths do not modify user/org keys. Invitations retain FOR UPDATE.
Use READ COMMITTED (the application's PostgreSQL default).
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.organization_audit_log import OrganizationAuditLog
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.org_audit import record_org_action
from app.utils.auth import decode_invite_token


def invalid_invite():
    return HTTPException(status_code=400, detail="Invalid or unavailable invitation")


async def lock_user(db: AsyncSession, user_id: str) -> User:
    # Auth may have already loaded the row: refresh it *after* acquiring the
    # lock, or a concurrent acceptance can leave a stale organization pointer.
    # PostgreSQL: key_share=True WITHOUT read=True emits NO KEY UPDATE, NOT
    # KEY SHARE. Keep writer exclusion while allowing audit/membership FKs.
    return (await db.execute(select(User).where(User.id == user_id)
                            .with_for_update(key_share=True).execution_options(populate_existing=True))).scalar_one_or_none()


async def lock_org(db: AsyncSession, org_id: str) -> Organization:
    # Same parent-row mode as lock_user; remains a seat/membership mutex while
    # permitting FKs referencing the org. Do not change keys through this lock.
    org = (await db.execute(select(Organization).where(Organization.id == org_id)
                           .with_for_update(key_share=True).execution_options(populate_existing=True))).scalar_one_or_none()
    if org is None:
        raise invalid_invite()
    return org


async def validate_invite(db: AsyncSession, token: str, email: str, org_id: str | None = None,
                          *, allow_accepted: bool = False) -> OrganizationInvite:
    payload = decode_invite_token(token)
    if (payload["email"].lower() != email.lower()
            or (org_id is not None and payload["org_id"] != org_id)):
        raise invalid_invite()
    row = (await db.execute(select(OrganizationInvite).where(
        OrganizationInvite.token == token,
        OrganizationInvite.organization_id == payload["org_id"],
        func.lower(OrganizationInvite.email) == email.lower(),
    ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (row is None or row.token != token or row.organization_id != payload["org_id"]
            or row.email.lower() != email.lower() or row.role not in ("admin", "member")
            or row.role != payload["role"] or row.invited_by != payload["invited_by"]
            or row.revoked_at is not None or row.expires_at <= now
            or row.status not in (("pending", "accepted") if allow_accepted else ("pending",))):
        raise invalid_invite()
    return row


async def accept_invite(db: AsyncSession, *, user_id: str, org_id: str, token: str) -> None:
    user = await lock_user(db, user_id)
    if user is None or user.deleted_at is not None or user.deactivated_at is not None:
        raise HTTPException(status_code=403, detail="Account not active")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email before accepting an invitation")
    org = await lock_org(db, org_id)
    invite = await validate_invite(db, token, user.email, org_id, allow_accepted=True)
    memberships = list((await db.execute(select(OrganizationMember).where(
        OrganizationMember.user_id == user.id))).scalars().all())
    if user.organization_id not in (None, org_id) or any(m.organization_id != org_id for m in memberships):
        raise HTTPException(status_code=409, detail="Leave your current organization before accepting")
    if invite.status == "accepted":
        # A replay may acknowledge the original transition, never rejoin a
        # removed member or restore an old role. Bind replay to the actual
        # accepting account through the transactional audit record.
        audit = (await db.execute(select(OrganizationAuditLog).where(
            OrganizationAuditLog.organization_id == org_id,
            OrganizationAuditLog.action == "invite_accepted",
            OrganizationAuditLog.actor_user_id == user.id,
            OrganizationAuditLog.payload["invite_id"].as_string() == invite.id,
        ))).scalar_one_or_none()
        if not memberships or user.organization_id != org_id or audit is None:
            raise invalid_invite()
        return
    if memberships or user.organization_id is not None:
        raise HTTPException(status_code=409, detail="Already a member of an organization")
    used = (await db.execute(select(func.count(OrganizationMember.user_id)).where(
        OrganizationMember.organization_id == org_id))).scalar() or 0
    if used >= org.seat_limit:
        raise HTTPException(status_code=409, detail="Organization seat limit reached")
    db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=invite.role,
                              invited_by=invite.invited_by))
    user.organization_id = org_id
    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    await record_org_action(db=db, org_id=org_id, actor_user_id=user.id,
                            action="invite_accepted", target_user_id=user.id,
                            payload={"invite_id": invite.id, "role": invite.role})
    await record_org_action(db=db, org_id=org_id, actor_user_id=user.id,
                            action="member_added", target_user_id=user.id,
                            payload={"invite_id": invite.id, "role": invite.role, "email": user.email})
