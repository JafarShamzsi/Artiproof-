"""Durable analysis queue, fenced execution and persisted progress.

Existing results remain untouched. Pending legacy resources without a run
must be explicitly rerun after draining old workers; GET/SSE never enqueue.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_analysis_runs"
down_revision = "0017_team_plan_v1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("owner_token", sa.String(64)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("dispatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prior_revision", sa.JSON()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('source_check', 'researcher')", name="kind_values"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name="status_values"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="attempt_bounds"),
    )
    op.create_index("ix_analysis_runs_dispatch", "analysis_runs", ["status", "next_dispatch_at"])
    op.create_index("ix_analysis_runs_lease", "analysis_runs", ["status", "lease_expires_at"])
    op.create_index("uq_analysis_runs_active_resource", "analysis_runs", ["kind", "resource_id"], unique=True,
                    postgresql_where=sa.text("status IN ('queued', 'running')"))
    op.create_table(
        "analysis_run_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_run_events_replay", "analysis_run_events", ["run_id", "id"])
    for table in ("source_checks", "researcher_profiles"):
        op.add_column(table, sa.Column("current_run_id", sa.String(), nullable=True))
        op.create_foreign_key(f"fk_{table}_current_run_id_analysis_runs", table, "analysis_runs",
                              ["current_run_id"], ["id"], ondelete="SET NULL")


def downgrade():
    for table in ("source_checks", "researcher_profiles"):
        op.drop_constraint(f"fk_{table}_current_run_id_analysis_runs", table, type_="foreignkey")
        op.drop_column(table, "current_run_id")
    op.drop_table("analysis_run_events")
    op.drop_table("analysis_runs")
