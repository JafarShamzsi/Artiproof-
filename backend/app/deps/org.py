"""Organization dependencies.

The two gates used by the org member-management endpoints:

- ``require_org_member`` — returns the membership row if the current
  user belongs to the given org. 403 otherwise. Used by read-only
  endpoints (list members, view org details) that any org member
  should be able to call.

- ``require_org_admin`` — returns the membership row if the current
  user is an admin of the given org. 403 otherwise. Used by every
  destructive endpoint (invite, remove, role change, branding edit).

Both deps issue a 404 if the organization itself doesn't exist, so a
non-member can't probe org existence by watching the error code.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.utils.auth import get_current_user


async def lock_and_require_org_admin(*, db: AsyncSession, org_id: str, actor_user_id: str):
    """Serialize first, then reauthorize without reusing the early dependency.

    Membership writers use user (when needed) -> org -> invitation order.
    Do not lock the actor user after the org: acceptance/removal lock users
    first. The membership and account subquery are fresh READ COMMITTED reads.
    All organization role/removal writers hold the same org lock.
    Parent locks are NO KEY UPDATE (not UPDATE), so audit FK KEY SHARE does
    not wait on a creation/enrollment user that is waiting for this org.
    """
    from app.services.team_invites import lock_org

    org = await lock_org(db, org_id)
    active_actor = select(User.id).where(
        User.organization_id == org_id, User.deleted_at.is_(None), User.deactivated_at.is_(None),
    )
    member = (await db.execute(select(OrganizationMember).where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == actor_user_id,
        OrganizationMember.user_id.in_(active_actor),
    ).execution_options(populate_existing=True))).scalar_one_or_none()
    if member is None or member.role != "admin":
        raise HTTPException(status_code=403, detail="Org admin required")
    return org, member


async def require_creation_membership(db: AsyncSession, user: User) -> User:
    """Validate authoritative enrollment before assigning new resource scope.

    Never repair pointers or fall back to personal scope. Locks remain held
    until the resource transaction commits. Call again after any intermediate
    commit, e.g. each source-check bulk item.
    """
    from app.services.team_invites import lock_org, lock_user

    requested_org_id = user.organization_id
    fresh = await lock_user(db, user.id)
    if fresh is None or fresh.deleted_at is not None or fresh.deactivated_at is not None:
        raise HTTPException(status_code=403, detail="Account not active")
    if fresh.organization_id != requested_org_id:
        raise HTTPException(status_code=403, detail="Organization enrollment changed; retry the request")
    if fresh.organization_id is not None:
        await lock_org(db, fresh.organization_id)
    members = list((await db.execute(select(OrganizationMember).where(
        OrganizationMember.user_id == fresh.id,
    ).execution_options(populate_existing=True))).scalars().all())
    if fresh.organization_id is None and not members:
        fresh._org_role = None
        return fresh
    if (len(members) != 1 or members[0].organization_id != fresh.organization_id
            or members[0].role not in ("admin", "member")):
        raise HTTPException(status_code=403, detail="Active matching organization membership required")
    fresh._org_role = members[0].role
    return fresh


async def _load_membership(
    *, org_id: str, user: User, db: AsyncSession
) -> tuple[Organization, OrganizationMember | None]:
    """Common loader — returns (org, membership-or-None) so the two deps
    above can each apply their own predicate without re-querying."""
    org_q = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_q.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    mem_q = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
    )
    membership = mem_q.scalar_one_or_none()
    return org, membership


async def require_org_member(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Allow any member of the org through. 404 if org doesn't exist,
    403 if the user isn't a member."""
    _, membership = await _load_membership(
        org_id=org_id, user=current_user, db=db
    )
    if membership is None:
        raise HTTPException(
            status_code=403, detail="Not a member of this organization"
        )
    return membership


async def require_org_admin(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Only org admins through. Same 404/403 distinction as above."""
    _, membership = await _load_membership(
        org_id=org_id, user=current_user, db=db
    )
    if membership is None or membership.role != "admin":
        # Same status code for "not a member" and "not admin" so callers
        # can't enumerate role from the response.
        raise HTTPException(
            status_code=403, detail="Org admin required"
        )
    return membership
