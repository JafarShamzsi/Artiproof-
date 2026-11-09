"""
Semantic Scholar API client — primary source for citation-level data.
Free tier: 100 requests per 5 minutes (no key needed).
"""

import logging
from typing import Optional

import httpx
from app.config import settings
from app.services.scrapers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
BASE_URL = "https://api.semanticscholar.org/graph/v1"


def _headers() -> dict:
    h = {}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        h["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY
    return h


async def search_author(name: str, limit: int = 5) -> list[dict]:
    await rate_limiter.acquire("semantic_scholar")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/author/search",
            params={"query": name, "limit": limit,
                    "fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds"},
            headers=_headers(),
        )
        if resp.status_code != 200:
            logger.warning("S2 author search %d: %s", resp.status_code, resp.text[:200])
            return []
        return resp.json().get("data", [])


async def get_author(author_id: str) -> Optional[dict]:
    await rate_limiter.acquire("semantic_scholar")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/author/{author_id}",
            params={"fields": "name,affiliations,homepage,paperCount,citationCount,hIndex,externalIds"},
            headers=_headers(),
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def find_by_orcid(orcid: str) -> Optional[dict]:
    await rate_limiter.acquire("semantic_scholar")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/author/ORCID:{orcid}",
            params={"fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds"},
            headers=_headers(),
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def get_author_papers(author_id: str, limit: int = 500) -> list[dict]:
    """Paginated fetch of all papers by an author."""
    all_papers = []
    offset = 0
    batch = min(500, limit)

    while offset < limit:
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/author/{author_id}/papers",
                params={
                    "fields": "paperId,title,abstract,venue,year,citationCount,influentialCitationCount,referenceCount,authors,journal,publicationTypes,externalIds",
                    "limit": min(batch, limit - offset),
                    "offset": offset,
                },
                headers=_headers(),
            )
            if resp.status_code != 200:
                break
            data = resp.json().get("data", [])
            if not data:
                break
            all_papers.extend(data)
            if len(data) < batch:
                break
            offset += batch

    return all_papers


async def get_paper_citations(paper_id: str, limit: int = 500) -> list[dict]:
    """Get papers that CITE this paper — critical for ring detection."""
    all_cites = []
    offset = 0
    batch = min(500, limit)

    while offset < limit:
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/paper/{paper_id}/citations",
                params={
                    "fields": "paperId,title,authors,year,venue",
                    "limit": min(batch, limit - offset),
                    "offset": offset,
                },
                headers=_headers(),
            )
            if resp.status_code != 200:
                break
            data = resp.json().get("data", [])
            if not data:
                break
            all_cites.extend(data)
            if len(data) < batch:
                break
            offset += batch

    return all_cites


async def get_paper_references(paper_id: str, limit: int = 500) -> list[dict]:
    """Get papers that this paper REFERENCES."""
    all_refs = []
    offset = 0
    batch = min(500, limit)

    while offset < limit:
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/paper/{paper_id}/references",
                params={
                    "fields": "paperId,title,authors,year,venue",
                    "limit": min(batch, limit - offset),
                    "offset": offset,
                },
                headers=_headers(),
            )
            if resp.status_code != 200:
                break
            data = resp.json().get("data", [])
            if not data:
                break
            all_refs.extend(data)
            if len(data) < batch:
                break
            offset += batch

    return all_refs
