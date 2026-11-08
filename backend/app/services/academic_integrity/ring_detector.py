"""
Citation-pattern summaries from sampled incoming citation relationships.

The current graph does not establish reciprocity, cycles or manipulation.
Legacy ring/pair keys remain empty; concentration is exploratory evidence.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Heuristic thresholds, not validated discipline baselines.
# "default" is the fallback when the field is unknown.
FIELD_THRESHOLDS = {
    "computer_science": {"frequent_citer": 8, "self_cite_warn": 0.20, "self_cite_flag": 0.35},
    "medicine":         {"frequent_citer": 5, "self_cite_warn": 0.12, "self_cite_flag": 0.20},
    "physics":          {"frequent_citer": 6, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
    "biology":          {"frequent_citer": 5, "self_cite_warn": 0.12, "self_cite_flag": 0.22},
    "chemistry":        {"frequent_citer": 5, "self_cite_warn": 0.13, "self_cite_flag": 0.22},
    "economics":        {"frequent_citer": 6, "self_cite_warn": 0.15, "self_cite_flag": 0.27},
    "default":          {"frequent_citer": 5, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
}

CONCENTRATION_MIN_SIZE = 3


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
    Summarize incoming citation patterns, without inferring manipulation.

    Args:
        graph_data: Output from citation_graph_builder.build_citation_graph()
        publications: List of publication dicts for the target researcher
        field: Research field for threshold tuning (e.g. "medicine"). Defaults
            to the conservative "default" thresholds when unknown.

    Returns:
        {
            "suspicious_pairs": [],  # retained legacy key; no reciprocal evidence
            "potential_rings": [],
            "frequent_citers": [...], "citation_concentration": [...],
            "self_citation_rate": float | None,
            "self_citation_status": "normal" | "elevated" | "flagged" | "unavailable",
            "citation_velocity_anomalies": [...],
            "flags": [str],
            "field_used": str,
            "thresholds_used": {...},
            "total_citations_checked": int,
        }
    """
    thresholds = get_thresholds(field)
    frequent_threshold = thresholds["frequent_citer"]
    warn_rate = thresholds["self_cite_warn"]
    flag_rate = thresholds["self_cite_flag"]

    citing_authors = graph_data.get("citing_authors", {})
    self_citations = graph_data.get("self_citations", 0)
    total_checked = graph_data.get("total_citations_checked", 0)
    edges = graph_data.get("edges", [])

    flags = []

    # Self-citation is assessed only for a successfully retrieved, identified sample.
    sample_available = total_checked > 0 and graph_data.get("citation_evidence_status") == "succeeded"
    self_citation_rate = 0.0
    if sample_available:
        self_citation_rate = self_citations / total_checked

    self_citation_status = "normal"
    if sample_available and self_citation_rate >= flag_rate:
        self_citation_status = "flagged"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) exceeds {flag_rate:.0%} threshold for {field or 'default'}")
    elif sample_available and self_citation_rate >= warn_rate:
        self_citation_status = "elevated"
        flags.append(f"Self-citation rate ({self_citation_rate:.0%}) is elevated for {field or 'default'}")

    # Incoming edges describe frequent citers, not mutual citation pairs.
    frequent_citers = []
    for edge in edges:
        weight = edge.get("weight", 0)
        if weight >= frequent_threshold:
            source_id = edge.get("source")
            source_info = citing_authors.get(source_id, {})
            frequent_citers.append({
                "author_id": source_id,
                "author_name": source_info.get("name", "Unknown"),
                "citation_count": weight,
                "papers_cited": edge.get("papers", []),
                "relationships": edge.get("relationships", []),
            })

    if frequent_citers:
        flags.append(f"{len(frequent_citers)} author(s) meet the frequent-citer threshold in this sample; this does not establish reciprocal citations")

    # Keep the former cluster observation without a ring label, fabricated
    # mutual-citation count or unsupported confidence in misconduct.
    concentrated_author_ids = [
        aid for aid, info in citing_authors.items()
        if info.get("count", 0) >= 3
    ]

    concentration = []
    if len(concentrated_author_ids) >= CONCENTRATION_MIN_SIZE:
        for citer_id in concentrated_author_ids[:10]:
            info = citing_authors.get(citer_id, {})
            concentration.append({
                "id": citer_id,
                "name": info.get("name", "Unknown"),
                "citations_to_target": info.get("count", 0),
                "relationships": [r for r in graph_data.get("relationships", []) if citer_id in r.get("author_ids", [])],
            })

        flags.append(f"Incoming citation concentration among {len(concentration)} frequent citing authors; relationships between those authors were not checked")

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
        "suspicious_pairs": [],
        "potential_rings": [],
        "frequent_citers": frequent_citers,
        "citation_concentration": concentration,
        "self_citation_rate": round(self_citation_rate, 4) if sample_available else None,
        "self_citation_status": self_citation_status if sample_available else "unavailable",
        "citation_velocity_anomalies": citation_velocity_anomalies,
        "flags": flags,
        "field_used": field or "default",
        "thresholds_used": thresholds,
        "total_citations_checked": total_checked,
        "citation_evidence_status": graph_data.get("citation_evidence_status", "unavailable"),
        "coverage": graph_data.get("coverage", {}),
        "limitation": "Only incoming citations were sampled. No reciprocal relationships or citation rings were established.",
    }
