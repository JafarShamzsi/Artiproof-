"""
Scopus API client — requires API key (free for academic use via Elsevier Dev Portal).
Optional enrichment source — system works without it.
"""

import logging
from typing import Optional

import httpx
from app.config import settings
from app.services.scrapers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
BASE_URL = "https://api.elsevier.com"


def is_available() -> bool:
    return bool(settings.SCOPUS_API_KEY)


def _headers():
    h = {"Accept": "application/json"}
    if settings.SCOPUS_API_KEY:
        h["X-ELS-APIKey"] = settings.SCOPUS_API_KEY
    return h


async def search_author(name: str, affiliation: str = None) -> list[dict]:
    if not is_available():
        return []

    parts = name.split()
    query = f"AUTHLASTNAME({parts[-1]})"
    if len(parts) > 1:
        query += f" AND AUTHFIRST({parts[0]})"
    if affiliation:
        query += f" AND AFFIL({affiliation})"

    await rate_limiter.acquire("scopus")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/content/search/author",
            params={"query": query, "count": 5},
            headers=_headers(),
        )
        if resp.status_code in (401, 403):
            return []
        if resp.status_code != 200:
            return []

    entries = resp.json().get("search-results", {}).get("entry", [])
    return [
        {
            "scopus_id": e.get("dc:identifier", "").replace("AUTHOR_ID:", ""),
            "name": f"{e.get('preferred-name', {}).get('given-name', '')} {e.get('preferred-name', {}).get('surname', '')}".strip(),
            "affiliation": (e.get("affiliation-current") or {}).get("affiliation-name"),
            "document_count": int(e.get("document-count", 0)),
            "cited_by_count": int(e.get("cited-by-count", 0)),
        }
        for e in entries if e.get("dc:identifier")
    ]


async def get_author_profile(scopus_id: str) -> Optional[dict]:
    if not is_available():
        return None

    await rate_limiter.acquire("scopus")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/content/author/author_id/{scopus_id}",
            params={"field": "h-index,document-count,cited-by-count,subject-area"},
            headers=_headers(),
        )
        if resp.status_code in (401, 403, 404):
            return None
        if resp.status_code != 200:
            return None

    data = resp.json().get("author-retrieval-response", [{}])[0]
    return {
        "scopus_id": scopus_id,
        "h_index": int(data.get("h-index", 0)),
        "document_count": int((data.get("coredata") or {}).get("document-count", 0)),
        "cited_by_count": int((data.get("coredata") or {}).get("cited-by-count", 0)),
        "subject_areas": [
            a.get("$", "") for a in (data.get("subject-areas") or {}).get("subject-area", [])
        ],
    }


async def get_author_publications(scopus_id: str, max_results: int = 200) -> list[dict]:
    if not is_available():
        return []

    await rate_limiter.acquire("scopus")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/content/search/scopus",
            params={
                "query": f"AU-ID({scopus_id})",
                "count": min(max_results, 200),
                "field": "dc:title,prism:publicationName,prism:coverDate,prism:doi,citedby-count,eid",
                "sort": "-citedby-count",
            },
            headers=_headers(),
        )
        if resp.status_code in (401, 403, 404):
            return []
        if resp.status_code != 200:
            return []

    entries = resp.json().get("search-results", {}).get("entry", [])
    return [
        {
            "title": e.get("dc:title"),
            "journal": e.get("prism:publicationName"),
            "doi": e.get("prism:doi"),
            "year": int(e.get("prism:coverDate", "0")[:4]) if e.get("prism:coverDate") else None,
            "citation_count": int(e.get("citedby-count", 0)),
            "eid": e.get("eid"),
        }
        for e in entries if e.get("dc:title")
    ]
