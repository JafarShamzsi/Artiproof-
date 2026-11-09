"""
CrossRef API client — free, no key needed. Used for DOI metadata enrichment and retraction checks.
"""

import logging
from typing import Optional

import httpx
from app.services.scrapers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
BASE_URL = "https://api.crossref.org"
POLITE_PARAMS = {"mailto": "artiproof@example.com"}


async def lookup_doi(doi: str) -> Optional[dict]:
    """Look up paper metadata by DOI."""
    await rate_limiter.acquire("crossref")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/works/{doi}", params=POLITE_PARAMS)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None

    item = resp.json().get("message", {})
    return {
        "doi": doi,
        "title": (item.get("title") or [None])[0],
        "abstract": item.get("abstract"),
        "journal": (item.get("container-title") or [None])[0],
        "issn": (item.get("ISSN") or [None])[0],
        "year": (item.get("published") or {}).get("date-parts", [[None]])[0][0],
        "type": item.get("type"),
        "is_retracted": "retracted" in str(item.get("update-to", [])).lower(),
        "reference_count": item.get("references-count", 0),
        "cited_by_count": item.get("is-referenced-by-count", 0),
        "authors": [
            {"name": f"{a.get('given', '')} {a.get('family', '')}".strip(), "orcid": a.get("ORCID")}
            for a in item.get("author", [])
        ],
    }


async def check_retraction(doi: str) -> bool:
    """Check if a DOI has been retracted."""
    data = await lookup_doi(doi)
    return data.get("is_retracted", False) if data else False
