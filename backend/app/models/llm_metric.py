"""Per-call LLM usage row.

One row per LLM completion across every provider (gemini / openai /
anthropic / …). Successor to ``GeminiMetric``; migration 0016 renames
the underlying table from ``gemini_metrics`` → ``llm_metrics`` and adds
a ``provider`` column with a back-compat default of ``"gemini"``.

The factory (``app.services.llm.factory.call_llm``) writes one row per
call, best-effort. Failures to write are logged at DEBUG and don't
propagate — telemetry must never abort an analysis pipeline.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.models.base import Base


class LLMMetric(Base):
    __tablename__ = "llm_metrics"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Which vendor served the call ("gemini" | "openai" | "anthropic").
    # New in migration 0016. Default "gemini" for historical rows that
    # predate the abstraction.
    provider = sa.Column(
        sa.String,
        nullable=False,
        server_default="gemini",
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


# Back-compat alias — some pre-migration code may still import
# ``GeminiMetric`` (it's exported from app.models). Re-export so the
# rename doesn't break those imports until they're migrated.
GeminiMetric = LLMMetric
