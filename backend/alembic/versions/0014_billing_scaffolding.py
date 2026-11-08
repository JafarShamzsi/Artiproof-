"""Payment-processor-agnostic billing scaffolding.

The user is bringing a payment processor (not Stripe) later. This
migration lays the schema so the future wire-up is a one-day job:

- ``users`` gains the columns the processor will write to via webhook
  (``subscription_state``, ``subscription_id``, ``next_billing_date``,
  ``last_billing_date``, ``billing_email``). All nullable / default
  values so existing rows don't need backfill.

- New ``billing_events`` table — every webhook callback lands as a row
  here, with ``(processor, processor_event_id)`` unique so a redelivered
  event can't double-charge or double-credit a user. The raw payload
  goes into a JSONB column for audit / replay.

- New ``tier_change_audits`` table — every mutation of ``user.tier``
  writes one row. Mandatory: admin tier changes, webhook-driven
  upgrades/downgrades, signup-intent capture. Each row carries the
  actor (admin or system), the reason code, and an optional
  ``billing_event_id`` linking back to what caused it. Reconciliation
  loop: SUM(billing_events) by user vs current tier — they must
  agree or the finance team has a question.

- New ``sales_leads`` table — Institution-tier inquiries from
  ``/contact-sales``. Separate from ``users`` because the lead might
  never become a customer.

Revision ID: 0014_billing
Revises: 0013_org_members
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB


revision = "0014_billing"
down_revision = "0013_org_members"
branch_labels = None
depends_on = None


_SUB_STATE_NAME = "subscription_state_enum"


def upgrade() -> None:
    # ─── subscription_state enum ────────────────────────────────────
    sub_state = ENUM(
        "none",
        "active",
        "past_due",
        "cancelled",
        "paused",
        name=_SUB_STATE_NAME,
        create_type=True,
    )
    sub_state.create(op.get_bind(), checkfirst=True)

    # ─── users: billing columns ─────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "subscription_state",
            ENUM(
                "none",
                "active",
                "past_due",
                "cancelled",
                "paused",
                name=_SUB_STATE_NAME,
                create_type=False,
            ),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "users",
        sa.Column("subscription_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_users_subscription_id", "users", ["subscription_id"]
    )
    op.add_column(
        "users",
        sa.Column("next_billing_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_billing_date", sa.DateTime(timezone=True), nullable=True),
    )
    # Separate from ``email`` (login) because billing receipts may go to
    # finance@institution.edu while the user logs in as alice@institution.edu.
    op.add_column("users", sa.Column("billing_email", sa.String(), nullable=True))

    # ─── billing_events ─────────────────────────────────────────────
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(), primary_key=True),
        # Nullable: the webhook may arrive before we've matched the
        # subscription_id to a user (rare but possible during signup
        # races). Matching happens in apply_tier_change.
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("processor", sa.String(), nullable=False),
        sa.Column("processor_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "processor",
            "processor_event_id",
            name="uq_billing_events_processor_event_id",
        ),
    )

    # ─── tier_change_audits ─────────────────────────────────────────
    op.create_table(
        "tier_change_audits",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_tier", sa.String(), nullable=True),
        sa.Column("to_tier", sa.String(), nullable=False),
        # Who triggered the change: another user (admin) or NULL for
        # system-initiated (webhook, signup intent).
        sa.Column(
            "changed_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            index=True,
        ),
        # Free-text reason code. Encouraged values: "admin_panel",
        # "billing_webhook", "signup_intent", "support_override".
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "billing_event_id",
            sa.String(),
            sa.ForeignKey("billing_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ─── sales_leads ────────────────────────────────────────────────
    op.create_table(
        "sales_leads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("institution", sa.String(), nullable=True),
        sa.Column("team_size", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        # Optional pointer to the User row if the inquirer was logged
        # in. Most inquiries come from cold visitors, so usually NULL.
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("sales_leads")
    op.drop_table("tier_change_audits")
    op.drop_table("billing_events")
    op.drop_column("users", "billing_email")
    op.drop_column("users", "last_billing_date")
    op.drop_column("users", "next_billing_date")
    op.drop_index("ix_users_subscription_id", table_name="users")
    op.drop_column("users", "subscription_id")
    op.drop_column("users", "subscription_state")
    ENUM(name=_SUB_STATE_NAME, create_type=False).drop(
        op.get_bind(), checkfirst=True
    )
