import uuid

import sqlalchemy as sa
from app.models.base import Base


class ResearcherProfile(Base):
    __tablename__ = "researcher_profiles"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=True, index=True)
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
    analysis_status = sa.Column(sa.String, nullable=False, server_default="pending")
    scrape_status = sa.Column(sa.String, nullable=False, server_default="pending")
    scrape_error = sa.Column(sa.Text, nullable=True)
    last_scraped_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    last_analyzed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class PublicationAnalysis(Base):
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
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class ScrapedPublication(Base):
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
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class CitationEdge(Base):
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
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class CoAuthorRelation(Base):
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
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
