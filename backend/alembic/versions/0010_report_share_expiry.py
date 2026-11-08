"""report share-token expiry

Adds:
- reports.share_expires_at (nullable timestamptz). Backfills existing rows
  with created_at + 90 days so every previously-issued share link gets an
  expiry going forward; new rows pick up the default at the application
  layer.

Revision ID: 0010_report_share_expiry
Revises: 0009_report_templates
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_report_share_expiry"
down_revision = "0009_report_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill — Postgres-specific interval syntax is fine, the project
    # ships on Postgres only (see config.DATABASE_URL).
    op.execute(
        "UPDATE reports "
        "SET share_expires_at = created_at + interval '90 days' "
        "WHERE share_expires_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("reports", "share_expires_at")
