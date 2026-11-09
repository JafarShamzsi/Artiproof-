"""Prompt-version governance gates.

The contract is simple:

1. Every engine's ``PROMPT_HASHES`` snapshot must equal the live
   hashes of its current prompt strings. If they diverge, a developer
   edited a prompt without bumping ``PROMPT_VERSION`` (and updating
   the snapshot) — that silently changes the score distribution and
   makes historical analyses incomparable to new ones.

2. ``ModelMetadata`` (the Pydantic governance schema) must accept what
   the orchestrators write. A typo in a field name would break audit
   replay weeks later; pinning the round-trip here catches it at PR.

3. ``build_model_metadata`` must populate the new prompt-version
   fields so the audit trail is consistent across both engines.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.governance.prompt_versioning import (
    assert_no_drift,
    check_prompt_drift,
    compute_prompt_hash,
    compute_prompt_hashes,
)
from app.schemas.governance import (
    AnalysisContext,
    ModelMetadata,
    build_model_metadata,
)


# ─── PROMPT_HASHES match live ──────────────────────────────────────────────


def test_source_verification_hashes_match_live():
    from app.services.source_verification import (
        PROMPT_HASHES,
        PROMPT_VERSION,
        compute_live_prompt_hashes,
    )

    assert PROMPT_VERSION  # must not be empty
    live = compute_live_prompt_hashes()
    # If this fails, a prompt was edited without bumping PROMPT_VERSION
    # + PROMPT_HASHES in app/services/source_verification/__init__.py.
    # The error message lists exactly which prompt drifted.
    assert_no_drift(("source_verification", PROMPT_HASHES, live))


def test_academic_integrity_hashes_match_live():
    from app.services.academic_integrity import (
        PROMPT_HASHES,
        PROMPT_VERSION,
        compute_live_prompt_hashes,
    )

    assert PROMPT_VERSION
    live = compute_live_prompt_hashes()
    assert_no_drift(("academic_integrity", PROMPT_HASHES, live))


# ─── Hash helper invariants ────────────────────────────────────────────────


def test_compute_prompt_hash_is_deterministic():
    assert compute_prompt_hash("hello") == compute_prompt_hash("hello")


def test_compute_prompt_hash_distinguishes_strings():
    assert compute_prompt_hash("hello") != compute_prompt_hash("world")


def test_compute_prompt_hash_normalises_trailing_whitespace():
    # An auto-formatter that touches trailing spaces shouldn't trigger
    # drift; canonical form strips per-line trailing whitespace.
    assert compute_prompt_hash("hello\nworld") == compute_prompt_hash("hello \nworld  ")


def test_compute_prompt_hash_preserves_leading_whitespace():
    # Leading whitespace can be load-bearing for structured prompts
    # (e.g. JSON examples), so a change there IS a meaningful edit.
    assert compute_prompt_hash("  hello") != compute_prompt_hash("hello")


def test_compute_prompt_hashes_returns_dict_with_same_keys():
    out = compute_prompt_hashes({"a": "x", "b": "y"})
    assert set(out) == {"a", "b"}
    assert all(len(v) == 64 for v in out.values())  # SHA-256 hex length


# ─── Drift detection ───────────────────────────────────────────────────────


def test_check_prompt_drift_no_drift():
    assert (
        check_prompt_drift(
            engine="test",
            expected={"a": "h1", "b": "h2"},
            live={"a": "h1", "b": "h2"},
        )
        is False
    )


def test_check_prompt_drift_value_change(caplog):
    with caplog.at_level("WARNING"):
        drifted = check_prompt_drift(
            engine="test",
            expected={"a": "h1"},
            live={"a": "DIFFERENT"},
        )
    assert drifted is True
    # The warning must surface the drift so Sentry picks it up.
    assert any("prompt drift" in rec.getMessage() for rec in caplog.records)


def test_check_prompt_drift_missing_key():
    # A new prompt landing without a hashes-snapshot update is drift too.
    assert (
        check_prompt_drift(
            engine="test",
            expected={"a": "h1"},
            live={"a": "h1", "new_prompt": "h2"},
        )
        is True
    )


# ─── ModelMetadata schema ──────────────────────────────────────────────────


def test_model_metadata_round_trips():
    payload = {
        "model_provider": "google",
        "model_name": "gemini-2.0-flash",
        "formula_version": "v1.0",
        "prompt_version": "2026-05-29.v1",
        "prompt_hashes": {"claim_extractor": "abc"},
        "prompt_drift_detected": False,
        "apis_used": ["gemini", "crossref"],
        "fallback_used": False,
        "processing_warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": {"text_length": 1234, "claims_extracted": 12},
    }
    m = ModelMetadata.model_validate(payload)
    assert m.prompt_version == "2026-05-29.v1"
    assert m.context.claims_extracted == 12


def test_model_metadata_accepts_legacy_blob_without_prompt_fields():
    # Old rows written before Phase B still validate — prompt fields
    # are Optional. This is what lets the migration land without
    # backfilling existing analyses.
    legacy = {
        "model_provider": "google",
        "model_name": "gemini-2.0-flash",
        "formula_version": "v1.0",
        "apis_used": ["gemini"],
        "fallback_used": False,
        "processing_warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    m = ModelMetadata.model_validate(legacy)
    assert m.prompt_version is None
    assert m.prompt_drift_detected is None


def test_build_model_metadata_populates_all_governance_fields():
    out = build_model_metadata(
        model_provider="google",
        model_name="gemini-2.0-flash",
        formula_version="v1.0",
        prompt_version="2026-05-29.v1",
        prompt_hashes={"claim_extractor": "abc"},
        prompt_drift_detected=False,
        apis_used=["gemini"],
        fallback_used=False,
        processing_warnings=[],
        context={"text_length": 100},
    )
    # The orchestrators write the returned dict straight into a JSON
    # column, so a missing required key would silently lose governance
    # data — pinning the shape here.
    for required in (
        "model_provider",
        "model_name",
        "formula_version",
        "prompt_version",
        "prompt_hashes",
        "prompt_drift_detected",
        "apis_used",
        "fallback_used",
        "processing_warnings",
        "timestamp",
        "context",
    ):
        assert required in out, f"missing {required}"
    assert out["prompt_hashes"] == {"claim_extractor": "abc"}
    assert out["context"]["text_length"] == 100


def test_build_model_metadata_records_drift_true():
    out = build_model_metadata(
        model_provider="google",
        model_name="gemini-2.0-flash",
        formula_version="v1.0",
        prompt_version="2026-05-29.v1",
        prompt_hashes={"claim_extractor": "abc"},
        prompt_drift_detected=True,
        apis_used=[],
        fallback_used=False,
        processing_warnings=[],
        context={},
    )
    assert out["prompt_drift_detected"] is True


def test_analysis_context_allows_extra_fields():
    # Engines can stash engine-specific extras without amending the
    # schema — opt-in via extra="allow".
    ctx = AnalysisContext(text_length=100, custom_metric=42)  # type: ignore[call-arg]
    assert ctx.model_dump()["custom_metric"] == 42
