"""
Scholar scraper — fetches researcher profiles and publications from academic APIs.

Primary: Semantic Scholar API (free, no key needed for basic access)
Secondary: ORCID public API
"""

import logging
from typing import Optional

import httpx

from app.utils.retry import HTTP_RETRY_EXCEPTIONS

logger = logging.getLogger(__name__)

# Transient HTTP failures during best-effort fetches are expected and
# shouldn't pager-storm Sentry. Demote them to WARNING with the cause;
# anything else still trips logger.exception so real bugs get a trace.
# The decorator-driven retry already handles transient failures inside
# the helper's own loop — by the time we see one here it means even the
# retry budget was exhausted, which is still worth a warning but not an
# alert.

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
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("Semantic Scholar name search transient failure: %s", e)
        return None
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
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("S2 author fetch transient failure for %s: %s", author_id, e)
        return None
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
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("ORCID fetch transient failure for %s: %s", orcid, e)
        return None
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
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("S2 publications fetch transient failure for %s: %s", author_id, e)
        return []
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
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("S2 citations fetch transient failure for %s: %s", paper_id, e)
        return []
    except Exception:
        logger.exception("S2 citations fetch failed for paper %s", paper_id)
        return []


async def _resolve_via_scopus(scopus_id: str) -> Optional[dict]:
    """Look up Scopus profile, then re-resolve to S2 by name so the rest
    of the pipeline can use citation graph queries.
    """
    try:
        from app.services.scrapers.scopus_client import get_author_profile
    except ImportError:
        return None

    try:
        scopus_profile = await get_author_profile(scopus_id)
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("Scopus profile fetch transient failure for %s: %s", scopus_id, e)
        return None
    except Exception:
        logger.exception("Scopus profile fetch failed")
        return None
    if not scopus_profile:
        return None

    # Scopus profile gives us h-index and citation count, but no name. We
    # also need S2 ID for downstream queries; fall through to S2 search if
    # we have a name from elsewhere.
    return {
        "s2_id": None,
        "name": None,
        "institution": None,
        "h_index": scopus_profile.get("h_index"),
        "citation_count": scopus_profile.get("cited_by_count"),
        "paper_count": scopus_profile.get("document_count"),
        "scopus_id": scopus_id,
        "subject_areas": scopus_profile.get("subject_areas", []),
    }


async def _resolve_via_google_scholar(scholar_id: str) -> Optional[dict]:
    """Scrape Google Scholar profile, then re-resolve via S2 name search."""
    try:
        from app.services.scrapers.google_scholar import scrape_profile
    except ImportError:
        return None

    try:
        gs = await scrape_profile(scholar_id)
    except HTTP_RETRY_EXCEPTIONS as e:
        logger.warning("Google Scholar profile scrape transient failure for %s: %s", scholar_id, e)
        return None
    except Exception:
        logger.exception("Google Scholar profile scrape failed")
        return None
    if not gs:
        return None

    name = gs.get("name")
    s2_profile = await search_by_name(name) if name else None
    base = s2_profile or {
        "s2_id": None,
        "name": name,
        "institution": gs.get("affiliation"),
        "paper_count": None,
        "orcid": None,
    }
    # Layer in Google Scholar metrics where S2 didn't have them
    return {
        **base,
        "google_scholar_id": scholar_id,
        "h_index": base.get("h_index") or gs.get("h_index"),
        "citation_count": base.get("citation_count") or gs.get("total_citations"),
        "i10_index": gs.get("i10_index"),
    }


async def resolve_researcher(
    name: Optional[str] = None,
    scopus_id: Optional[str] = None,
    google_scholar_id: Optional[str] = None,
    orcid: Optional[str] = None,
) -> Optional[dict]:
    """Resolve a researcher's profile from any combination of identifiers.

    Tries identifiers in order of reliability: ORCID → name → Google Scholar
    → Scopus. The first to return a profile with an ``s2_id`` wins, since
    the rest of the pipeline needs an S2 id for citation-graph queries.
    """
    if orcid:
        profile = await fetch_by_orcid(orcid)
        if profile and profile.get("s2_id"):
            return profile
        if profile and not name:
            # ORCID gave us a name even without S2 match; promote it
            name = profile.get("name")

    if name:
        profile = await search_by_name(name)
        if profile and profile.get("s2_id"):
            if orcid and not profile.get("orcid"):
                profile["orcid"] = orcid
            return profile

    if google_scholar_id:
        profile = await _resolve_via_google_scholar(google_scholar_id)
        if profile and profile.get("s2_id"):
            return profile
        # Even without S2 match, retain GS-only fields for the response
        if profile and not name:
            name = profile.get("name")
            if name:
                retry = await search_by_name(name)
                if retry and retry.get("s2_id"):
                    retry["google_scholar_id"] = google_scholar_id
                    return retry

    if scopus_id:
        profile = await _resolve_via_scopus(scopus_id)
        if profile and name:
            # Use the name we have to look up S2
            s2 = await search_by_name(name)
            if s2 and s2.get("s2_id"):
                return {**profile, **{k: v for k, v in s2.items() if v is not None}}
        if profile:
            return profile  # No s2_id but at least we have Scopus metrics

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
