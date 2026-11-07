"""
Scholar scraper — fetches researcher profiles and publications from academic APIs.

Primary: Semantic Scholar API (free, no key needed for basic access)
Secondary: ORCID public API
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

S2_BASE = "https://api.semanticscholar.org/graph/v1"
ORCID_BASE = "https://pub.orcid.org/v3.0"


async def search_by_name(name: str) -> Optional[dict]:
    """Search Semantic Scholar for an author by name. Returns best match."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{S2_BASE}/author/search",
                params={"query": name, "limit": 1, "fields": "name,affiliations,paperCount,citationCount,hIndex"},
            )
            if resp.status_code != 200:
                logger.warning("S2 author search returned %d", resp.status_code)
                return None
            data = resp.json().get("data", [])
            if not data:
                return None
            author = data[0]
            return _normalize_s2_author(author)
    except Exception:
        logger.exception("Semantic Scholar name search failed")
        return None


async def fetch_by_s2_id(author_id: str) -> Optional[dict]:
    """Fetch author profile from Semantic Scholar by their S2 author ID."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{S2_BASE}/author/{author_id}",
                params={"fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds"},
            )
            if resp.status_code != 200:
                return None
            return _normalize_s2_author(resp.json())
    except Exception:
        logger.exception("S2 author fetch failed")
        return None


async def fetch_by_orcid(orcid: str) -> Optional[dict]:
    """Fetch researcher info from ORCID public API."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{ORCID_BASE}/{orcid}/record",
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            person = data.get("person", {})
            name_data = person.get("name", {})
            given = name_data.get("given-names", {}).get("value", "")
            family = name_data.get("family-name", {}).get("value", "")

            # Try to find on Semantic Scholar using name
            full_name = f"{given} {family}".strip()
            if full_name:
                s2_profile = await search_by_name(full_name)
                if s2_profile:
                    s2_profile["orcid"] = orcid
                    return s2_profile

            return {
                "s2_id": None,
                "name": full_name or "Unknown",
                "institution": None,
                "h_index": None,
                "citation_count": None,
                "paper_count": None,
                "orcid": orcid,
            }
    except Exception:
        logger.exception("ORCID fetch failed")
        return None


async def fetch_publications(author_id: str, limit: int = 100) -> list[dict]:
    """
    Fetch an author's publications from Semantic Scholar.

    Returns list of dicts with: paper_id, title, journal, year, doi, citation_count, authors
    """
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{S2_BASE}/author/{author_id}/papers",
                params={
                    "fields": "title,venue,year,externalIds,citationCount,authors",
                    "limit": min(limit, 500),
                },
            )
            if resp.status_code != 200:
                logger.warning("S2 papers fetch returned %d", resp.status_code)
                return []

            papers = resp.json().get("data", [])
            results = []
            for p in papers:
                ext_ids = p.get("externalIds") or {}
                authors = p.get("authors") or []
                results.append({
                    "paper_id": p.get("paperId"),
                    "title": p.get("title", "Untitled"),
                    "journal": p.get("venue") or None,
                    "year": p.get("year"),
                    "doi": ext_ids.get("DOI"),
                    "citation_count": p.get("citationCount", 0),
                    "authors": [
                        {"id": a.get("authorId"), "name": a.get("name", "")}
                        for a in authors
                    ],
                })
            return results
    except Exception:
        logger.exception("S2 publications fetch failed")
        return []


async def fetch_paper_citations(paper_id: str, limit: int = 100) -> list[dict]:
    """Fetch papers that cite a given paper, with their author info."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{S2_BASE}/paper/{paper_id}/citations",
                params={
                    "fields": "title,authors,year",
                    "limit": min(limit, 500),
                },
            )
            if resp.status_code != 200:
                return []

            citations = resp.json().get("data", [])
            results = []
            for c in citations:
                citing = c.get("citingPaper", {})
                authors = citing.get("authors") or []
                results.append({
                    "paper_id": citing.get("paperId"),
                    "title": citing.get("title", ""),
                    "year": citing.get("year"),
                    "authors": [
                        {"id": a.get("authorId"), "name": a.get("name", "")}
                        for a in authors
                    ],
                })
            return results
    except Exception:
        logger.exception("S2 citations fetch failed for paper %s", paper_id)
        return []


async def resolve_researcher(
    name: Optional[str] = None,
    scopus_id: Optional[str] = None,
    google_scholar_id: Optional[str] = None,
    orcid: Optional[str] = None,
) -> Optional[dict]:
    """
    Resolve a researcher's profile from any identifier.
    Returns normalized profile dict or None.
    """
    # Try ORCID first (most reliable)
    if orcid:
        profile = await fetch_by_orcid(orcid)
        if profile:
            return profile

    # Try name search on Semantic Scholar
    if name:
        profile = await search_by_name(name)
        if profile:
            return profile

    # If we only have scopus/scholar IDs, try name-based fallback
    return None


def _normalize_s2_author(author: dict) -> dict:
    """Normalize Semantic Scholar author data to our internal format."""
    affiliations = author.get("affiliations") or []
    institution = affiliations[0] if affiliations else None
    ext_ids = author.get("externalIds") or {}

    return {
        "s2_id": author.get("authorId"),
        "name": author.get("name", "Unknown"),
        "institution": institution,
        "h_index": author.get("hIndex"),
        "citation_count": author.get("citationCount"),
        "paper_count": author.get("paperCount"),
        "orcid": ext_ids.get("ORCID"),
    }
