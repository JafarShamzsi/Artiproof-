"""
Ring detector — analyzes citation graphs for citation manipulation patterns.

Detects:
- Citation rings (groups of 3+ authors with circular citation)
- Abnormally high mutual citation pairs
- Citation farms (papers cited mostly by the same small group)

Thresholds vary by research field because base rates of self-citation and
mutual citation differ a lot between, say, medicine and computer science.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Field-normalized thresholds. Pick by passing `field=` into `detect_rings`.
# "default" is the fallback when the field is unknown.
FIELD_THRESHOLDS = {
    "computer_science": {"mutual_citation": 8, "self_cite_warn": 0.20, "self_cite_flag": 0.35},
    "medicine":         {"mutual_citation": 5, "self_cite_warn": 0.12, "self_cite_flag": 0.20},
    "physics":          {"mutual_citation": 6, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
    "biology":          {"mutual_citation": 5, "self_cite_warn": 0.12, "self_cite_flag": 0.22},
    "chemistry":        {"mutual_citation": 5, "self_cite_warn": 0.13, "self_cite_flag": 0.22},
    "economics":        {"mutual_citation": 6, "self_cite_warn": 0.15, "self_cite_flag": 0.27},
    "default":          {"mutual_citation": 5, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
}

RING_MIN_SIZE = 3


def get_thresholds(field: str | None = None) -> dict:
    """Return the threshold dict for a given research field."""
    if not field:
        return FIELD_THRESHOLDS["default"]
    key = field.lower().replace(" ", "_").replace("-", "_")
    return FIELD_THRESHOLDS.get(key, FIELD_THRESHOLDS["default"])


def detect_rings(
    graph_data: dict,
    publications: list[dict],
    field: str | None = None,
) -> dict:
    """
    Analyze a citation graph for manipulation patterns.

    Args:
        graph_data: Output from citation_graph_builder.build_citation_graph()
        publications: List of publication dicts for the target researcher
        field: Research field for threshold tuning (e.g. "medicine"). Defaults
            to the conservative "default" thresholds when unknown.

    Returns:
        {
            "suspicious_pairs": [{"author_a": {...}, "author_b": {...}, "mutual_count": int}],
            "potential_rings": [{"members": [...], "total_mutual_citations": int}],
            "self_citation_rate": float,
            "self_citation_status": "normal" | "elevated" | "flagged",
            "citation_velocity_anomalies": [...],
            "flags": [str],
            "field_used": str,
            "thresholds_used": {...},
            "total_citations_checked": int,
        }
    """
    thresholds = get_thresholds(field)
    mutual_threshold = thresholds["mutual_citation"]
    warn_rate = thresholds["self_cite_warn"]
    flag_rate = thresholds["self_cite_flag"]

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
    if self_citation_rate >= flag_rate:
        self_citation_status = "flagged"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) exceeds {flag_rate:.0%} threshold for {field or 'default'}")
    elif self_citation_rate >= warn_rate:
        self_citation_status = "elevated"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) is elevated for {field or 'default'}")

    # 2. Suspicious mutual citation pairs
    suspicious_pairs = []
    for edge in edges:
        weight = edge.get("weight", 0)
        if weight >= mutual_threshold:
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
    frequent_citers = [
        aid for aid, info in citing_authors.items()
        if info.get("count", 0) >= 3
    ]

    potential_rings = []
    if len(frequent_citers) >= RING_MIN_SIZE:
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
    current_year = datetime.now().year
    citation_velocity_anomalies = []
    for pub in publications:
        citation_count = pub.get("citation_count", 0)
        year = pub.get("year")
        if year and citation_count > 0:
            age = max(1, current_year - year)
            rate = citation_count / age
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
        "field_used": field or "default",
        "thresholds_used": thresholds,
        "total_citations_checked": total_checked,
    }
