"""Per-call Gemini usage row.

One row per ``generate_content`` invocation. Written by
``app.services.gemini.client.call_gemini`` — best-effort, never raises
into the caller. Read by the admin cost dashboard and the per-user MTD
cost tile in Settings.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.models.base import Base


class GeminiMetric(Base):
    __tablename__ = "gemini_metrics"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation = sa.Column(sa.String, nullable=False, index=True)
    model = sa.Column(sa.String, nullable=False)
    input_tokens = sa.Column(sa.Integer, nullable=True)
    output_tokens = sa.Column(sa.Integer, nullable=True)
    total_tokens = sa.Column(sa.Integer, nullable=True)
    latency_ms = sa.Column(sa.Integer, nullable=False)
    error_class = sa.Column(sa.String, nullable=True)
    source_check_id = sa.Column(
        sa.String,
        sa.ForeignKey("source_checks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    researcher_profile_id = sa.Column(
        sa.String,
        sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        index=True,
    )
