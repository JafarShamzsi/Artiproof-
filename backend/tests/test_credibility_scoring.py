"""Tests for the credibility-score formula in
``app.services.source_verification.orchestrator``.

The orchestrator's ``_calculate_credibility`` and ``_calculate_confidence``
methods don't touch the database, so we instantiate the orchestrator with
``db=None`` and call them directly. Weights are imported from the module so
this file stays in sync if the formula gets retuned (and FORMULA_VERSION is
bumped — see app/schemas/breakdown.py).
"""

from __future__ import annotations

import pytest

from app.services.source_verification import orchestrator as svo
from app.services.source_verification.orchestrator import (
    SourceVerificationOrchestrator,
    WEIGHT_FALSE_CLAIM,
    WEIGHT_MISLEADING,
    WEIGHT_RETRACTED_CITATION,
)


def _orch():
    return SourceVerificationOrchestrator(db=None)  # type: ignore[arg-type]


class TestCredibilityScoring:
    def test_perfect_score_no_issues(self):
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[
                {"claim_text": "x", "verdict": "true", "confidence": 0.9},
            ],
            ai_percentage=10.0,
            citation_results=[{"is_accessible": True, "is_retracted": False}],
        )
        assert score == 100.0
        assert breakdown["base"] == 100.0
        assert breakdown["deductions"] == []
        assert breakdown["final"] == 100.0
        assert breakdown["formula_version"]  # any non-empty string

    def test_false_claim_reduces_score(self):
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[
                {"claim_text": "lie", "verdict": "false", "confidence": 1.0},
            ],
            ai_percentage=0,
            citation_results=[],
        )
        assert score == pytest.approx(100 - WEIGHT_FALSE_CLAIM, rel=1e-3)
        deductions = [d["reason"] for d in breakdown["deductions"]]
        assert "false_claim" in deductions

    def test_misleading_weighted_lower_than_false(self):
        """Sanity: misleading should hurt the score less than false."""
        orch = _orch()
        false_score, _ = orch._calculate_credibility(
            [{"claim_text": "x", "verdict": "false", "confidence": 1.0}], 0, []
        )
        mislead_score, _ = orch._calculate_credibility(
            [{"claim_text": "x", "verdict": "misleading", "confidence": 1.0}], 0, []
        )
        assert mislead_score > false_score
        assert WEIGHT_MISLEADING < WEIGHT_FALSE_CLAIM  # guards the assumption

    def test_retracted_citation_reduces_score(self):
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[{"verdict": "true", "confidence": 1.0}],
            ai_percentage=0,
            citation_results=[{"is_accessible": True, "is_retracted": True}],
        )
        assert score == pytest.approx(100 - WEIGHT_RETRACTED_CITATION)
        assert any(d["reason"] == "retracted_citations" for d in breakdown["deductions"])

    def test_inaccessible_citation_is_not_a_factual_deduction(self):
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[{"verdict": "true", "confidence": 1.0}],
            ai_percentage=0,
            citation_results=[
                {"is_accessible": False, "is_retracted": False},
                {"is_accessible": False, "is_retracted": False},
            ],
        )
        assert score == 100
        assert breakdown["deductions"] == []

    def test_ai_style_is_separate_from_factual_score(self):
        orch = _orch()
        evidence = [{"verdict": "true", "confidence": 1.0}]
        below, _ = orch._calculate_credibility(evidence, ai_percentage=49.9, citation_results=[])
        assert below == 100.0

        at_70, breakdown = orch._calculate_credibility(
            evidence, ai_percentage=70.0, citation_results=[]
        )
        assert at_70 == below
        assert breakdown["deductions"] == []

    def test_unverified_claims_are_unknown_not_false(self):
        score, breakdown = _orch()._calculate_credibility([
            {"verdict": "true", "confidence": 0.9},
            {"verdict": "unverified", "confidence": 0.9},
        ], 100, [{"is_accessible": False}])
        assert score == 100
        assert breakdown["assessment_status"] == "partial"
        assert breakdown["deductions"] == []

    def test_truncation_cannot_raise_a_low_evidence_indicator(self):
        orch = _orch()
        claims = [{"verdict": "true"}] + [{"verdict": "unverified"}] * 3
        baseline = orch._calculate_confidence(claims, [])
        orch._text_was_truncated = True
        assert orch._calculate_confidence(claims, []) < baseline

    def test_score_clamped_to_zero(self):
        """Catastrophic input shouldn't produce a negative score."""
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[
                {"claim_text": str(i), "verdict": "false", "confidence": 1.0}
                for i in range(20)
            ],
            ai_percentage=100.0,
            citation_results=[
                {"is_accessible": False, "is_retracted": True} for _ in range(10)
            ],
        )
        assert score == 0.0
        assert breakdown["final"] == 0.0

    def test_score_clamped_to_100(self):
        """Cleanest possible input still produces 100, never above."""
        orch = _orch()
        score, _ = orch._calculate_credibility([{"verdict": "true", "confidence": 1.0}], 0.0, [])
        assert score == 100.0

    def test_breakdown_deductions_sum_to_final(self):
        """Sum of (base + deductions) should equal final, modulo rounding."""
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            fact_check_results=[
                {"claim_text": "a", "verdict": "false", "confidence": 0.8},
                {"claim_text": "b", "verdict": "misleading", "confidence": 0.6},
            ],
            ai_percentage=60.0,
            citation_results=[{"is_accessible": False, "is_retracted": False}],
        )
        total = breakdown["base"] + sum(d["impact"] for d in breakdown["deductions"])
        # Allow 0.2 wiggle for the rounding the formula does internally
        assert abs(total - breakdown["final"]) < 0.2
        assert breakdown["final"] == score

    def test_unknown_verdict_is_ignored(self):
        """A verdict label not in the weight table should not crash or deduct."""
        orch = _orch()
        score, breakdown = orch._calculate_credibility(
            [{"claim_text": "x", "verdict": "what_even_is_this", "confidence": 1.0}],
            0,
            [],
        )
        assert score is None
        assert breakdown["final"] is None
        assert breakdown["confidence"] == 0

    @pytest.mark.parametrize("claims", [[], [{"verdict": "unverified", "confidence": 0.3}]])
    def test_missing_claim_evidence_withholds_headline(self, claims):
        score, breakdown = _orch()._calculate_credibility(
            claims, 0.0, [{"is_accessible": True, "is_retracted": False}],
        )
        assert score is None
        assert breakdown["assessment_status"] == "unavailable"
        assert breakdown["confidence"] == 0

    @pytest.mark.parametrize("warning", [
        "claim_extraction_failed", "parallel_analysis_failed", "citation_analysis_failed",
        "missing_gemini_key", "scraping_failed", "pdf_extraction_failed",
    ])
    def test_required_failure_withholds_score_despite_other_findings(self, warning):
        orch = _orch()
        orch._warnings = [{"type": warning}]
        score, breakdown = orch._calculate_credibility(
            [{"verdict": "true", "confidence": 0.9}], 0, [],
        )
        assert score is None
        assert warning in breakdown["warnings"]


