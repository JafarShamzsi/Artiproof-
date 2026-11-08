"""Heuristic citation metrics for a checked sample, with explicit abstention.

Incoming citation concentration cannot establish a ring or justify removing
citations. Adjusted metrics extrapolate the sampled self-citation rate and
are estimates; they are not a paper-by-paper recomputation or misconduct finding.
"""

import math

from app.constants import CREDIBILITY_SCORE_MAX, CREDIBILITY_SCORE_MIN
from app.schemas.breakdown import RESEARCHER_FORMULA_VERSION as FORMULA_VERSION

WEIGHT_SELF_CITE_FLAGGED = 25.0
WEIGHT_SELF_CITE_ELEVATED = 10.0
WEIGHT_VELOCITY_PER_ANOMALY = 3.0
WEIGHT_VELOCITY_MAX = 10.0
WEIGHT_TOPIC_RELEVANCE_GAP = 20.0


def unavailable_adjustment(reason: str, warnings: list[str] | None = None) -> dict:
    """Keep missing evidence distinct from zero, official metrics or clearance."""
    return {
        "adjusted_h_index": None, "adjusted_citation_count": None,
        "integrity_score": None, "self_citation_rate": None,
        "topic_relevance_score": None, "explanation": reason,
        "breakdown": {
            "base": 100.0, "adjustments": [], "final": None,
            "confidence": 0.0, "formula_version": FORMULA_VERSION,
            "assessment_status": "unavailable",
            "explanation": reason,
            "warnings": list(dict.fromkeys([*(warnings or []), "insufficient_citation_evidence"])),
        },
    }


def calculate_adjusted_metrics(
    publications: list[dict], ring_data: dict,
    official_h_index: int | None, official_citation_count: int | None,
    *, processing_warnings: list[dict] | None = None,
) -> dict:
    """Score only a successfully checked citation sample; preserve unknowns."""
    warning_types = [w.get("type", "") for w in (processing_warnings or [])]
    required_failures = {
        "resolve_failed", "publications_fetch_failed", "citation_graph_failed",
        "ring_detection_failed", "topic_analysis_failed", "topic_analysis_unavailable", "rating_adjustment_failed",
    }
    self_citation_rate = ring_data.get("self_citation_rate")
    if (
        not publications
        or ring_data.get("citation_evidence_status") != "succeeded"
        or ring_data.get("total_citations_checked", 0) <= 0
        or not isinstance(self_citation_rate, (int, float))
        or not math.isfinite(self_citation_rate)
        or not 0 <= self_citation_rate <= 1
        or required_failures.intersection(warning_types)
    ):
        return unavailable_adjustment(
            "Citation assessment unavailable: the checked sample is missing or incomplete, "
            "or a required analysis step failed. Available publications do not establish integrity.",
            warning_types,
        )

    if official_citation_count is not None and official_citation_count < ring_data["total_citations_checked"]:
        return unavailable_adjustment(
            "The official citation count conflicts with the observed citation sample; adjusted metrics are unavailable.",
            [*warning_types, "official_metrics_conflict"],
        )

    total_official = (official_citation_count if official_citation_count is not None
                      else sum(p.get("citation_count", 0) for p in publications))
    h_index = official_h_index if official_h_index is not None else _calculate_h_index(publications)
    self_cite_deduction = int(total_official * self_citation_rate)
    adjusted_citations = max(0, total_official - self_cite_deduction)
    adjusted_h = max(0, int(h_index * adjusted_citations / total_official)) if total_official > 0 else h_index

    topic_scores = [p["topic_match_score"] for p in publications if p.get("topic_match_score") is not None]
    avg_topic = sum(topic_scores) / len(topic_scores) if topic_scores else None
    integrity = 100.0
    adjustments = []
    if self_citation_rate > 0.25:
        weight, reason, threshold = WEIGHT_SELF_CITE_FLAGGED, "high_self_citation_rate", 0.25
    elif self_citation_rate > 0.15:
        weight, reason, threshold = WEIGHT_SELF_CITE_ELEVATED, "elevated_self_citation_rate", 0.15
    else:
        weight = 0
    if weight:
        integrity -= weight
        adjustments.append({"reason": reason, "impact": -weight,
                            "detail": {"rate": round(self_citation_rate, 4), "threshold": threshold}})

    # Neither frequent citers nor legacy ring candidates affect ratings or
    # adjusted citation counts. No directed evidence establishes those rings.
    if ring_data.get("potential_rings") or ring_data.get("suspicious_pairs"):
        warning_types.append("unsupported_ring_assessment_ignored")

    if avg_topic is not None and avg_topic < 0.5:
        impact = -round((0.5 - avg_topic) * WEIGHT_TOPIC_RELEVANCE_GAP, 2)
        integrity += impact
        adjustments.append({"reason": "low_topic_relevance", "impact": impact,
                            "detail": {"average": round(avg_topic, 3), "threshold": 0.5}})
    anomalies = ring_data.get("citation_velocity_anomalies", [])
    if anomalies:
        impact = -min(WEIGHT_VELOCITY_MAX, len(anomalies) * WEIGHT_VELOCITY_PER_ANOMALY)
        integrity += impact
        adjustments.append({"reason": "citation_velocity_anomalies", "impact": impact,
                            "detail": {"count": len(anomalies), "weight_each": WEIGHT_VELOCITY_PER_ANOMALY,
                                       "cap": WEIGHT_VELOCITY_MAX}})
    integrity = round(max(CREDIBILITY_SCORE_MIN, min(CREDIBILITY_SCORE_MAX, integrity)), 1)
    explanation = (
        f"Adjusted metrics estimate the effect of the sampled self-citation rate ({self_citation_rate:.1%}). "
        "Citation concentration does not establish reciprocal citation rings. "
        "This heuristic describes the checked sample and is not a finding about misconduct."
    )
    return {
        "adjusted_h_index": adjusted_h, "adjusted_citation_count": adjusted_citations,
        "integrity_score": integrity, "self_citation_rate": round(self_citation_rate, 4),
        "topic_relevance_score": round(avg_topic, 3) if avg_topic is not None else None,
        "explanation": explanation,
        "breakdown": {
            "base": 100.0, "adjustments": adjustments, "warnings": warning_types,
            "final": integrity, "confidence": _confidence(publications, ring_data),
            "formula_version": FORMULA_VERSION, "assessment_status": "available",
            "limitations": ["Sample-based heuristic; not a misconduct assessment.",
                            "Adjusted metrics extrapolate a sampled self-citation rate."],
        },
    }


def _confidence(publications: list[dict], ring_data: dict) -> float:
    """Sample-size indicator, not a calibrated probability of research integrity."""
    checked = ring_data.get("total_citations_checked", 0)
    if not publications or checked <= 0 or ring_data.get("citation_evidence_status") != "succeeded":
        return 0.0
    return round(min(1.0, len(publications) / 20) * min(1.0, checked / (len(publications) * 5)), 2)


def _calculate_h_index(publications: list[dict]) -> int:
    citations = sorted([p.get("citation_count", 0) for p in publications], reverse=True)
    return sum(1 for rank, count in enumerate(citations, 1) if count >= rank)
