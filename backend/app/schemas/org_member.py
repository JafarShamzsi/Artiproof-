"""Pydantic schemas for the org member-management endpoints.

Lives in its own module so the existing ``schemas/report.py``
(which carries ``OrganizationBranding``) doesn't grow into a
universal org-schema dumping ground.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Roles match the org_member_role_enum in migration 0013.
OrgRole = Literal["admin", "member"]


class OrgMemberItem(BaseModel):
    """A single row in the member list — joined with the user record
    and supplemented with MTD usage so an org admin can see at a glance
    who is consuming quota.

    ``usage_mtd`` counts only LIVE rows (soft-deleted excluded) created
    in the current calendar month UTC. They're computed in the route
    via a single COUNT-per-table for simplicity; if the member list
    grows past a few hundred per org, denormalise these into a sweep.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    full_name: str
    role: OrgRole
    joined_at: datetime
    invited_by: Optional[str] = None
    source_checks_mtd: int = 0
    researcher_analyses_mtd: int = 0
    reports_mtd: int = 0


class OrgMemberListResponse(BaseModel):
    items: list[OrgMemberItem]
    total: int


class OrgMemberInvite(BaseModel):
    """Body for ``POST /organizations/{org_id}/members/invite``.

    Email is validated by Pydantic's EmailStr before the route runs.
    The role defaults to ``member``; org admins can promote later via
    the PATCH endpoint.
    """

    email: EmailStr
    role: OrgRole = "member"


class OrgMemberInviteResponse(BaseModel):
    """Same response for existing and new accounts; never attaches a user."""

    invited_email: EmailStr
    status: Literal["invited"]


class OrgInviteAccept(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class OrgMemberRoleUpdate(BaseModel):
    """Body for ``PATCH /organizations/{org_id}/members/{user_id}``.

    Only ``role`` is mutable today. The endpoint refuses to demote the
    last admin (mirror of the ``last_admin_guard`` pattern in the
    admin router).
    """

    role: OrgRole = Field(..., description="New role for the member")
