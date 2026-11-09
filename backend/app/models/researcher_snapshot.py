"""ResearcherSnapshot — frozen record of a researcher analysis at a point in time.

Captured by the academic-integrity orchestrator before _save_results
overwrites the live ResearcherProfile values during a re-analysis. The
first analysis on a fresh profile creates no snapshot (there's nothing
yet to preserve); every subsequent re-run captures the previous values.
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


class ResearcherSnapshot(Base, TimestampMixin):
    __tablename__ = "researcher_snapshots"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    researcher_profile_id = sa.Column(
        sa.String,
        sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Frozen scalar metrics at snapshot time
    official_h_index = sa.Column(sa.Integer, nullable=True)
    official_citation_count = sa.Column(sa.Integer, nullable=True)
    adjusted_h_index = sa.Column(sa.Integer, nullable=True)
    adjusted_citation_count = sa.Column(sa.Integer, nullable=True)
    integrity_score = sa.Column(sa.Float, nullable=True)
    self_citation_rate = sa.Column(sa.Float, nullable=True)
    topic_relevance_score = sa.Column(sa.Float, nullable=True)
    total_publications = sa.Column(sa.Integer, nullable=True)
    # JSON snapshots of the rich-shape fields
    citation_ring_flags = sa.Column(sa.JSON, nullable=True)
    integrity_breakdown = sa.Column(sa.JSON, nullable=True)
    model_metadata = sa.Column(sa.JSON, nullable=True)
    # captured_at is distinct from created_at (which is the row insert time)
    # so we can preserve the *original* completion timestamp of the analysis
    captured_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
