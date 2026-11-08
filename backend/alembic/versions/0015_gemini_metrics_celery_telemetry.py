"""Phase E telemetry tables: gemini_metrics + celery_run_log + celery_dlq.

Three tables, all opt-in:

- ``gemini_metrics`` — one row per Gemini API call. Captures
  ``usage_metadata`` (input/output tokens) and end-to-end latency so an
  operator can see ``SELECT user_id, SUM(input_tokens + output_tokens)
  FROM gemini_metrics WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY user_id`` to identify cost outliers. The ``source_check_id`` /
  ``researcher_profile_id`` columns let us trace cost back to the
  pipeline that incurred it. Both nullable because some Gemini calls
  (e.g. the narrative_generator for report templates) aren't tied to
  either pipeline.

- ``celery_run_log`` — one row per task execution. Cheap continuous
  metric of "did this task succeed and how long did it take?". Distinct
  from Sentry which only records exceptions; this is for the
  succeeded-but-slow case.

- ``celery_dlq`` — failed tasks beyond their retry budget. The admin
  panel reads from this to give an operator a one-click retry path.
  ``args`` / ``kwargs`` are JSONB so the original payload can be re-run
  verbatim.

Revision ID: 0015_telemetry
Revises: 0014_billing
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0015_telemetry"
down_revision = "0014_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── gemini_metrics ─────────────────────────────────────────────────
    op.create_table(
        "gemini_metrics",
        sa.Column("id", sa.String(), primary_key=True),
        # Nullable: a few callers (admin tooling, smoke checks) won't
        # have a user attached. Most rows will.
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Engine that made the call: "claim_extractor",
        # "fact_checker", "ai_detector", "topic_analyzer",
        # "narrative_generator", "origin_tracer". Free-text so new
        # engines just appear without a schema migration.
        sa.Column("operation", sa.String(), nullable=False, index=True),
        sa.Column("model", sa.String(), nullable=False),
        # usage_metadata fields from google-genai. Nullable because the
        # SDK occasionally omits them on stream/error paths.
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        # End-to-end client-side latency (includes network).
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        # NULL on success. Recorded for failed calls so cost dashboards
        # can show "tokens-spent vs tokens-wasted" splits.
        sa.Column("error_class", sa.String(), nullable=True),
        # Pipeline linkage — both nullable. The orchestrator stashes
        # whichever pipeline it's currently running through a ContextVar
        # so the call site doesn't need to plumb the id through.
        sa.Column(
            "source_check_id",
            sa.String(),
            sa.ForeignKey("source_checks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "researcher_profile_id",
            sa.String(),
            sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            index=True,
        ),
    )
    # Composite for the "MTD cost per user" query.
    op.create_index(
        "ix_gemini_metrics_user_created",
        "gemini_metrics",
        ["user_id", "created_at"],
    )

    # ─── celery_run_log ─────────────────────────────────────────────────
    op.create_table(
        "celery_run_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_name", sa.String(), nullable=False, index=True),
        # The Celery task id (UUID assigned by the broker). Indexed
        # because the DLQ row references this; joins answer "what
        # happened in the log when this DLQ entry was created?".
        sa.Column("task_id", sa.String(), nullable=False, index=True),
        # "started" | "success" | "failed" | "retry"
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            index=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Populated on failure (status='failed' or 'retry'). Class name
        # only — full traceback goes to the DLQ row when retries run out.
        sa.Column("exception_class", sa.String(), nullable=True),
    )

    # ─── celery_dlq ─────────────────────────────────────────────────────
    op.create_table(
        "celery_dlq",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_name", sa.String(), nullable=False, index=True),
        sa.Column("task_id", sa.String(), nullable=False, index=True),
        sa.Column("args", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("kwargs", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("exception_class", sa.String(), nullable=False),
        sa.Column("exception_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            index=True,
        ),
        # When an operator clicks "retry" in the admin panel, we stamp
        # this column with the retry timestamp. Filtering by NULL gives
        # the active DLQ; non-NULL is the history.
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            index=True,
        ),
        sa.Column("resolved_by_user_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("celery_dlq")
    op.drop_table("celery_run_log")
    op.drop_index("ix_gemini_metrics_user_created", table_name="gemini_metrics")
    op.drop_table("gemini_metrics")
