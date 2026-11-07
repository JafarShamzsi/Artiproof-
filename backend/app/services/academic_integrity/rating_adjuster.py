"""
Rating adjuster — calculates adjusted academic metrics after removing suspicious citations.

Produces:
- Adjusted h-index (excluding self-citations and ring citations)
- Adjusted citation count
- Overall integrity score (0-100) plus a breakdown explaining each adjustment
"""

import logging

from app.constants import CREDIBILITY_SCORE_MAX, CREDIBILITY_SCORE_MIN
from app.schemas.breakdown import FORMULA_VERSION

logger = logging.getLogger(__name__)


# Adjustment weights — bumping these requires bumping FORMULA_VERSION
WEIGHT_SELF_CITE_FLAGGED = 25.0
WEIGHT_SELF_CITE_ELEVATED = 10.0
WEIGHT_RING_PER_CONFIDENCE = 20.0
WEIGHT_SUSPICIOUS_PAIR_EACH = 5.0
WEIGHT_SUSPICIOUS_PAIR_MAX = 15.0
WEIGHT_VELOCITY_PER_ANOMALY = 3.0
WEIGHT_VELOCITY_MAX = 10.0
WEIGHT_TOPIC_RELEVANCE_GAP = 20.0  # multiplied by (0.5 - score)


