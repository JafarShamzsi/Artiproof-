"""Team plan v1: org seat/trial cols + persistent invites + org audit log.

Backs the new ``/team`` workspace and the public ``/pricing#team`` tier.
Three pieces, all additive — no destructive renames, no backfill writes
that change existing data:

1. ``organizations`` gains ``seat_limit``, ``is_trial``,
   ``trial_ends_at``, ``contact_email``. Every existing org is treated
   as a non-trial org with the default Team Starter cap of 10 seats and
   ``contact_email = NULL`` until an admin fills it in.

2. New ``organization_invites`` table — persists pending invites so the
   `/team` workspace can list, resend, and revoke them. The signed JWT
   that the email carries is independent (it's stateless), but the row
   is what the UI lists and what revoke needs to invalidate.

3. New ``organization_audit_logs`` table — first-class audit trail for
   every org-management action (invite_sent / invite_revoked /
   member_added / role_changed / member_removed / seat_limit_changed /
   org_settings_changed). Read from the ``/team`` Audit tab.

Revision ID: 0017_team_plan_v1
Revises: 0016_llm_metrics
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0017_team_plan_v1"
down_revision = "0016_llm_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── organizations: seat / trial / contact ─────────────────────────
    # `server_default="10"` so existing rows pick up the default without
    # the application having to backfill in a separate step. Subsequent
    # writes from the app layer pass an explicit value, and the column
    # remains NOT NULL.
    op.add_column(
        "organizations",
        sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "is_trial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("contact_email", sa.String(), nullable=True),
    )

    # ─── organization_invites: persistent pending-invite rows ─────────
    # Status enum is plain VARCHAR — only three states and the column is
    # only ever set by the app layer, so a Postgres ENUM type would be
    # overkill (and harder to extend if a fourth state lands later).
    op.create_table(
        "organization_invites",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(), nullable=False),
        # Mirrors org_member_role_enum but stored as VARCHAR to keep the
        # invite row writable without coupling it to the enum's mutation
        # surface (the enum is owned by organization_members).
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        # Signed JWT — long string. Stored so /resend can re-mail it and
        # /revoke can flip status to "revoked" (any subsequent signup
        # attempt with this email rejects against the row, not the token).
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "invited_by",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invites"),
    )
    # Two reads dominate: "list pending for org X" and "is there a live
    # pending invite for this email + org?". A composite covers both.
    op.create_index(
        "ix_organization_invites_org_status",
        "organization_invites",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_organization_invites_email_lower",
        "organization_invites",
        [sa.text("lower(email)")],
    )

    # ─── organization_audit_logs ──────────────────────────────────────
    op.create_table(
        "organization_audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # NULL when the actor was deleted; we keep the row so the org
        # admin still sees "<deleted user> revoked invite for X".
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column(
            "target_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Free-form context (email of invitee, old/new role, seat delta,
        # etc.) so the UI can render a human description without an extra
        # join. JSONB lets us GIN-index later if we ever need to filter.
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_audit_logs"),
    )
    op.create_index(
        "ix_organization_audit_logs_org_created",
        "organization_audit_logs",
        ["organization_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_audit_logs_org_created",
        table_name="organization_audit_logs",
    )
    op.drop_table("organization_audit_logs")
    op.drop_index(
        "ix_organization_invites_email_lower",
        table_name="organization_invites",
    )
    op.drop_index(
        "ix_organization_invites_org_status",
        table_name="organization_invites",
    )
    op.drop_table("organization_invites")
    op.drop_column("organizations", "contact_email")
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("organizations", "is_trial")
    op.drop_column("organizations", "seat_limit")
