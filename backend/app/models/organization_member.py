"""Organization membership — the (org, user, role) relation.

Source of truth for "is X in org Y" and "what role does X have in Y".
``users.organization_id`` is kept in sync as a denormalised pointer to
the user's primary org (used by quota lookup, JWT claims, and report
branding) and updated by the route layer when memberships change.

Two roles only for now:

- ``admin`` — can invite + remove members, change branding, change
  other members' roles (subject to the last-admin guard). At least
  one admin must exist per org at all times.
- ``member`` — can read other members' org-scoped resources (per the
  ownership helper in ``app.utils.ownership``) but cannot manage the
  org. The default for invited users.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from app.models.base import Base

# `create_type=False` — the type was created in migration 0013. Same
# pattern as the UserRole enum in models/user.py for the Prisma-era
# UserRole type: SQLAlchemy must reference the existing Postgres type,
# not try to re-create it on every connect.
org_member_role_enum = ENUM(
    "admin", "member", name="org_member_role_enum", create_type=False
)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    organization_id = sa.Column(
        sa.String,
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role = sa.Column(
        org_member_role_enum, nullable=False, server_default="member"
    )
    joined_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    # Inviter. NULL for backfilled rows (no inviter knowable from the
    # pre-Phase-C state) and for the auto-promoted seed admin.
    invited_by = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
