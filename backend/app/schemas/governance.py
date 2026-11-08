"""Per-analysis governance record schemas.

Every analysis (source check, researcher integrity) writes a
``model_metadata`` JSON blob to the database. The shape was loose
before — anything could end up in it — which made historical audits
("what model and prompt produced this score?") impossible.

This module pins the contract: ``ModelMetadata`` is the Pydantic v2
shape that orchestrators MUST conform to. New fields can land here
(opt-in via ``Optional``) but renames need a migration of existing
JSON blobs, so the contract reads conservatively.

The pieces:

- ``model_provider`` / ``model_name`` — which LLM produced the
  analysis. ``model_name`` is the version string at call time, e.g.
  ``"gemini-2.0-flash"``. Google updates that weights silently, which
  is acknowledged here in the docstring rather than papered over.
- ``formula_version`` — the scoring weight bundle used. Bumped when
  any of the ``WEIGHT_*`` constants change.
- ``prompt_version`` — the prompt bundle revision. Bumped when any
  prompt is edited (and ``PROMPT_HASHES`` is updated to match the new
  live hashes).
- ``prompt_hashes`` — live SHA-256 of each prompt as the analysis
  ran. Same shape as ``PROMPT_HASHES`` in the engine ``__init__.py``.
- ``prompt_drift_detected`` — True iff the live hashes diverged from
  the expected ``PROMPT_HASHES`` at analysis time. When True the
  orchestrator also fires a Sentry warning.
- ``apis_used`` / ``fallback_used`` / ``processing_warnings`` —
  inherited from the existing record shape.
- ``context`` — engine-specific extras (text length, claim count,
  thresholds applied). Treated as opaque by this schema.

Why two layers of hashes
------------------------
``PROMPT_HASHES`` is a hardcoded constant — the snapshot of every
prompt at the moment ``PROMPT_VERSION`` was bumped. ``prompt_hashes``
(stored per-analysis) is the live computation at that analysis's
runtime. Comparing the two detects "someone edited a prompt without
bumping the version" — a silent quality regression that's invisible
otherwise.

A unit test (``test_prompt_governance.py``) asserts the two match in
CI, so the drift can never reach prod unnoticed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisContext(BaseModel):
    """Engine-specific extras. Opaque to this schema — each orchestrator
    populates whichever fields make sense (text_length for source
    verification, publications_count for researcher integrity, etc).
    """

    model_config = ConfigDict(extra="allow")

    text_length: Optional[int] = None
    text_truncated: Optional[bool] = None
    claims_extracted: Optional[int] = None
    paragraphs_analyzed: Optional[int] = None
    detected_language: Optional[str] = None
    detected_language_name: Optional[str] = None
    language_reliable: Optional[bool] = None
    publications_count: Optional[int] = None
    citations_checked: Optional[int] = None
    field_used: Optional[str] = None
    thresholds_used: Optional[dict[str, Any]] = None


class ModelMetadata(BaseModel):
    """The contract every ``model_metadata`` JSON blob must satisfy.

    Used by orchestrators on write and by the (future) reproducibility
    UI on read. ``extra="allow"`` keeps old blobs forward-compatible —
    a row written before this schema landed deserialises fine and just
    skips the new fields.
    """

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model_provider: str
    model_name: str
    formula_version: str

    # New in Phase B — older rows have these as None / absent.
    prompt_version: Optional[str] = None
    prompt_hashes: Optional[dict[str, str]] = None
    prompt_drift_detected: Optional[bool] = None

    apis_used: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    processing_warnings: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str

    context: Optional[AnalysisContext] = None


def build_model_metadata(
    *,
    model_provider: str,
    model_name: str,
    formula_version: str,
    prompt_version: str,
    prompt_hashes: dict[str, str],
    prompt_drift_detected: bool,
    apis_used: list[str],
    fallback_used: bool,
    processing_warnings: list[dict[str, Any]],
    context: dict[str, Any],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build a validated ``model_metadata`` dict ready for the JSON column.

    Going through the Pydantic model first means a typo in a field name
    (or an orchestrator drifting from the contract) fails loudly at
    serialise time, not at audit time three months later when someone
    tries to reproduce a disputed score.
    """
    from datetime import timezone as _tz

    record = ModelMetadata(
        model_provider=model_provider,
        model_name=model_name,
        formula_version=formula_version,
        prompt_version=prompt_version,
        prompt_hashes=prompt_hashes,
        prompt_drift_detected=prompt_drift_detected,
        apis_used=list(apis_used),
        fallback_used=fallback_used,
        processing_warnings=list(processing_warnings),
        timestamp=(now or datetime.now(_tz.utc)).isoformat(),
        context=AnalysisContext(**context) if context else None,
    )
    # mode="json" because the column is JSON (datetime → iso string,
    # etc); the timestamp is already a string here but use the same
    # serialisation path so any future datetime field round-trips.
    return record.model_dump(mode="json", exclude_none=False)
