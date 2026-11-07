"""Tests for ``calculate_adjusted_metrics`` in
``app.services.academic_integrity.rating_adjuster``.

The function is pure and takes plain dicts, so no fixtures are needed.
"""

from __future__ import annotations

import pytest

from app.services.academic_integrity.rating_adjuster import (
    WEIGHT_RING_PER_CONFIDENCE,
    WEIGHT_SELF_CITE_ELEVATED,
    WEIGHT_SELF_CITE_FLAGGED,
    _calculate_h_index,
    calculate_adjusted_metrics,
)


def _publications(citation_counts: list[int]):
    """Build minimal publication dicts from a list of citation counts."""
    return [
        {"paper_id": f"p{i}", "title": f"Paper {i}", "citation_count": c}
        for i, c in enumerate(citation_counts)
    ]


def _empty_ring_data(**overrides):
    """Default ring_data dict for a clean researcher."""
    base = {
        "self_citation_rate": 0.0,
        "suspicious_pairs": [],
        "potential_rings": [],
        "flags": [],
        "citation_velocity_anomalies": [],
        "total_citations_checked": 0,
    }
    base.update(overrides)
    return base


class TestCleanResearcher:
    def test_no_flags_keeps_score_at_100(self):
        result = calculate_adjusted_metrics(
            publications=_publications([10, 8, 5, 3, 1]),
            ring_data=_empty_ring_data(),
            official_h_index=4,
            official_citation_count=27,
        )
        assert result["integrity_score"] == 100.0
        assert result["breakdown"]["adjustments"] == []
        assert result["adjusted_h_index"] == 4
        assert result["adjusted_citation_count"] == 27


class TestSelfCitationDeductions:
    def test_elevated_rate_smaller_deduction(self):
        """0.15 < rate < 0.25 → elevated tier (smaller deduction)."""
        result = calculate_adjusted_metrics(
            publications=_publications([10, 8]),
            ring_data=_empty_ring_data(self_citation_rate=0.20),
            official_h_index=2,
            official_citation_count=18,
        )
        assert result["integrity_score"] == pytest.approx(
            100 - WEIGHT_SELF_CITE_ELEVATED, rel=1e-3
        )
        reasons = [a["reason"] for a in result["breakdown"]["adjustments"]]
        assert "elevated_self_citation_rate" in reasons

    def test_flagged_rate_larger_deduction(self):
        """rate > 0.25 → flagged tier (larger deduction)."""
        result = calculate_adjusted_metrics(
            publications=_publications([10, 8]),
            ring_data=_empty_ring_data(self_citation_rate=0.30),
            official_h_index=2,
            official_citation_count=18,
        )
        assert result["integrity_score"] == pytest.approx(
            100 - WEIGHT_SELF_CITE_FLAGGED, rel=1e-3
        )
        reasons = [a["reason"] for a in result["breakdown"]["adjustments"]]
        assert "high_self_citation_rate" in reasons


class TestRingMembership:
    def test_ring_member_reduces_score_by_confidence(self):
        result = calculate_adjusted_metrics(
            publications=_publications([10]),
            ring_data=_empty_ring_data(
                potential_rings=[
                    {"members": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                     "total_mutual_citations": 30, "confidence": 0.8},
                ]
            ),
            official_h_index=1,
            official_citation_count=10,
        )
        # 100 - (WEIGHT_RING_PER_CONFIDENCE * 0.8)
        expected = 100 - (WEIGHT_RING_PER_CONFIDENCE * 0.8)
        assert result["integrity_score"] == pytest.approx(expected, rel=1e-3)
        reasons = [a["reason"] for a in result["breakdown"]["adjustments"]]
        assert "citation_ring_member" in reasons


class TestAdjustedHIndex:
    def test_adjusted_h_lower_when_self_citations_inflated(self):
        """Heavy self-cite → adjusted h-index drops below official."""
        result = calculate_adjusted_metrics(
            publications=_publications([20, 10, 5]),
            ring_data=_empty_ring_data(self_citation_rate=0.40),
            official_h_index=3,
            official_citation_count=35,
        )
        assert result["adjusted_h_index"] < 3
        assert result["adjusted_citation_count"] < 35

    def test_h_index_zero_when_no_papers(self):
        result = calculate_adjusted_metrics(
            publications=[],
            ring_data=_empty_ring_data(),
            official_h_index=None,
            official_citation_count=0,
        )
        assert result["adjusted_h_index"] == 0


class TestBreakdownShape:
    def test_breakdown_has_required_fields(self):
        result = calculate_adjusted_metrics(
            publications=_publications([5]),
            ring_data=_empty_ring_data(self_citation_rate=0.30),
            official_h_index=1,
            official_citation_count=5,
        )
        breakdown = result["breakdown"]
        assert breakdown["base"] == 100.0
        assert "adjustments" in breakdown
        assert "warnings" in breakdown
        assert "final" in breakdown
        assert "confidence" in breakdown
        assert "formula_version" in breakdown

    def test_each_adjustment_has_reason_and_impact(self):
        result = calculate_adjusted_metrics(
            publications=_publications([5]),
            ring_data=_empty_ring_data(self_citation_rate=0.30),
            official_h_index=1,
            official_citation_count=5,
        )
        for adj in result["breakdown"]["adjustments"]:
            assert "reason" in adj
            assert "impact" in adj
            assert isinstance(adj["impact"], (int, float))
            # All adjustments are deductions in this version of the formula
            assert adj["impact"] < 0


class TestHIndexCalculation:
    def test_h_index_basic(self):
        # 5 papers cited 5,4,3,2,1 → h-index 3
        h = _calculate_h_index([{"citation_count": c} for c in [5, 4, 3, 2, 1]])
        assert h == 3

    def test_h_index_zero_for_no_citations(self):
        h = _calculate_h_index([{"citation_count": 0} for _ in range(5)])
        assert h == 0

    def test_h_index_handles_empty_list(self):
        assert _calculate_h_index([]) == 0
