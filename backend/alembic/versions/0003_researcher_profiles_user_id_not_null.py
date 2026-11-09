"""researcher_profiles.user_id NOT NULL

Every profile is owned by the user who triggered the analysis. There is no
"anonymous" creation path in the current code, so tighten the column. If
this migration finds orphan rows (user_id IS NULL), it raises rather than
silently picking a sentinel — those rows would be invisible to all owners
and need a manual decision.

Revision ID: 0003_user_id_not_null
Revises: 0002_phase3
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_id_not_null"
down_revision = "0002_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    orphan_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM researcher_profiles WHERE user_id IS NULL")
    ).scalar_one()
    if orphan_count:
        raise RuntimeError(
            f"Refusing to enforce NOT NULL: {orphan_count} researcher_profiles "
            "rows have NULL user_id. Resolve those manually before re-running."
        )

    op.alter_column(
        "researcher_profiles",
        "user_id",
        existing_type=sa.String(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "researcher_profiles",
        "user_id",
        existing_type=sa.String(),
        nullable=True,
    )
