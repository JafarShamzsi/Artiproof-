"""
Rating adjuster — calculates adjusted academic metrics after removing suspicious citations.

Produces:
- Adjusted h-index (excluding self-citations and ring citations)
- Adjusted citation count
- Overall integrity score (0-100)
"""

import logging

logger = logging.getLogger(__name__)


def calculate_adjusted_metrics(
    publications: list[dict],
    ring_data: dict,
    official_h_index: int | None,
    official_citation_count: int | None,
) -> dict:
    """
    Calculate adjusted metrics after accounting for citation manipulation.

    Args:
        publications: Publication dicts with citation_count
        ring_data: Output from ring_detector.detect_rings()
        official_h_index: The researcher's reported h-index
        official_citation_count: The researcher's reported total citation count

    Returns:
        {
            "adjusted_h_index": int,
            "adjusted_citation_count": int,
            "integrity_score": float (0-100),
            "self_citation_rate": float,
            "topic_relevance_score": float | None,
            "explanation": str,
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

    # Self-citation deduction
    total_official = official_citation_count or sum(p.get("citation_count", 0) for p in publications)
    self_cite_deduction = int(total_official * self_citation_rate)

    # Adjusted citation count
    adjusted_citations = max(0, total_official - self_cite_deduction - ring_citation_estimate)

    # Adjusted h-index
    # Simple approach: scale h-index by the ratio of adjusted/official citations
    h_index = official_h_index or _calculate_h_index(publications)
    if total_official > 0:
        ratio = adjusted_citations / total_official
        adjusted_h = max(0, int(h_index * ratio))
    else:
        adjusted_h = h_index

    # Topic relevance score (average of papers with scores)
    topic_scores = [
        p.get("topic_match_score")
        for p in publications
        if p.get("topic_match_score") is not None
    ]
    avg_topic_relevance = sum(topic_scores) / len(topic_scores) if topic_scores else None

    # Integrity score (0-100)
    integrity = 100.0

    # Deductions for self-citation
    if self_citation_rate > 0.25:
        integrity -= 25
    elif self_citation_rate > 0.15:
        integrity -= 10

    # Deductions for citation rings
    if potential_rings:
        for ring in potential_rings:
            confidence = ring.get("confidence", 0.5)
            integrity -= 20 * confidence

    # Deductions for suspicious pairs
    integrity -= min(15, len(suspicious_pairs) * 5)

    # Deductions for poor topic relevance
    if avg_topic_relevance is not None and avg_topic_relevance < 0.5:
        integrity -= (0.5 - avg_topic_relevance) * 20

    # Deductions for velocity anomalies
    anomalies = ring_data.get("citation_velocity_anomalies", [])
    if anomalies:
        integrity -= min(10, len(anomalies) * 3)

    integrity = max(0.0, min(100.0, integrity))

    # Build explanation
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

    return {
        "adjusted_h_index": adjusted_h,
        "adjusted_citation_count": adjusted_citations,
        "integrity_score": round(integrity, 1),
        "self_citation_rate": round(self_citation_rate, 4),
        "topic_relevance_score": round(avg_topic_relevance, 3) if avg_topic_relevance is not None else None,
        "explanation": ". ".join(explanation_parts),
    }


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
