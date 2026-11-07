import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.models.base import Base
from app.models.enums import CheckStatus
from app.models.mixins import SoftDeleteMixin, TimestampMixin

# Postgres enum types are created in migration 0002. The Python-side type
# uses create_type=False so SQLAlchemy never tries to create them implicitly
# (which would race with the migration on a fresh DB).
check_status_enum = PGEnum(
    CheckStatus,
    name="check_status",
    values_callable=lambda x: [e.value for e in x],
    create_type=False,
)


class SourceCheck(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "source_checks"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False, index=True)
    input_type = sa.Column(sa.String, nullable=False)  # url, text, document
    input_content = sa.Column(sa.Text, nullable=False)
    input_title = sa.Column(sa.String, nullable=True)
    status = sa.Column(check_status_enum, nullable=False, server_default=CheckStatus.pending.value, index=True)
    overall_credibility_score = sa.Column(sa.Float, nullable=True)
    ai_content_percentage = sa.Column(sa.Float, nullable=True)
    misinfo_claims_found = sa.Column(sa.Integer, nullable=True, server_default="0")
    original_pdf_path = sa.Column(sa.String, nullable=True)
    annotated_pdf_path = sa.Column(sa.String, nullable=True)
    text_position_map = sa.Column(sa.JSON, nullable=True)
    # Transparent scoring breakdown
    score_breakdown = sa.Column(sa.JSON, nullable=True)
    # Records the model/prompt/APIs used so analyses are reproducible
    model_metadata = sa.Column(sa.JSON, nullable=True)
    completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_source_checks_user_status", "user_id", "status"),
        sa.Index("ix_source_checks_user_created", "user_id", "created_at"),
        sa.CheckConstraint(
            "overall_credibility_score IS NULL OR (overall_credibility_score >= 0 AND overall_credibility_score <= 100)",
            name="credibility_score_range",
        ),
        sa.CheckConstraint(
            "ai_content_percentage IS NULL OR (ai_content_percentage >= 0 AND ai_content_percentage <= 100)",
            name="ai_content_percentage_range",
        ),
    )


class ClaimAnalysis(Base, TimestampMixin):
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

    __table_args__ = (
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )


class AIDetectionResult(Base, TimestampMixin):
    __tablename__ = "ai_detection_results"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_check_id = sa.Column(sa.String, sa.ForeignKey("source_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    paragraph_index = sa.Column(sa.Integer, nullable=False)
    paragraph_text = sa.Column(sa.Text, nullable=False)
    ai_probability = sa.Column(sa.Float, nullable=False)
    detection_method = sa.Column(sa.String, nullable=False)

    __table_args__ = (
        sa.CheckConstraint("ai_probability >= 0 AND ai_probability <= 1", name="ai_probability_range"),
    )


class CitationCheck(Base, TimestampMixin):
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

    __table_args__ = (
        sa.CheckConstraint(
            "credibility_score IS NULL OR (credibility_score >= 0 AND credibility_score <= 100)",
            name="credibility_score_range",
        ),
    )
