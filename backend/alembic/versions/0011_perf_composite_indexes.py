"""perf: composite indexes on hot read paths

Adds composite indexes for queries the audit flagged as scanning
unnecessary rows on a moderately-loaded DB:

- ``claim_analyses(source_check_id, created_at)`` — the report renderer
  sorts a check's claims by created_at; the existing single-column index
  on source_check_id forces an in-memory sort.
- ``publication_analyses(researcher_profile_id, year)`` — researcher
  reports filter by year window.
- ``reports(user_id, created_at)`` — list-reports endpoint orders by
  created_at after filtering by user_id.
- ``report_schedules(active, next_run_at)`` — the daily sweep query is
  ``WHERE active = TRUE AND next_run_at <= now()``; existing single
  indexes force a bitmap merge.

Revision ID: 0011_perf_indexes
Revises: 0010_report_share_expiry
Create Date: 2026-05-10
"""

from alembic import op


revision = "0011_perf_indexes"
down_revision = "0010_report_share_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_claim_analyses_source_check_id_created_at",
        "claim_analyses",
        ["source_check_id", "created_at"],
    )
    op.create_index(
        "ix_publication_analyses_profile_id_year",
        "publication_analyses",
        ["researcher_profile_id", "year"],
    )
    op.create_index(
        "ix_reports_user_id_created_at",
        "reports",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_report_schedules_active_next_run_at",
        "report_schedules",
        ["active", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_schedules_active_next_run_at",
        table_name="report_schedules",
    )
    op.drop_index(
        "ix_reports_user_id_created_at",
        table_name="reports",
    )
    op.drop_index(
        "ix_publication_analyses_profile_id_year",
        table_name="publication_analyses",
    )
    op.drop_index(
        "ix_claim_analyses_source_check_id_created_at",
        table_name="claim_analyses",
    )
