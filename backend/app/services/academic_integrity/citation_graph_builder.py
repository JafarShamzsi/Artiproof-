"""
Citation graph builder — constructs a citation network for a researcher
using networkx and Semantic Scholar data.
"""

import logging
from collections import Counter, defaultdict

from app.services.academic_integrity.scholar_scraper import fetch_paper_citations

logger = logging.getLogger(__name__)


async def build_citation_graph(
    target_author_id: str,
    publications: list[dict],
    max_papers_to_check: int = 20,
) -> dict:
    """
    Build a citation graph for a researcher.

    Analyzes who cites them (and how often) to detect patterns.

    Returns:
        {
            "nodes": [{"id": str, "name": str, "type": "target"|"citer", "citation_count": int}],
            "edges": [{"source": str, "target": str, "weight": int, "papers": [str]}],
            "citing_authors": {author_id: {"name": str, "count": int}},
            "self_citations": int,
            "total_citations_checked": int,
            "per_paper_citations": {paper_id: {"total": int, "self_citations": int}},
        }
    """
    citing_author_counts: Counter = Counter()
    citing_author_names: dict[str, str] = {}
    self_citations = 0
    total_checked = 0
    edges_data: dict[str, list[str]] = defaultdict(list)
    # Per-paper tracking so the orchestrator can mark which publications
    # are heavily self-cited (issue 13) and count suspicious citations
    # without relying on title-string matching (issue 14).
    per_paper: dict[str, dict] = {}
    relationships = []
    attempted_paper_ids = []
    unavailable_paper_ids = []
    incomplete_author_records = 0
    unidentified_citations = 0
    missing_paper_ids = 0
    seen_papers = set()

    sorted_pubs = sorted(publications, key=lambda p: p.get("citation_count", 0), reverse=True)
    papers_to_check = sorted_pubs[:max_papers_to_check]

    for pub in papers_to_check:
        paper_id = pub.get("paper_id")
        if not paper_id:
            missing_paper_ids += 1
            continue
        if paper_id in seen_papers:
            continue
        seen_papers.add(paper_id)
        attempted_paper_ids.append(paper_id)

        citations = await fetch_paper_citations(paper_id, limit=50)
        if citations is None:
            unavailable_paper_ids.append(paper_id)
            continue
        # Each citing-paper/cited-paper relationship counts once. Duplicate
        # authors must not count a self-citation twice or inflate an edge.
        unique_citations = {}
        for citing in citations:
            citing_id = citing.get("paper_id")
            if not citing_id:
                unidentified_citations += 1
                continue
            unique_citations.setdefault(citing_id, citing)
        paper_total = len(unique_citations)
        paper_self = 0
        # author_id -> count of times they cited THIS paper
        paper_citers: Counter = Counter()
        total_checked += paper_total

        for citing_id, citing in unique_citations.items():
            authors = citing.get("authors") or []
            known_authors = {a["id"]: a for a in authors if a.get("id")}
            if not authors or any(not a.get("id") for a in authors):
                incomplete_author_records += 1
            relationships.append({
                "citing_paper_id": citing_id, "cited_paper_id": paper_id,
                "author_ids": list(known_authors),
            })
            for aid, author in known_authors.items():

                citing_author_names[aid] = author.get("name", "Unknown")

                if aid == target_author_id:
                    self_citations += 1
                    paper_self += 1
                else:
                    citing_author_counts[aid] += 1
                    edges_data[aid].append(pub.get("title", "")[:80])
                    paper_citers[aid] += 1

        per_paper[paper_id] = {
            "total": paper_total,
            "self_citations": paper_self,
            "citing_authors": dict(paper_citers),
        }

    nodes = [
        {
            "id": target_author_id,
            "name": "Target Researcher",
            "type": "target",
            "citation_count": sum(p.get("citation_count", 0) for p in publications),
        }
    ]

    edges = []
    for author_id, count in citing_author_counts.most_common(30):
        nodes.append({
            "id": author_id,
            "name": citing_author_names.get(author_id, "Unknown"),
            "type": "citer",
            "citation_count": count,
        })
        edges.append({
            "source": author_id,
            "target": target_author_id,
            "weight": count,
            "papers": edges_data.get(author_id, [])[:5],
            "relationships": [r for r in relationships if author_id in r["author_ids"]],
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "citing_authors": {
            aid: {"name": citing_author_names.get(aid, "Unknown"), "count": c}
            for aid, c in citing_author_counts.most_common(50)
        },
        "self_citations": self_citations,
        "total_citations_checked": total_checked,
        "per_paper_citations": per_paper,
        "relationships": relationships,
        "citation_evidence_status": (
            "unavailable" if not per_paper else
            "partial" if unavailable_paper_ids or missing_paper_ids or incomplete_author_records or unidentified_citations else
            "succeeded"
        ),
        "coverage": {
            "publications_available": len(publications),
            "papers_attempted": len(attempted_paper_ids),
            "papers_succeeded": len(per_paper),
            "unavailable_paper_ids": unavailable_paper_ids,
            "missing_paper_ids": missing_paper_ids,
            "incomplete_author_records": incomplete_author_records,
            "unidentified_citations": unidentified_citations,
            "paper_limit": max_papers_to_check, "citations_per_paper_limit": 50,
            "scope": "Leading citation samples from selected publications; not a complete citation network.",
        },
    }
