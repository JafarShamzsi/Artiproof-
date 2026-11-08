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
