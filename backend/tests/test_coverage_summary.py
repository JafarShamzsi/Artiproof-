"""Tests for the coverage-caveat summarizer.

`build_coverage` reads ``SourceCheck.model_metadata`` and produces a
user-facing list of caveats. The model_metadata shape is fixed by the
orchestrator (``app.services.source_verification.orchestrator``).
"""

from __future__ import annotations

from app.services.source_verification.coverage import build_coverage


def test_none_metadata_returns_none():
    assert build_coverage(None) is None
    assert build_coverage({}) is not None  # empty dict → empty summary, not None


def test_clean_analysis_produces_no_notes():
    metadata = {
        "context": {
            "text_length": 7420,
            "text_truncated": False,
            "claims_extracted": 8,
            "paragraphs_analyzed": 14,
        },
        "processing_warnings": [],
    }
    cov = build_coverage(metadata)
    assert cov is not None
    assert cov.notes == []
    assert cov.claims_analyzed == 8
    assert cov.paragraphs_analyzed == 14
    assert cov.text_chars_analyzed == 7420
    assert cov.text_chars_total == 7420


def test_text_truncation_surfaces_with_original_and_analyzed_length():
    metadata = {
        "context": {"text_length": 73000, "text_truncated": True},
        "processing_warnings": [
            {
                "type": "text_truncated",
                "module": "claim_extractor",
                "original_length": 73000,
                "analyzed_length": 15000,
            }
        ],
    }
    cov = build_coverage(metadata)
    assert cov is not None
    assert any(n.kind == "text_truncated" for n in cov.notes)
    note = next(n for n in cov.notes if n.kind == "text_truncated")
    assert "15,000" in note.headline
    assert "73,000" in note.headline
    assert cov.text_chars_total == 73000
    assert cov.text_chars_analyzed == 15000


def test_claims_capped_shows_kept_vs_extracted():
    metadata = {
        "processing_warnings": [
            {
                "type": "claims_capped",
                "module": "claim_extractor",
                "extracted": 47,
                "kept": 15,
            }
        ]
    }
    cov = build_coverage(metadata)
    note = next(n for n in cov.notes if n.kind == "claims_capped")
    assert "15" in note.headline
    assert "47" in note.headline
    assert cov.claims_extracted == 47
    assert cov.claims_analyzed == 15


def test_paragraphs_capped_uses_sample_language():
    metadata = {
        "processing_warnings": [
            {
                "type": "paragraphs_capped",
                "module": "ai_detector",
                "total": 53,
                "analyzed": 20,
            }
        ]
    }
    cov = build_coverage(metadata)
    note = next(n for n in cov.notes if n.kind == "paragraphs_capped")
    assert "20" in note.headline
    assert "53" in note.headline
    assert note.severity == "warning"
    assert cov.paragraphs_total == 53
    assert cov.paragraphs_analyzed == 20


def test_fallback_heuristic_is_warning():
    metadata = {
        "processing_warnings": [
            {"type": "fallback_heuristic", "module": "ai_detector"}
        ]
    }
    cov = build_coverage(metadata)
    note = next(n for n in cov.notes if n.kind == "fallback_heuristic")
    assert note.severity == "warning"
    assert "Ai Detector" in note.headline or "ai detector" in note.headline.lower()


def test_missing_gemini_key_explicitly_called_out():
    metadata = {
        "processing_warnings": [
            {"type": "missing_gemini_key", "module": "claim_extractor"}
        ]
    }
    cov = build_coverage(metadata)
    assert any(n.kind == "missing_gemini_key" for n in cov.notes)


def test_pipeline_step_errors_are_surfaced():
    metadata = {
        "processing_warnings": [
            {"type": "pdf_annotation_failed", "error": "ValueError"},
            {"type": "scraping_failed", "error": "TimeoutException"},
        ]
    }
    cov = build_coverage(metadata)
    kinds = {n.kind for n in cov.notes}
    assert "pdf_annotation_failed" in kinds
    assert "scraping_failed" in kinds


def test_unknown_warning_types_are_skipped_silently():
    """Forward-compat: a new warning kind from a future orchestrator
    shouldn't break the renderer."""
    metadata = {
        "processing_warnings": [
            {"type": "future_kind_we_dont_know_about", "data": "x"}
        ]
    }
    cov = build_coverage(metadata)
    assert cov.notes == []


def test_malformed_warnings_list_is_tolerated():
    """processing_warnings might be missing or non-list; don't crash."""
    cov = build_coverage({"processing_warnings": "not a list"})
    assert cov is not None
    assert cov.notes == []

    cov2 = build_coverage({"processing_warnings": [None, "string", 42]})
    assert cov2 is not None
    assert cov2.notes == []
