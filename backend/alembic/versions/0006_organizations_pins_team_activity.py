"""organizations + pinned_items + team activity sharing

User columns added:
- pinned_items (JSON): user-curated dashboard pins. Capped at
  MAX_PINNED_ITEMS by the route layer; no DB constraint because the
  shape is dynamic.
- organization_id: FK to organizations.id, ON DELETE SET NULL so
  deleting an org doesn't cascade-delete its members. NULL for free/pro
  accounts; required for tier='team' features at the route level.
- share_activity_with_team (bool, default true): privacy toggle for the
  team activity feed. Default-true so team members opt out actively
  rather than discover after the fact that they're invisible.

New table organizations:
- id (UUID), name, slug. Slug optional + unique for future URL routing.
- No row-level admin / member metadata yet — orgs are seeded out-of-band
  in this phase. A self-serve invite + admin UI is a separate epic.

All new columns nullable / default'd to keep this migration zero-downtime.

Revision ID: 0006_organizations_pins
Revises: 0005_security_sessions
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_organizations_pins"
down_revision = "0005_security_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- organizations table ----------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # --- User columns ------------------------------------------------------
    op.add_column("users", sa.Column("pinned_items", sa.JSON(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.add_column(
        "users",
        sa.Column(
            "share_activity_with_team",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "share_activity_with_team")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")
    op.drop_column("users", "pinned_items")
    op.drop_table("organizations")
