"""report templates + annotations + schedules + org branding

Adds:
- reports.template (default 'full'): one of 'full' | 'executive_summary'
  | 'comparison' | 'institutional_audit'. Renderer dispatches on this.
- reports.annotations (JSON): list of {author_name, text, created_at}
  rendered at the top of the PDF before sharing.
- reports.source_check_ids / researcher_profile_ids (JSON): used by the
  comparison + institutional_audit templates which span multiple
  underlying records. Single-source/researcher reports keep the existing
  scalar FKs and leave these NULL.
- new report_schedules table for recurring report generation.
- organizations.logo_url + primary_color + secondary_color for white-
  label rendering. URL-based for now; file upload is a future phase.

Revision ID: 0009_report_templates
Revises: 0008_researcher_snapshots
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_report_templates"
down_revision = "0008_researcher_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- reports columns --------------------------------------------------
    op.add_column(
        "reports",
        sa.Column(
            "template", sa.String(), nullable=False, server_default="full"
        ),
    )
    op.add_column("reports", sa.Column("annotations", sa.JSON(), nullable=True))
    op.add_column("reports", sa.Column("source_check_ids", sa.JSON(), nullable=True))
    op.add_column("reports", sa.Column("researcher_profile_ids", sa.JSON(), nullable=True))

    # --- organizations branding ------------------------------------------
    op.add_column("organizations", sa.Column("logo_url", sa.String(), nullable=True))
    op.add_column(
        "organizations", sa.Column("primary_color", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "organizations",
        sa.Column("secondary_color", sa.String(length=16), nullable=True),
    )

    # --- report_schedules table ------------------------------------------
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("frequency", sa.String(), nullable=False),
        sa.Column(
            "template",
            sa.String(),
            nullable=False,
            server_default="executive_summary",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
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
    op.create_index("ix_report_schedules_user_id", "report_schedules", ["user_id"])
    op.create_index("ix_report_schedules_active", "report_schedules", ["active"])
    op.create_index(
        "ix_report_schedules_next_run_at", "report_schedules", ["next_run_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_report_schedules_next_run_at", table_name="report_schedules")
    op.drop_index("ix_report_schedules_active", table_name="report_schedules")
    op.drop_index("ix_report_schedules_user_id", table_name="report_schedules")
    op.drop_table("report_schedules")

    op.drop_column("organizations", "secondary_color")
    op.drop_column("organizations", "primary_color")
    op.drop_column("organizations", "logo_url")

    op.drop_column("reports", "researcher_profile_ids")
    op.drop_column("reports", "source_check_ids")
    op.drop_column("reports", "annotations")
    op.drop_column("reports", "template")
