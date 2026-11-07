"""user: tier, locale, notification_preferences, deactivated_at, deleted_at

Settings + dashboard expansion lands here. All new columns are NULLABLE or
have server defaults so existing rows pick up sane values without a backfill.

- tier: 'free' default; quotas defined in app.constants.TIER_LIMITS.
- notification_preferences: JSON, NULL means "use defaults" — see
  DEFAULT_NOTIFICATION_PREFERENCES; safer than hard-coding a JSON blob into
  the DB default.
- locale: ISO 639-1, default 'en'. Allowed set lives in app.constants.
- deactivated_at: account suspension; auth dep blocks all routes when set.
- deleted_at: SoftDeleteMixin column; cleanup task hard-deletes after the
  same grace window used for SourceCheck / ResearcherProfile / Report.

Revision ID: 0004_user_tier_locale
Revises: 0003_user_id_not_null
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_user_tier_locale"
down_revision = "0003_user_id_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
    )
    op.create_index("ix_users_tier", "users", ["tier"])

    op.add_column("users", sa.Column("notification_preferences", sa.JSON(), nullable=True))

    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="en"),
    )

    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deactivated_at", "users", ["deactivated_at"])

    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
    op.drop_index("ix_users_deactivated_at", table_name="users")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "locale")
    op.drop_column("users", "notification_preferences")
    op.drop_index("ix_users_tier", table_name="users")
    op.drop_column("users", "tier")
