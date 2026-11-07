import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.models.base import Base
from app.models.enums import AnalysisStatus
from app.models.mixins import SoftDeleteMixin, TimestampMixin

# Postgres enum types are created in migration 0002. See note in source_check.py.
analysis_status_enum = PGEnum(
    AnalysisStatus,
    name="analysis_status",
    values_callable=lambda x: [e.value for e in x],
    create_type=False,
)


class ResearcherProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "researcher_profiles"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Every profile is owned by the user who triggered the analysis. There is
    # no "anonymous" profile path today; if/when one is added, relax this and
    # update list/get filters to allow ``user_id IS NULL`` as well.
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False, index=True)
    researcher_name = sa.Column(sa.String, nullable=False)
    scopus_id = sa.Column(sa.String, nullable=True)
    google_scholar_id = sa.Column(sa.String, nullable=True)
    google_scholar_url = sa.Column(sa.String, nullable=True)
    orcid = sa.Column(sa.String, nullable=True)
    semantic_scholar_id = sa.Column(sa.String, nullable=True)
    institution = sa.Column(sa.String, nullable=True)
    research_fields = sa.Column(sa.JSON, nullable=True)
    total_publications = sa.Column(sa.Integer, nullable=True)
    i10_index = sa.Column(sa.Integer, nullable=True)
    official_h_index = sa.Column(sa.Integer, nullable=True)
    official_citation_count = sa.Column(sa.Integer, nullable=True)
    adjusted_h_index = sa.Column(sa.Integer, nullable=True)
    adjusted_citation_count = sa.Column(sa.Integer, nullable=True)
    integrity_score = sa.Column(sa.Float, nullable=True)
    self_citation_rate = sa.Column(sa.Float, nullable=True)
    citation_ring_flags = sa.Column(sa.JSON, nullable=True)
    topic_relevance_score = sa.Column(sa.Float, nullable=True)
    analysis_status = sa.Column(
        analysis_status_enum, nullable=False, server_default=AnalysisStatus.pending.value, index=True
    )
    scrape_status = sa.Column(
        analysis_status_enum, nullable=False, server_default=AnalysisStatus.pending.value, index=True
    )
    scrape_error = sa.Column(sa.Text, nullable=True)
    last_scraped_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    last_analyzed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    # Transparent integrity scoring breakdown
    integrity_breakdown = sa.Column(sa.JSON, nullable=True)
    model_metadata = sa.Column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.Index("ix_researcher_profiles_user_status", "user_id", "analysis_status"),
        sa.CheckConstraint(
            "integrity_score IS NULL OR (integrity_score >= 0 AND integrity_score <= 100)",
            name="integrity_score_range",
        ),
        sa.CheckConstraint(
            "adjusted_h_index IS NULL OR adjusted_h_index >= 0",
            name="adjusted_h_index_non_negative",
        ),
        sa.CheckConstraint(
            "self_citation_rate IS NULL OR (self_citation_rate >= 0 AND self_citation_rate <= 1)",
            name="self_citation_rate_range",
        ),
    )


class PublicationAnalysis(Base, TimestampMixin):
    __tablename__ = "publication_analyses"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    researcher_profile_id = sa.Column(sa.String, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = sa.Column(sa.String, nullable=False)
    journal = sa.Column(sa.String, nullable=True)
    year = sa.Column(sa.Integer, nullable=True)
    doi = sa.Column(sa.String, nullable=True)
    citation_count = sa.Column(sa.Integer, nullable=False, server_default="0")
    suspicious_citations = sa.Column(sa.Integer, nullable=False, server_default="0")
    topic_match_score = sa.Column(sa.Float, nullable=True)
    is_self_cited_heavily = sa.Column(sa.Boolean, nullable=False, server_default="false")
    flags = sa.Column(sa.JSON, nullable=True)


class ScrapedPublication(Base, TimestampMixin):
    __tablename__ = "scraped_publications"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    researcher_profile_id = sa.Column(sa.String, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = sa.Column(sa.String, nullable=False)
    doi = sa.Column(sa.String, nullable=True)
    semantic_scholar_id = sa.Column(sa.String, nullable=True)
    google_scholar_cluster_id = sa.Column(sa.String, nullable=True)
    scopus_eid = sa.Column(sa.String, nullable=True)
    abstract = sa.Column(sa.Text, nullable=True)
    journal_name = sa.Column(sa.String, nullable=True)
    journal_issn = sa.Column(sa.String, nullable=True)
    venue = sa.Column(sa.String, nullable=True)
    year = sa.Column(sa.Integer, nullable=True)
    publication_type = sa.Column(sa.String, nullable=True)
    citation_count = sa.Column(sa.Integer, server_default="0")
    influential_citation_count = sa.Column(sa.Integer, server_default="0")
    reference_count = sa.Column(sa.Integer, server_default="0")
    authors_json = sa.Column(sa.JSON, nullable=True)
    data_source = sa.Column(sa.String, nullable=False)
    raw_data = sa.Column(sa.JSON, nullable=True)
    scraped_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class CitationEdge(Base, TimestampMixin):
    __tablename__ = "citation_edges"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    researcher_profile_id = sa.Column(sa.String, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    cited_paper_id = sa.Column(sa.String, sa.ForeignKey("scraped_publications.id", ondelete="CASCADE"), nullable=False, index=True)
    cited_paper_title = sa.Column(sa.String, nullable=False)
    citing_paper_title = sa.Column(sa.String, nullable=False)
    citing_paper_doi = sa.Column(sa.String, nullable=True)
    citing_paper_semantic_id = sa.Column(sa.String, nullable=True)
    citing_paper_year = sa.Column(sa.Integer, nullable=True)
    citing_authors_json = sa.Column(sa.JSON, nullable=True)
    is_self_citation = sa.Column(sa.Boolean, server_default="false")
    is_coauthor_citation = sa.Column(sa.Boolean, server_default="false")
    is_ring_suspected = sa.Column(sa.Boolean, server_default="false")


class CoAuthorRelation(Base, TimestampMixin):
    __tablename__ = "coauthor_relations"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    researcher_profile_id = sa.Column(sa.String, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    coauthor_name = sa.Column(sa.String, nullable=False)
    coauthor_semantic_id = sa.Column(sa.String, nullable=True)
    coauthor_scopus_id = sa.Column(sa.String, nullable=True)
    coauthor_institution = sa.Column(sa.String, nullable=True)
    shared_publication_count = sa.Column(sa.Integer, server_default="0")
    shared_publication_ids = sa.Column(sa.JSON, nullable=True)
    mutual_citation_count = sa.Column(sa.Integer, server_default="0")
    suspicion_score = sa.Column(sa.Float, server_default="0.0")
