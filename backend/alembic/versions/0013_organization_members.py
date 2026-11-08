"""organization_members table + role enum + backfill

Migration 0012 added ``organization_id`` to owned resources so team
admins could eventually see their team's work. Phase C makes "team
admin" a real role:

- New ``organization_members`` table stores ``(organization_id,
  user_id, role)`` with PK on the pair so a user can have at most one
  membership per org.
- Backfill: every existing team-tier user with a non-null
  ``users.organization_id`` is seeded as a member. The single user with
  the smallest ``user.id`` (lexicographically) per organization is
  promoted to ``admin`` so the org never starts in a "no admin"
  state. The rest become ``member``.

Authoritative model after this migration: ``organization_members`` is
the source of truth for "is X in org Y" and "what is X's role in Y".
``users.organization_id`` is kept as a denormalised pointer to a user's
primary org (for quota lookups, display, JWT claims) and is updated in
sync from the route layer when memberships change.

Zero-downtime: the new table is independent of any existing read path,
so adding it doesn't block writers. The backfill is a single ``INSERT
... SELECT`` per org; safe for any size repo we ship with.

Revision ID: 0013_org_members
Revises: 0012_org_id_owned
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision = "0013_org_members"
down_revision = "0012_org_id_owned"
branch_labels = None
depends_on = None


_ROLE_ENUM_NAME = "org_member_role_enum"


def upgrade() -> None:
    # Postgres ENUM type — create_type=True (default) lets alembic ship
    # the CREATE TYPE for us. Downgrade drops the type after the column
    # so nothing references it.
    org_role = ENUM("admin", "member", name=_ROLE_ENUM_NAME, create_type=True)
    org_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organization_members",
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            ENUM("admin", "member", name=_ROLE_ENUM_NAME, create_type=False),
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # invited_by is nullable because backfilled rows have no inviter.
        # SET NULL on delete so removing the inviter doesn't cascade the
        # membership away — losing an inviter is purely cosmetic.
        sa.Column(
            "invited_by",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "user_id", name="pk_organization_members"
        ),
    )
    # Reverse-direction lookup ("which orgs is user X in?") — small
    # cardinality but the route layer touches it on every authenticated
    # admin-page load, so worth an explicit index.
    op.create_index(
        "ix_organization_members_user_id",
        "organization_members",
        ["user_id"],
    )

    # ─── Backfill ───────────────────────────────────────────────────
    # For every (org, user) where users.organization_id matches, insert
    # a membership row. Default role 'member' from the column default;
    # the next statement promotes one admin per org.
    op.execute(
        """
        INSERT INTO organization_members (organization_id, user_id, role)
        SELECT u.organization_id, u.id, 'member'
          FROM users AS u
         WHERE u.organization_id IS NOT NULL
           AND u.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )

    # Promote the lexicographically-smallest user.id per org to admin.
    # Deterministic without requiring any "created_by" column on
    # organizations (which we don't have at this point in the schema).
    # Once Phase D's billing flow lands, the paying customer should be
    # promoted by the route layer at subscription start instead of
    # relying on this fallback.
    op.execute(
        """
        WITH first_user_per_org AS (
            SELECT organization_id, MIN(user_id) AS admin_user_id
              FROM organization_members
             GROUP BY organization_id
        )
        UPDATE organization_members AS m
           SET role = 'admin'
          FROM first_user_per_org AS f
         WHERE m.organization_id = f.organization_id
           AND m.user_id = f.admin_user_id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_members_user_id",
        table_name="organization_members",
    )
    op.drop_table("organization_members")
    ENUM(name=_ROLE_ENUM_NAME, create_type=False).drop(
        op.get_bind(), checkfirst=True
    )
