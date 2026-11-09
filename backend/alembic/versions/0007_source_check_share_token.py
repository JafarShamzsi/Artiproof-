"""source_check.share_token

Adds a public share token to SourceCheck — distinct from Report.share_token.
The reports' share token gates a PDF download; this one gates the
read-only result page (`/check/shared/{token}` on the frontend).

Nullable + unique. Generated on demand from the route layer; revoking
just sets it back to NULL. The unique index lets us look up by token
in O(log n) without scanning.

Revision ID: 0007_check_share_token
Revises: 0006_organizations_pins
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_check_share_token"
down_revision = "0006_organizations_pins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_checks", sa.Column("share_token", sa.String(), nullable=True))
    op.create_index(
        "ix_source_checks_share_token",
        "source_checks",
        ["share_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_source_checks_share_token", table_name="source_checks")
    op.drop_column("source_checks", "share_token")
