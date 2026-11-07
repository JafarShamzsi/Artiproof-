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

    sorted_pubs = sorted(publications, key=lambda p: p.get("citation_count", 0), reverse=True)
    papers_to_check = sorted_pubs[:max_papers_to_check]

    for pub in papers_to_check:
        paper_id = pub.get("paper_id")
        if not paper_id:
            continue

        citations = await fetch_paper_citations(paper_id, limit=50)
        paper_total = len(citations)
        paper_self = 0
        # author_id -> count of times they cited THIS paper
        paper_citers: Counter = Counter()
        total_checked += paper_total

        for citing in citations:
            for author in citing.get("authors", []):
                aid = author.get("id")
                if not aid:
                    continue

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
    }
