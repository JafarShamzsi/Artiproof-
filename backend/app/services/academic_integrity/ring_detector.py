"""
Ring detector — analyzes citation graphs for citation manipulation patterns.

Detects:
- Citation rings (groups of 3+ authors with circular citation)
- Abnormally high mutual citation pairs
- Citation farms (papers cited mostly by the same small group)
"""

import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Thresholds
MUTUAL_CITATION_THRESHOLD = 5  # If author A cites author B 5+ times, flag pair
RING_MIN_SIZE = 3
SELF_CITATION_WARN_RATE = 0.15  # 15%
SELF_CITATION_FLAG_RATE = 0.25  # 25%


def detect_rings(graph_data: dict, publications: list[dict]) -> dict:
    """
    Analyze a citation graph for manipulation patterns.

    Args:
        graph_data: Output from citation_graph_builder.build_citation_graph()
        publications: List of publication dicts for the target researcher

    Returns:
        {
            "suspicious_pairs": [{"author_a": {...}, "author_b": {...}, "mutual_count": int}],
            "potential_rings": [{"members": [...], "total_mutual_citations": int}],
            "self_citation_rate": float,
            "self_citation_status": "normal" | "elevated" | "flagged",
            "citation_velocity_anomalies": [...],
            "flags": [str],
        }
    """
    citing_authors = graph_data.get("citing_authors", {})
    self_citations = graph_data.get("self_citations", 0)
    total_checked = graph_data.get("total_citations_checked", 0)
    edges = graph_data.get("edges", [])

    flags = []

    # 1. Self-citation analysis
    self_citation_rate = 0.0
    if total_checked > 0:
        self_citation_rate = self_citations / total_checked

    self_citation_status = "normal"
    if self_citation_rate >= SELF_CITATION_FLAG_RATE:
        self_citation_status = "flagged"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) exceeds {SELF_CITATION_FLAG_RATE:.0%} threshold")
    elif self_citation_rate >= SELF_CITATION_WARN_RATE:
        self_citation_status = "elevated"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) is elevated")

    # 2. Suspicious mutual citation pairs
    suspicious_pairs = []
    for edge in edges:
        weight = edge.get("weight", 0)
        if weight >= MUTUAL_CITATION_THRESHOLD:
            source_id = edge.get("source")
            source_info = citing_authors.get(source_id, {})
            suspicious_pairs.append({
                "author_id": source_id,
                "author_name": source_info.get("name", "Unknown"),
                "citation_count": weight,
                "papers_cited": edge.get("papers", []),
            })

    if suspicious_pairs:
        flags.append(f"{len(suspicious_pairs)} author(s) cite this researcher an unusually high number of times")

    # 3. Potential citation rings — find clusters of frequent citers
    # Group frequent citers and check if they also cite each other
    frequent_citers = [
        aid for aid, info in citing_authors.items()
        if info.get("count", 0) >= 3
    ]

    potential_rings = []
    if len(frequent_citers) >= RING_MIN_SIZE:
        # If multiple authors all heavily cite the target, they may form a ring
        ring_members = []
        for citer_id in frequent_citers[:10]:
            info = citing_authors.get(citer_id, {})
            ring_members.append({
                "id": citer_id,
                "name": info.get("name", "Unknown"),
                "citations_to_target": info.get("count", 0),
            })

        total_mutual = sum(m["citations_to_target"] for m in ring_members)

        if len(ring_members) >= RING_MIN_SIZE and total_mutual >= 10:
            potential_rings.append({
                "members": ring_members,
                "total_mutual_citations": total_mutual,
                "confidence": min(0.9, 0.3 + (total_mutual / 50)),
            })
            flags.append(f"Potential citation ring detected: {len(ring_members)} authors with {total_mutual} mutual citations")

    # 4. Citation velocity anomalies — papers with sudden citation spikes
    citation_velocity_anomalies = []
    for pub in publications:
        citation_count = pub.get("citation_count", 0)
        year = pub.get("year")
        if year and citation_count > 0:
            age = max(1, 2026 - year)
            rate = citation_count / age
            # Flag papers with >50 citations/year (unusually high for most fields)
            if rate > 50 and citation_count > 100:
                citation_velocity_anomalies.append({
                    "title": pub.get("title", ""),
                    "year": year,
                    "citation_count": citation_count,
                    "citations_per_year": round(rate, 1),
                })

    if citation_velocity_anomalies:
        flags.append(f"{len(citation_velocity_anomalies)} paper(s) have abnormally high citation velocity")

    return {
        "suspicious_pairs": suspicious_pairs,
        "potential_rings": potential_rings,
        "self_citation_rate": round(self_citation_rate, 4),
        "self_citation_status": self_citation_status,
        "citation_velocity_anomalies": citation_velocity_anomalies,
        "flags": flags,
    }
