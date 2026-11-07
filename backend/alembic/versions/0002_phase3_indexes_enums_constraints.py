"""phase 3: status enums, indexes, check constraints, soft deletes, scoring transparency

Patterns used so this migration is safe to run with minimal downtime:
- All new columns are NULLABLE or have a server-side DEFAULT (no rewrites)
- ENUM conversions use USING clause; existing string values match the new enum values
- Indexes are added inside the migration. For very large prod tables, prefer
  running CREATE INDEX CONCURRENTLY out-of-band and then alembic stamp.
- CHECK constraints use the NOT VALID + VALIDATE pattern. Doing both steps in
  one migration (as we do here) gives no real downtime benefit because Alembic
  wraps the migration in a transaction; for large prod tables, split the
  VALIDATE into a separate follow-up migration. See backend/alembic/README.md.

Revision ID: 0002_phase3
Revises: 0001_baseline
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_phase3"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


CHECK_STATUS_VALUES = ("pending", "processing", "completed", "failed")
ANALYSIS_STATUS_VALUES = ("pending", "scraping", "processing", "analyzing", "completed", "failed")


def upgrade() -> None:
    # --- 1. New Postgres ENUM types -----------------------------------------
    check_status = postgresql.ENUM(*CHECK_STATUS_VALUES, name="check_status")
    check_status.create(op.get_bind(), checkfirst=True)

    analysis_status = postgresql.ENUM(*ANALYSIS_STATUS_VALUES, name="analysis_status")
    analysis_status.create(op.get_bind(), checkfirst=True)

    # --- 2. Convert string status columns to enums --------------------------
    # USING clause casts existing values; defaults are dropped and re-added
    # because Postgres won't reuse a string default for an enum column.
    op.execute("ALTER TABLE source_checks ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE source_checks ALTER COLUMN status TYPE check_status "
        "USING status::check_status"
    )
    op.execute("ALTER TABLE source_checks ALTER COLUMN status SET DEFAULT 'pending'")

    op.execute("ALTER TABLE researcher_profiles ALTER COLUMN analysis_status DROP DEFAULT")
    op.execute(
        "ALTER TABLE researcher_profiles ALTER COLUMN analysis_status TYPE analysis_status "
        "USING analysis_status::analysis_status"
    )
    op.execute(
        "ALTER TABLE researcher_profiles ALTER COLUMN analysis_status SET DEFAULT 'pending'"
    )

    op.execute("ALTER TABLE researcher_profiles ALTER COLUMN scrape_status DROP DEFAULT")
    op.execute(
        "ALTER TABLE researcher_profiles ALTER COLUMN scrape_status TYPE analysis_status "
        "USING scrape_status::analysis_status"
    )
    op.execute(
        "ALTER TABLE researcher_profiles ALTER COLUMN scrape_status SET DEFAULT 'pending'"
    )

    # --- 3. Indexes ---------------------------------------------------------
    # Rename the Prisma-generated composite to follow our naming convention.
    op.execute(
        "ALTER INDEX IF EXISTS source_checks_user_id_created_at_idx "
        "RENAME TO ix_source_checks_user_created"
    )
    op.create_index("ix_source_checks_user_id", "source_checks", ["user_id"])
    op.create_index("ix_source_checks_status", "source_checks", ["status"])
    op.create_index("ix_source_checks_user_status", "source_checks", ["user_id", "status"])

    op.execute(
        "ALTER INDEX IF EXISTS researcher_profiles_user_id_idx "
        "RENAME TO ix_researcher_profiles_user_id"
    )
    op.create_index(
        "ix_researcher_profiles_analysis_status", "researcher_profiles", ["analysis_status"]
    )
    op.create_index(
        "ix_researcher_profiles_scrape_status", "researcher_profiles", ["scrape_status"]
    )
    op.create_index(
        "ix_researcher_profiles_user_status",
        "researcher_profiles",
        ["user_id", "analysis_status"],
    )

    # Rename remaining Prisma-style indexes to the convention. Safe IF EXISTS
    # so this also runs on fresh DBs that already used the new names in 0001.
    op.execute(
        "ALTER INDEX IF EXISTS claim_analyses_source_check_id_idx "
        "RENAME TO ix_claim_analyses_source_check_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ai_detection_results_source_check_id_idx "
        "RENAME TO ix_ai_detection_results_source_check_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS citation_checks_source_check_id_idx "
        "RENAME TO ix_citation_checks_source_check_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS publication_analyses_researcher_profile_id_idx "
        "RENAME TO ix_publication_analyses_researcher_profile_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS scraped_publications_researcher_profile_id_idx "
        "RENAME TO ix_scraped_publications_researcher_profile_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS citation_edges_researcher_profile_id_idx "
        "RENAME TO ix_citation_edges_researcher_profile_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS citation_edges_cited_paper_id_idx "
        "RENAME TO ix_citation_edges_cited_paper_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS coauthor_relations_researcher_profile_id_idx "
        "RENAME TO ix_coauthor_relations_researcher_profile_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS reports_share_token_key RENAME TO ix_reports_share_token"
    )
    op.execute(
        "ALTER INDEX IF EXISTS reports_user_id_idx RENAME TO ix_reports_user_id"
    )
    op.execute("ALTER INDEX IF EXISTS users_email_key RENAME TO ix_users_email")

    # --- 4. CHECK constraints (NOT VALID + VALIDATE for low-lock pattern) ---
    _add_check_constraint(
        "source_checks", "ck_source_checks_credibility_score_range",
        "overall_credibility_score IS NULL OR "
        "(overall_credibility_score >= 0 AND overall_credibility_score <= 100)",
    )
    _add_check_constraint(
        "source_checks", "ck_source_checks_ai_content_percentage_range",
        "ai_content_percentage IS NULL OR "
        "(ai_content_percentage >= 0 AND ai_content_percentage <= 100)",
    )
    _add_check_constraint(
        "claim_analyses", "ck_claim_analyses_confidence_range",
        "confidence >= 0 AND confidence <= 1",
    )
    _add_check_constraint(
        "ai_detection_results", "ck_ai_detection_results_ai_probability_range",
        "ai_probability >= 0 AND ai_probability <= 1",
    )
    _add_check_constraint(
        "citation_checks", "ck_citation_checks_credibility_score_range",
        "credibility_score IS NULL OR (credibility_score >= 0 AND credibility_score <= 100)",
    )
    _add_check_constraint(
        "researcher_profiles", "ck_researcher_profiles_integrity_score_range",
        "integrity_score IS NULL OR (integrity_score >= 0 AND integrity_score <= 100)",
    )
    _add_check_constraint(
        "researcher_profiles", "ck_researcher_profiles_adjusted_h_index_non_negative",
        "adjusted_h_index IS NULL OR adjusted_h_index >= 0",
    )
    _add_check_constraint(
        "researcher_profiles", "ck_researcher_profiles_self_citation_rate_range",
        "self_citation_rate IS NULL OR (self_citation_rate >= 0 AND self_citation_rate <= 1)",
    )

    # --- 5. Soft-delete columns ---------------------------------------------
    for table in ("source_checks", "researcher_profiles", "reports"):
        op.add_column(
            table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])

    # --- 6. Scoring transparency / model governance JSON columns ------------
    op.add_column("source_checks", sa.Column("score_breakdown", sa.JSON(), nullable=True))
    op.add_column("source_checks", sa.Column("model_metadata", sa.JSON(), nullable=True))
    op.add_column(
        "researcher_profiles", sa.Column("integrity_breakdown", sa.JSON(), nullable=True)
    )
    op.add_column(
        "researcher_profiles", sa.Column("model_metadata", sa.JSON(), nullable=True)
    )

    # --- 7. updated_at columns where missing --------------------------------
    # Add as nullable with default now(), backfill from created_at, then set NOT NULL.
    tables_needing_updated_at = (
        "source_checks",
        "claim_analyses",
        "ai_detection_results",
        "citation_checks",
        "researcher_profiles",
        "publication_analyses",
        "scraped_publications",
        "citation_edges",
        "coauthor_relations",
        "reports",
    )
    for table in tables_needing_updated_at:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
        op.execute(f"UPDATE {table} SET updated_at = created_at WHERE updated_at IS NULL")
        op.alter_column(table, "updated_at", nullable=False)

    # users.updated_at exists but is nullable; backfill and lock it down too.
    op.execute("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column(
        "users",
        "updated_at",
        nullable=False,
        server_default=sa.func.now(),
        existing_type=sa.DateTime(timezone=True),
    )


def downgrade() -> None:
    # 7. updated_at
    for table in (
        "source_checks",
        "claim_analyses",
        "ai_detection_results",
        "citation_checks",
        "researcher_profiles",
        "publication_analyses",
        "scraped_publications",
        "citation_edges",
        "coauthor_relations",
        "reports",
    ):
        op.drop_column(table, "updated_at")
    op.alter_column("users", "updated_at", nullable=True)

    # 6. JSON columns
    op.drop_column("researcher_profiles", "model_metadata")
    op.drop_column("researcher_profiles", "integrity_breakdown")
    op.drop_column("source_checks", "model_metadata")
    op.drop_column("source_checks", "score_breakdown")

    # 5. Soft-delete columns
    for table in ("source_checks", "researcher_profiles", "reports"):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")

    # 4. CHECK constraints
    for table, name in (
        ("source_checks", "ck_source_checks_credibility_score_range"),
        ("source_checks", "ck_source_checks_ai_content_percentage_range"),
        ("claim_analyses", "ck_claim_analyses_confidence_range"),
        ("ai_detection_results", "ck_ai_detection_results_ai_probability_range"),
        ("citation_checks", "ck_citation_checks_credibility_score_range"),
        ("researcher_profiles", "ck_researcher_profiles_integrity_score_range"),
        ("researcher_profiles", "ck_researcher_profiles_adjusted_h_index_non_negative"),
        ("researcher_profiles", "ck_researcher_profiles_self_citation_rate_range"),
    ):
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')

    # 3. Index renames + new indexes
    op.drop_index("ix_researcher_profiles_user_status", table_name="researcher_profiles")
    op.drop_index("ix_researcher_profiles_scrape_status", table_name="researcher_profiles")
    op.drop_index("ix_researcher_profiles_analysis_status", table_name="researcher_profiles")
    op.drop_index("ix_source_checks_user_status", table_name="source_checks")
    op.drop_index("ix_source_checks_status", table_name="source_checks")
    op.drop_index("ix_source_checks_user_id", table_name="source_checks")
    op.execute(
        "ALTER INDEX IF EXISTS ix_source_checks_user_created "
        "RENAME TO source_checks_user_id_created_at_idx"
    )

    # 2. Revert enum columns to text
    for table, col in (
        ("source_checks", "status"),
        ("researcher_profiles", "analysis_status"),
        ("researcher_profiles", "scrape_status"),
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {col} TYPE varchar USING {col}::text"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT 'pending'")

    # 1. Drop enum types
    op.execute("DROP TYPE IF EXISTS analysis_status")
    op.execute("DROP TYPE IF EXISTS check_status")


def _add_check_constraint(table: str, name: str, expression: str) -> None:
    """Add a CHECK constraint with NOT VALID then VALIDATE.

    Splitting the operation lets future big-table migrations avoid blocking
    writers during the validation scan. On small tables it's a no-op
    optimization but keeps the pattern consistent across migrations.
    """
    op.execute(
        f'ALTER TABLE {table} ADD CONSTRAINT "{name}" CHECK ({expression}) NOT VALID'
    )
    op.execute(f'ALTER TABLE {table} VALIDATE CONSTRAINT "{name}"')