class TestConfidenceCalculation:
    def test_full_coverage_high_confidence(self):
        """All claims verified + all citations accessible → confidence 1.0."""
        orch = _orch()
        c = orch._calculate_confidence(
            fact_check_results=[
                {"verdict": "true"},
                {"verdict": "false"},
                {"verdict": "misleading"},
            ],
            citation_results=[
                {"is_accessible": True},
                {"is_accessible": True},
            ],
        )
        assert c == 1.0

    def test_unverified_claims_lower_confidence(self):
        """Half the claims unverified → confidence ~0.5 from that factor."""
        orch = _orch()
        c = orch._calculate_confidence(
            fact_check_results=[
                {"verdict": "true"},
                {"verdict": "unverified"},
                {"verdict": "unverified"},
                {"verdict": "unverified"},
            ],
            citation_results=[],
        )
        # 1/4 verified → factor 0.25, average with no other factors = 0.25
        assert c == pytest.approx(0.25, abs=0.01)

    def test_truncation_lowers_confidence(self):
        """Setting _text_was_truncated should pull confidence down."""
        orch = _orch()
        baseline = orch._calculate_confidence(
            [{"verdict": "true"}], [{"is_accessible": True}]
        )
        orch._text_was_truncated = True
        truncated = orch._calculate_confidence(
            [{"verdict": "true"}], [{"is_accessible": True}]
        )
        assert truncated < baseline

    def test_ai_fallback_does_not_change_factual_evidence_indicator(self):
        orch = _orch()
        baseline = orch._calculate_confidence(
            [{"verdict": "true"}], [{"is_accessible": True}]
        )
        orch._fallback_used = True
        fallback = orch._calculate_confidence(
            [{"verdict": "true"}], [{"is_accessible": True}]
        )
        assert fallback == baseline

    def test_no_data_has_zero_confidence(self):
        """No evidence cannot support confidence, even with fallback flags."""
        orch = _orch()
        orch._fallback_used = True
        assert orch._calculate_confidence([], []) == 0.0


def test_formula_version_constant_stable():
    """Catch accidental edits to FORMULA_VERSION without a corresponding bump.

    If you intentionally retune the formula, update both the constant in
    app/schemas/breakdown.py and this test in the same commit.
    """
    assert svo.FORMULA_VERSION == "1.2"
