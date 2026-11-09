"""Pydantic schemas for org create / detail / settings / invites / audit.

Separate from ``schemas/org_member.py`` to keep the existing member
schemas stable — that module is imported by the routers + tests and we
don't want to grow it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─── Org create / detail / settings ───────────────────────────────────────


class OrgCreateRequest(BaseModel):
    """Body for ``POST /api/organizations``.

    Anyone authenticated can call this to start a self-serve Team trial.
    The route enforces that the user is not already in an org. ``slug``
    is optional; when omitted the route slugifies ``name``.
    """

    name: str = Field(..., min_length=2, max_length=80)
    slug: Optional[str] = Field(
        None,
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
        description="Optional URL-friendly slug. Lowercase, digits, hyphens.",
    )


class OrgSettingsUpdate(BaseModel):
    """Body for ``PATCH /api/organizations/{id}``.

    All fields optional — omitted fields are not changed. Empty string
    on a field that's currently set means "clear it" (only for
    contact_email; name is required so empty is rejected).
    """

    name: Optional[str] = Field(None, min_length=2, max_length=80)
    contact_email: Optional[EmailStr] = None


class OrgDetailResponse(BaseModel):
    """Full org detail. Returned from POST /organizations,
    GET /organizations/{id}, and PATCH /organizations/{id}.

    ``seat_used`` is computed live from organization_members so the
    client doesn't need a separate request. ``seat_remaining`` is a
    convenience derived from ``seat_limit - seat_used`` clamped at 0.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: Optional[str]
    contact_email: Optional[str]
    seat_limit: int
    seat_used: int
    seat_remaining: int
    is_trial: bool
    trial_ends_at: Optional[datetime]
    created_at: datetime
    # The current user's role in this org. Convenience for the UI so it
    # doesn't have to cross-reference the member list to decide what
    # actions to render.
    current_user_role: Literal["admin", "member"]


# ─── Invites ──────────────────────────────────────────────────────────────


class OrgInviteItem(BaseModel):
    """A row in the pending-invites list. ``status='pending'`` is the
    only one the listing endpoint surfaces today; accepted/revoked rows
    exist in the DB for the audit log but aren't shown in the live tab."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: Literal["admin", "member"]
    status: Literal["pending", "accepted", "revoked", "expired"]
    invited_by: Optional[str]
    created_at: datetime
    expires_at: datetime


class OrgInviteListResponse(BaseModel):
    items: list[OrgInviteItem]
    total: int


# ─── Audit log ────────────────────────────────────────────────────────────


class OrgAuditLogItem(BaseModel):
    """One audit-log row, denormalised for the UI.

    ``actor_email`` and ``target_email`` are filled by the route from
    the joined user records so the UI can render "X invited Y" without
    a second request. They're nullable because the linked user may have
    been deleted in the meantime.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    actor_user_id: Optional[str]
    actor_email: Optional[str]
    target_user_id: Optional[str]
    target_email: Optional[str]
    payload: dict
    created_at: datetime


class OrgAuditLogResponse(BaseModel):
    items: list[OrgAuditLogItem]
    total: int
    page: int
    page_size: int
