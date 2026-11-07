"""baseline schema (mirrors what Prisma db push created)

For existing databases that already have this schema (created via Prisma
db push or restored from data-dump.sql), run:

    alembic stamp 0001_baseline

so Alembic records this revision without re-running the DDL.

Fresh databases run `alembic upgrade head` and this migration creates
everything from scratch.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


# Existing DBs already have the UserRole type (Prisma created it). New DBs need it.
USER_ROLE_VALUES = ("researcher", "faculty", "admin")


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE "UserRole" AS ENUM ('researcher', 'faculty', 'admin');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    user_role = postgresql.ENUM(*USER_ROLE_VALUES, name="UserRole", create_type=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("institution", sa.String(), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="researcher"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("users_email_key", "users", ["email"], unique=True)

    op.create_table(
        "source_checks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("input_type", sa.String(), nullable=False),
        sa.Column("input_content", sa.Text(), nullable=False),
        sa.Column("input_title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("overall_credibility_score", sa.Float(), nullable=True),
        sa.Column("ai_content_percentage", sa.Float(), nullable=True),
        sa.Column("misinfo_claims_found", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("original_pdf_path", sa.String(), nullable=True),
        sa.Column("annotated_pdf_path", sa.String(), nullable=True),
        sa.Column("text_position_map", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("source_checks_user_id_created_at_idx", "source_checks", ["user_id", "created_at"])

    op.create_table(
        "claim_analyses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_check_id", sa.String(), sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("true_version", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("origin_trace", sa.JSON(), nullable=True),
        sa.Column("position_in_text", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("claim_analyses_source_check_id_idx", "claim_analyses", ["source_check_id"])

    op.create_table(
        "ai_detection_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_check_id", sa.String(), sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=False),
        sa.Column("paragraph_text", sa.Text(), nullable=False),
        sa.Column("ai_probability", sa.Float(), nullable=False),
        sa.Column("detection_method", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ai_detection_results_source_check_id_idx", "ai_detection_results", ["source_check_id"])

    op.create_table(
        "citation_checks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_check_id", sa.String(), sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_citation", sa.Text(), nullable=False),
        sa.Column("citation_url", sa.String(), nullable=True),
        sa.Column("is_accessible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_retracted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("credibility_score", sa.Float(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=True),
        sa.Column("suggested_alternative", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("citation_checks_source_check_id_idx", "citation_checks", ["source_check_id"])

    op.create_table(
        "researcher_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("researcher_name", sa.String(), nullable=False),
        sa.Column("scopus_id", sa.String(), nullable=True),
        sa.Column("google_scholar_id", sa.String(), nullable=True),
        sa.Column("google_scholar_url", sa.String(), nullable=True),
        sa.Column("orcid", sa.String(), nullable=True),
        sa.Column("semantic_scholar_id", sa.String(), nullable=True),
        sa.Column("institution", sa.String(), nullable=True),
        sa.Column("research_fields", sa.JSON(), nullable=True),
        sa.Column("total_publications", sa.Integer(), nullable=True),
        sa.Column("i10_index", sa.Integer(), nullable=True),
        sa.Column("official_h_index", sa.Integer(), nullable=True),
        sa.Column("official_citation_count", sa.Integer(), nullable=True),
        sa.Column("adjusted_h_index", sa.Integer(), nullable=True),
        sa.Column("adjusted_citation_count", sa.Integer(), nullable=True),
        sa.Column("integrity_score", sa.Float(), nullable=True),
        sa.Column("self_citation_rate", sa.Float(), nullable=True),
        sa.Column("citation_ring_flags", sa.JSON(), nullable=True),
        sa.Column("topic_relevance_score", sa.Float(), nullable=True),
        sa.Column("analysis_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("scrape_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("scrape_error", sa.Text(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("researcher_profiles_user_id_idx", "researcher_profiles", ["user_id"])

    op.create_table(
        "publication_analyses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("researcher_profile_id", sa.String(), sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("journal", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.String(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspicious_citations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topic_match_score", sa.Float(), nullable=True),
        sa.Column("is_self_cited_heavily", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("publication_analyses_researcher_profile_id_idx", "publication_analyses", ["researcher_profile_id"])

    op.create_table(
        "scraped_publications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("researcher_profile_id", sa.String(), sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("doi", sa.String(), nullable=True),
        sa.Column("semantic_scholar_id", sa.String(), nullable=True),
        sa.Column("google_scholar_cluster_id", sa.String(), nullable=True),
        sa.Column("scopus_eid", sa.String(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("journal_name", sa.String(), nullable=True),
        sa.Column("journal_issn", sa.String(), nullable=True),
        sa.Column("venue", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("publication_type", sa.String(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("influential_citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reference_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("authors_json", sa.JSON(), nullable=True),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("scraped_publications_researcher_profile_id_idx", "scraped_publications", ["researcher_profile_id"])

    op.create_table(
        "citation_edges",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("researcher_profile_id", sa.String(), sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cited_paper_id", sa.String(), sa.ForeignKey("scraped_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cited_paper_title", sa.String(), nullable=False),
        sa.Column("citing_paper_title", sa.String(), nullable=False),
        sa.Column("citing_paper_doi", sa.String(), nullable=True),
        sa.Column("citing_paper_semantic_id", sa.String(), nullable=True),
        sa.Column("citing_paper_year", sa.Integer(), nullable=True),
        sa.Column("citing_authors_json", sa.JSON(), nullable=True),
        sa.Column("is_self_citation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_coauthor_citation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_ring_suspected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("citation_edges_researcher_profile_id_idx", "citation_edges", ["researcher_profile_id"])
    op.create_index("citation_edges_cited_paper_id_idx", "citation_edges", ["cited_paper_id"])

    op.create_table(
        "coauthor_relations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("researcher_profile_id", sa.String(), sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coauthor_name", sa.String(), nullable=False),
        sa.Column("coauthor_semantic_id", sa.String(), nullable=True),
        sa.Column("coauthor_scopus_id", sa.String(), nullable=True),
        sa.Column("coauthor_institution", sa.String(), nullable=True),
        sa.Column("shared_publication_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shared_publication_ids", sa.JSON(), nullable=True),
        sa.Column("mutual_citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suspicion_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("coauthor_relations_researcher_profile_id_idx", "coauthor_relations", ["researcher_profile_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_check_id", sa.String(), sa.ForeignKey("source_checks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("researcher_profile_id", sa.String(), sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(), nullable=True),
        sa.Column("share_token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("reports_share_token_key", "reports", ["share_token"], unique=True)
    op.create_index("reports_user_id_idx", "reports", ["user_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("coauthor_relations")
    op.drop_table("citation_edges")
    op.drop_table("scraped_publications")
    op.drop_table("publication_analyses")
    op.drop_table("researcher_profiles")
    op.drop_table("citation_checks")
    op.drop_table("ai_detection_results")
    op.drop_table("claim_analyses")
    op.drop_table("source_checks")
    op.drop_table("users")
    op.execute('DROP TYPE IF EXISTS "UserRole"')
