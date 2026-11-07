"""Tests for ``detect_rings`` and threshold helpers in
``app.services.academic_integrity.ring_detector``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.academic_integrity.ring_detector import (
    FIELD_THRESHOLDS,
    detect_rings,
    get_thresholds,
)


def _graph(
    *,
    self_citations: int = 0,
    total_checked: int = 0,
    edges: list[dict] | None = None,
    citing_authors: dict | None = None,
):
    return {
        "self_citations": self_citations,
        "total_citations_checked": total_checked,
        "edges": edges or [],
        "citing_authors": citing_authors or {},
    }


class TestGetThresholds:
    def test_default_when_field_missing(self):
        assert get_thresholds(None) == FIELD_THRESHOLDS["default"]
        assert get_thresholds("") == FIELD_THRESHOLDS["default"]
        assert get_thresholds("not-a-real-field") == FIELD_THRESHOLDS["default"]

    def test_normalizes_field_name(self):
        """Spaces and dashes get normalized to match the dict keys."""
        assert get_thresholds("Computer Science") == FIELD_THRESHOLDS["computer_science"]
        assert get_thresholds("computer-science") == FIELD_THRESHOLDS["computer_science"]

    def test_medicine_stricter_than_cs(self):
        """Sanity: medicine should have a tighter self-cite ceiling than CS."""
        assert (
            FIELD_THRESHOLDS["medicine"]["self_cite_flag"]
            < FIELD_THRESHOLDS["computer_science"]["self_cite_flag"]
        )


class TestSelfCitationDetection:
    def test_normal_rate_no_flag(self):
        out = detect_rings(_graph(self_citations=5, total_checked=100), [])
        assert out["self_citation_status"] == "normal"
        assert out["flags"] == [] or all("self-citation" not in f.lower() for f in out["flags"])

    def test_warn_threshold_default(self):
        # default warn = 0.15
        out = detect_rings(_graph(self_citations=16, total_checked=100), [])
        assert out["self_citation_status"] == "elevated"

    def test_flag_threshold_default(self):
        # default flag = 0.25
        out = detect_rings(_graph(self_citations=30, total_checked=100), [])
        assert out["self_citation_status"] == "flagged"

    def test_medicine_field_tighter(self):
        """A 13% self-cite rate is normal in CS (warn=0.20) but elevated in
        medicine (warn=0.12). Demonstrates field-aware scoring without picking
        a rate that straddles both fields' flag thresholds simultaneously.
        """
        graph = _graph(self_citations=13, total_checked=100)
        cs = detect_rings(graph, [], field="computer_science")
        med = detect_rings(graph, [], field="medicine")
        assert cs["self_citation_status"] == "normal"
        assert med["self_citation_status"] == "elevated"

    def test_zero_total_does_not_divide_by_zero(self):
        out = detect_rings(_graph(self_citations=0, total_checked=0), [])
        assert out["self_citation_rate"] == 0.0
        assert out["self_citation_status"] == "normal"


class TestSuspiciousPairs:
    def test_threshold_boundary(self):
        """Default mutual_citation = 5: weight 4 should not flag, weight 5 should."""
        below = detect_rings(
            _graph(
                edges=[{"source": "a", "weight": 4}],
                citing_authors={"a": {"name": "Alice", "count": 4}},
            ),
            [],
        )
        at = detect_rings(
            _graph(
                edges=[{"source": "a", "weight": 5}],
                citing_authors={"a": {"name": "Alice", "count": 5}},
            ),
            [],
        )
        assert below["suspicious_pairs"] == []
        assert len(at["suspicious_pairs"]) == 1
        assert at["suspicious_pairs"][0]["author_id"] == "a"

    def test_suspicious_pair_includes_papers_cited(self):
        out = detect_rings(
            _graph(
                edges=[{"source": "a", "weight": 6, "papers": ["P1", "P2"]}],
                citing_authors={"a": {"name": "Alice", "count": 6}},
            ),
            [],
        )
        assert out["suspicious_pairs"][0]["papers_cited"] == ["P1", "P2"]


class TestPotentialRings:
    def test_three_frequent_citers_form_ring(self):
        """≥3 authors each citing target ≥3 times, total ≥10 → potential ring."""
        out = detect_rings(
            _graph(
                edges=[],
                citing_authors={
                    "a": {"name": "A", "count": 4},
                    "b": {"name": "B", "count": 4},
                    "c": {"name": "C", "count": 3},
                },
            ),
            [],
        )
        assert len(out["potential_rings"]) == 1
        ring = out["potential_rings"][0]
        assert len(ring["members"]) == 3
        assert ring["total_mutual_citations"] == 11
        assert 0 < ring["confidence"] <= 0.9

    def test_below_ring_size_no_ring(self):
        """Only 2 frequent citers → no ring even if counts are high."""
        out = detect_rings(
            _graph(
                citing_authors={
                    "a": {"name": "A", "count": 10},
                    "b": {"name": "B", "count": 10},
                },
            ),
            [],
        )
        assert out["potential_rings"] == []


class TestVelocityAnomalies:
    def test_dynamic_year_used(self):
        """A 2-year-old paper with 200 cites/year flags. Confirms current year is read."""
        current_year = datetime.now().year
        out = detect_rings(
            _graph(),
            publications=[
                {
                    "title": "Spike",
                    "year": current_year - 2,
                    "citation_count": 400,  # 200/yr
                }
            ],
        )
        assert len(out["citation_velocity_anomalies"]) == 1
        anomaly = out["citation_velocity_anomalies"][0]
        assert anomaly["year"] == current_year - 2
        assert anomaly["citations_per_year"] == 200.0

    def test_below_threshold_no_anomaly(self):
        current_year = datetime.now().year
        out = detect_rings(
            _graph(),
            publications=[
                # 49/yr — just below the 50/yr threshold
                {"title": "Modest", "year": current_year - 1, "citation_count": 49},
            ],
        )
        assert out["citation_velocity_anomalies"] == []

    def test_low_total_citations_not_flagged(self):
        """Even with high per-year ratio, low absolute counts shouldn't flag.

        80 cites over 1 year = 80/yr (above the 50/yr rate floor), but the
        total is below the 100-citation absolute floor — so no anomaly.
        """
        current_year = datetime.now().year
        out = detect_rings(
            _graph(),
            publications=[
                {"title": "Tiny", "year": current_year - 1, "citation_count": 80},
            ],
        )
        assert out["citation_velocity_anomalies"] == []


class TestReturnShape:
    def test_field_used_recorded(self):
        out = detect_rings(_graph(), [], field="medicine")
        assert out["field_used"] == "medicine"
        assert out["thresholds_used"]["self_cite_flag"] == 0.20

    def test_default_field_recorded_when_missing(self):
        out = detect_rings(_graph(), [])
        assert out["field_used"] == "default"