def calculate_adjusted_metrics(
    publications: list[dict],
    ring_data: dict,
    official_h_index: int | None,
    official_citation_count: int | None,
) -> dict:
    """
    Calculate adjusted metrics after accounting for citation manipulation.

    Returns:
        {
            "adjusted_h_index": int,
            "adjusted_citation_count": int,
            "integrity_score": float (0-100),
            "self_citation_rate": float,
            "topic_relevance_score": float | None,
            "explanation": str,
            "breakdown": {...}  # IntegrityBreakdown shape
        }
    """
    self_citation_rate = ring_data.get("self_citation_rate", 0.0)
    suspicious_pairs = ring_data.get("suspicious_pairs", [])
    potential_rings = ring_data.get("potential_rings", [])
    flags = ring_data.get("flags", [])

    # Estimate citation inflation from rings
    ring_citation_estimate = 0
    for pair in suspicious_pairs:
        ring_citation_estimate += pair.get("citation_count", 0)

    total_official = official_citation_count or sum(p.get("citation_count", 0) for p in publications)
    self_cite_deduction = int(total_official * self_citation_rate)

    adjusted_citations = max(0, total_official - self_cite_deduction - ring_citation_estimate)

    h_index = official_h_index or _calculate_h_index(publications)
    if total_official > 0:
        ratio = adjusted_citations / total_official
        adjusted_h = max(0, int(h_index * ratio))
    else:
        adjusted_h = h_index

    topic_scores = [
        p.get("topic_match_score")
        for p in publications
        if p.get("topic_match_score") is not None
    ]
    avg_topic_relevance = sum(topic_scores) / len(topic_scores) if topic_scores else None

    integrity = 100.0
    adjustments: list[dict] = []

    # Self-citation
    if self_citation_rate > 0.25:
        impact = -WEIGHT_SELF_CITE_FLAGGED
        integrity += impact
        adjustments.append({
            "reason": "high_self_citation_rate",
            "impact": impact,
            "detail": {
                "rate": round(self_citation_rate, 4),
                "threshold": 0.25,
            },
        })
    elif self_citation_rate > 0.15:
        impact = -WEIGHT_SELF_CITE_ELEVATED
        integrity += impact
        adjustments.append({
            "reason": "elevated_self_citation_rate",
            "impact": impact,
            "detail": {
                "rate": round(self_citation_rate, 4),
                "threshold": 0.15,
            },
        })

    # Citation rings
    for ring in potential_rings:
        confidence = ring.get("confidence", 0.5)
        impact = -round(WEIGHT_RING_PER_CONFIDENCE * confidence, 2)
        integrity += impact
        adjustments.append({
            "reason": "citation_ring_member",
            "impact": impact,
            "detail": {
                "ring_size": len(ring.get("members", [])),
                "total_mutual_citations": ring.get("total_mutual_citations", 0),
                "confidence": round(confidence, 2),
            },
        })

    # Suspicious pairs (capped)
    if suspicious_pairs:
        impact = -min(WEIGHT_SUSPICIOUS_PAIR_MAX, len(suspicious_pairs) * WEIGHT_SUSPICIOUS_PAIR_EACH)
        integrity += impact
        adjustments.append({
            "reason": "suspicious_citation_pairs",
            "impact": impact,
            "detail": {
                "count": len(suspicious_pairs),
                "weight_each": WEIGHT_SUSPICIOUS_PAIR_EACH,
                "cap": WEIGHT_SUSPICIOUS_PAIR_MAX,
            },
        })

    # Topic relevance
    if avg_topic_relevance is not None and avg_topic_relevance < 0.5:
        impact = -round((0.5 - avg_topic_relevance) * WEIGHT_TOPIC_RELEVANCE_GAP, 2)
        integrity += impact
        adjustments.append({
            "reason": "low_topic_relevance",
            "impact": impact,
            "detail": {
                "average": round(avg_topic_relevance, 3),
                "threshold": 0.5,
            },
        })

    # Velocity anomalies (capped)
    anomalies = ring_data.get("citation_velocity_anomalies", [])
    if anomalies:
        impact = -min(WEIGHT_VELOCITY_MAX, len(anomalies) * WEIGHT_VELOCITY_PER_ANOMALY)
        integrity += impact
        adjustments.append({
            "reason": "citation_velocity_anomalies",
            "impact": impact,
            "detail": {
                "count": len(anomalies),
                "weight_each": WEIGHT_VELOCITY_PER_ANOMALY,
                "cap": WEIGHT_VELOCITY_MAX,
            },
        })

    integrity = max(CREDIBILITY_SCORE_MIN, min(CREDIBILITY_SCORE_MAX, integrity))

    explanation_parts = []
    if adjusted_h != h_index:
        explanation_parts.append(
            f"h-index adjusted from {h_index} to {adjusted_h} after removing "
            f"{self_cite_deduction} self-citations and ~{ring_citation_estimate} suspicious citations"
        )
    if flags:
        explanation_parts.extend(flags)
    if not explanation_parts:
        explanation_parts.append("No significant integrity issues detected")

    breakdown = {
        "base": 100.0,
        "adjustments": adjustments,
        "warnings": flags,
        "final": round(integrity, 1),
        "confidence": _confidence(publications, ring_data),
        "formula_version": FORMULA_VERSION,
    }

    return {
        "adjusted_h_index": adjusted_h,
        "adjusted_citation_count": adjusted_citations,
        "integrity_score": round(integrity, 1),
        "self_citation_rate": round(self_citation_rate, 4),
        "topic_relevance_score": round(avg_topic_relevance, 3) if avg_topic_relevance is not None else None,
        "explanation": ". ".join(explanation_parts),
        "breakdown": breakdown,
    }


def _confidence(publications: list[dict], ring_data: dict) -> float:
    """Confidence in the integrity score.

    Lower when we have very few publications (small sample) or when the
    citation graph was incomplete.
    """
    factors: list[float] = []

    pub_count = len(publications)
    factors.append(min(1.0, pub_count / 20))  # 20 papers ~= full confidence

    total_checked = ring_data.get("total_citations_checked", 0)
    if pub_count:
        # ~5 citations checked per paper would be a reasonable target
        factors.append(min(1.0, total_checked / max(pub_count * 5, 1)))

    if not factors:
        return 0.5
    return round(sum(factors) / len(factors), 2)


def _calculate_h_index(publications: list[dict]) -> int:
    """Calculate h-index from a list of publications."""
    citations = sorted(
        [p.get("citation_count", 0) for p in publications],
        reverse=True,
    )
    h = 0
    for i, c in enumerate(citations):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h
