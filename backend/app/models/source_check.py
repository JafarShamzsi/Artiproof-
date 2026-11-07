import uuid

import sqlalchemy as sa
from app.models.base import Base


class SourceCheck(Base):
    __tablename__ = "source_checks"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False, index=True)
    input_type = sa.Column(sa.String, nullable=False)  # url, text, document
    input_content = sa.Column(sa.Text, nullable=False)
    input_title = sa.Column(sa.String, nullable=True)
    status = sa.Column(sa.String, nullable=False, server_default="pending")  # pending, processing, completed, failed
    overall_credibility_score = sa.Column(sa.Float, nullable=True)
    ai_content_percentage = sa.Column(sa.Float, nullable=True)
    misinfo_claims_found = sa.Column(sa.Integer, nullable=True, server_default="0")
    original_pdf_path = sa.Column(sa.String, nullable=True)
    annotated_pdf_path = sa.Column(sa.String, nullable=True)
    text_position_map = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


class ClaimAnalysis(Base):
    __tablename__ = "claim_analyses"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_check_id = sa.Column(sa.String, sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = sa.Column(sa.Text, nullable=False)
    verdict = sa.Column(sa.String, nullable=False)  # true, false, misleading, unverified, partially_true
    confidence = sa.Column(sa.Float, nullable=False)
    explanation = sa.Column(sa.Text, nullable=False)
    true_version = sa.Column(sa.Text, nullable=True)
    sources = sa.Column(sa.JSON, nullable=True)
    origin_trace = sa.Column(sa.JSON, nullable=True)
    position_in_text = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class AIDetectionResult(Base):
    __tablename__ = "ai_detection_results"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_check_id = sa.Column(sa.String, sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    paragraph_index = sa.Column(sa.Integer, nullable=False)
    paragraph_text = sa.Column(sa.Text, nullable=False)
    ai_probability = sa.Column(sa.Float, nullable=False)
    detection_method = sa.Column(sa.String, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())


class CitationCheck(Base):
    __tablename__ = "citation_checks"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_check_id = sa.Column(sa.String, sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    original_citation = sa.Column(sa.Text, nullable=False)
    citation_url = sa.Column(sa.String, nullable=True)
    is_accessible = sa.Column(sa.Boolean, nullable=False, server_default="true")
    is_retracted = sa.Column(sa.Boolean, nullable=False, server_default="false")
    credibility_score = sa.Column(sa.Float, nullable=True)
    issues = sa.Column(sa.JSON, nullable=True)
    suggested_alternative = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
