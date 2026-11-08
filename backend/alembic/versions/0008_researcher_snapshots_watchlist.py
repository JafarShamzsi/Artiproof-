"""researcher_snapshots + User.watchlist

Adds:
- researcher_snapshots table — captured by the orchestrator before
  re-analysis overwrites a profile. First analysis on a fresh profile
  creates no snapshot (nothing to preserve); every subsequent re-run
  freezes the previous values into a row here so users can track
  integrity changes over time.
- User.watchlist (JSON) — list of {researcher_id, added_at}. Capped
  at MAX_WATCHLIST in the route layer. The watchlist endpoint hydrates
  the entries with current metrics + delta vs latest snapshot.

Revision ID: 0008_researcher_snapshots
Revises: 0007_check_share_token
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_researcher_snapshots"
down_revision = "0007_check_share_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "researcher_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "researcher_profile_id",
            sa.String(),
            sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("official_h_index", sa.Integer(), nullable=True),
        sa.Column("official_citation_count", sa.Integer(), nullable=True),
        sa.Column("adjusted_h_index", sa.Integer(), nullable=True),
        sa.Column("adjusted_citation_count", sa.Integer(), nullable=True),
        sa.Column("integrity_score", sa.Float(), nullable=True),
        sa.Column("self_citation_rate", sa.Float(), nullable=True),
        sa.Column("topic_relevance_score", sa.Float(), nullable=True),
        sa.Column("total_publications", sa.Integer(), nullable=True),
        sa.Column("citation_ring_flags", sa.JSON(), nullable=True),
        sa.Column("integrity_breakdown", sa.JSON(), nullable=True),
        sa.Column("model_metadata", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(
        "ix_researcher_snapshots_profile_id",
        "researcher_snapshots",
        ["researcher_profile_id"],
    )

    op.add_column("users", sa.Column("watchlist", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "watchlist")
    op.drop_index(
        "ix_researcher_snapshots_profile_id", table_name="researcher_snapshots"
    )
    op.drop_table("researcher_snapshots")
