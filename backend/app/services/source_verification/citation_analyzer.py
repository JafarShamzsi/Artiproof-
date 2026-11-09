"""
Citation analyzer — checks citations for accessibility, retractions, and credibility.
"""

import asyncio
import logging
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

from app.config import settings
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, HTTP_RETRY_EXCEPTIONS, with_retry
from app.utils.public_http import fetch_public

logger = logging.getLogger(__name__)


_client: "genai.Client | None" = None


def _gemini_client() -> "genai.Client | None":
    """Lazy module-level singleton — one Client per process, not per call."""
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# Cap how often we ask Gemini for an alternative — only retracted / inaccessible
# citations qualify, and even then we keep the prompt short.
_SUGGEST_ALTERNATIVE_PROMPT = (
    "A citation in a research article has been flagged as {issue}. "
    "Suggest one alternative that is reputable, accessible, and on the same "
    "topic. Reply with one short sentence (under 25 words). If you can't "
    "confidently suggest one, reply exactly: NONE.\n\n"
    "Original citation: \"{citation}\"\n"
)


@with_retry(max_retries=1, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _suggest_alternative_via_gemini(citation_text: str, issue: str) -> str | None:
    """Best-effort short alternative suggestion from Gemini. None on failure."""
    if not settings.GEMINI_API_KEY or not citation_text:
        return None

    client = _gemini_client()
    if client is None:
        return None

    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=_SUGGEST_ALTERNATIVE_PROMPT.format(
                issue=issue, citation=citation_text[:200]
            ),
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=120,
            ),
        )
        text = (response.text or "").strip()
        if not text or text.upper().startswith("NONE"):
            return None
        # Strip any quotes/markdown the model might add
        if text.startswith(("\"", "'")) and text.endswith(("\"", "'")):
            text = text[1:-1].strip()
        return text[:240] or None
    except Exception:
        logger.debug("Alternative-citation suggestion failed", exc_info=True)
        return None

# Known high-credibility domains
HIGH_CREDIBILITY_DOMAINS = {
    "nature.com", "science.org", "thelancet.com", "nejm.org",
    "bmj.com", "cell.com", "pnas.org", "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov", "scholar.google.com",
    "doi.org", "springer.com", "wiley.com", "elsevier.com",
    "ieee.org", "acm.org", "reuters.com", "apnews.com",
    "bbc.com", "bbc.co.uk", "nytimes.com", "washingtonpost.com",
    "who.int", "cdc.gov", "nih.gov", "europa.eu",
}

LOW_CREDIBILITY_DOMAINS = {
    "infowars.com", "naturalnews.com", "beforeitsnews.com",
    "breitbart.com", "zerohedge.com", "thegatewaypundit.com",
}


@with_retry(max_retries=2, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _head_request(url: str) -> int:
    return (await fetch_public(url, method="HEAD")).status_code


async def check_url_accessible(url: str) -> bool:
    """Check if a URL is accessible via HEAD request."""
    try:
        return (await _head_request(url)) < 400
    except httpx.RequestError:
        return False
    except httpx.HTTPStatusError:
        return False
    except httpx.InvalidURL:
        return False


@with_retry(max_retries=2, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _fetch_crossref(doi: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": f"ArtiProof/1.0 (mailto:{settings.CONTACT_EMAIL})"},
        )
        resp.raise_for_status()
        return resp.json()


@with_retry(max_retries=2, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _fetch_openalex(doi: str) -> dict:
    """OpenAlex tracks retractions independently and covers a broader set
    of venues than CrossRef alone — particularly relevant for non-English
    and Eastern-European publications that are under-represented in
    CrossRef's `update-to` retraction records.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # OpenAlex politeness: include a `mailto` query param to land in
        # the polite pool (higher rate limits, priority queue).
        resp = await client.get(
            f"https://api.openalex.org/works/https://doi.org/{doi}",
            params={"mailto": settings.CONTACT_EMAIL},
            headers={"User-Agent": f"ArtiProof/1.0 (mailto:{settings.CONTACT_EMAIL})"},
        )
        resp.raise_for_status()
        return resp.json()


def _normalize_doi(doi: str) -> str:
    """Strip common DOI URL wrappers so downstream APIs see a bare DOI."""
    doi = doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]
    elif doi.startswith("doi:"):
        doi = doi[4:]
    return doi


async def check_retraction_crossref(doi: str) -> bool:
    """Check if a DOI has been retracted via CrossRef API."""
    if not doi:
        return False

    doi = _normalize_doi(doi)

    try:
        data = await _fetch_crossref(doi)
    except httpx.HTTPStatusError as e:
        # 404 = unknown DOI; not a retraction signal but not an error either
        if e.response.status_code != 404:
            logger.debug("CrossRef returned %d for DOI %s", e.response.status_code, doi)
        return False
    except (httpx.TimeoutException, httpx.ConnectError):
        logger.debug("CrossRef unreachable for DOI %s", doi)
        return False

    message = data.get("message", {})
    update_to = message.get("update-to", [])
    for update in update_to:
        if update.get("type") == "retraction":
            return True
    titles = message.get("title", [])
    for t in titles:
        if "retract" in t.lower():
            return True
    return False


async def check_retraction_openalex(doi: str) -> bool:
    """Check if a DOI has been retracted via OpenAlex.

    OpenAlex exposes ``is_retracted`` directly on the work object and
    pulls retraction signals from PubMed, Retraction Watch, and publisher
    notices — covering DOIs CrossRef's ``update-to`` graph misses.
    """
    if not doi:
        return False

    doi = _normalize_doi(doi)

    try:
        data = await _fetch_openalex(doi)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.debug("OpenAlex returned %d for DOI %s", e.response.status_code, doi)
        return False
    except (httpx.TimeoutException, httpx.ConnectError):
        logger.debug("OpenAlex unreachable for DOI %s", doi)
        return False

    return bool(data.get("is_retracted"))


async def check_retraction(doi: str) -> tuple[bool, list[str]]:
    """Cross-reference retraction status across all available databases.

    Returns ``(is_retracted, sources)`` where ``sources`` lists the
    databases that flagged the DOI. A DOI is treated as retracted when
    ANY source flags it — the false-positive risk is lower than the
    cost of missing a real retraction.

    The two checks run in parallel because they hit independent APIs;
    a single sequential pass added 200-400ms per citation to the
    pipeline at the same overall reliability.
    """
    if not doi:
        return False, []

    crossref_result, openalex_result = await asyncio.gather(
        check_retraction_crossref(doi),
        check_retraction_openalex(doi),
        return_exceptions=True,
    )

    sources: list[str] = []
    if isinstance(crossref_result, bool) and crossref_result:
        sources.append("CrossRef")
    if isinstance(openalex_result, bool) and openalex_result:
        sources.append("OpenAlex")

    return bool(sources), sources


def _extract_doi(url: str) -> str | None:
    """Try to extract a DOI from a URL."""
    if "doi.org/" in url:
        return url.split("doi.org/", 1)[1].split("?")[0]
    return None


def _score_domain(url: str) -> float:
    """Score a citation's credibility based on its domain."""
    try:
        domain = urlparse(url).netloc.lower()
        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return 50.0

    if domain in HIGH_CREDIBILITY_DOMAINS:
        return 90.0
    if domain in LOW_CREDIBILITY_DOMAINS:
        return 15.0
    if domain.endswith(".gov") or domain.endswith(".edu"):
        return 85.0
    if domain.endswith(".org"):
        return 65.0
    if domain.endswith(".ac.uk") or domain.endswith(".edu.au"):
        return 80.0

    return 50.0  # Unknown domain, neutral score


async def analyze_citation(citation: dict) -> dict:
    """
    Analyze a single citation for accessibility, retraction status, and credibility.

    Input dict should have: text, url
    Returns dict with: original_citation, citation_url, is_accessible, is_retracted,
                        credibility_score, issues, suggested_alternative
    """
    url = citation.get("url", "")
    text = citation.get("text", "")

    issues = []

    # Check accessibility
    is_accessible = True
    if url:
        is_accessible = await check_url_accessible(url)
        if not is_accessible:
            issues.append("Source URL could not be reached by this check; it may still be accessible elsewhere")

    # Check retraction status across both CrossRef and OpenAlex.
    # Surfacing *which* database flagged it lets an editor or integrity
    # officer trace the finding back to source — a critical defensibility
    # property the previous CrossRef-only check couldn't offer.
    is_retracted = False
    retraction_sources: list[str] = []
    doi = _extract_doi(url) if url else None
    if doi:
        is_retracted, retraction_sources = await check_retraction(doi)
        if is_retracted:
            attribution = (
                f" (per {', '.join(retraction_sources)})" if retraction_sources else ""
            )
            issues.append(
                f"This paper has been RETRACTED{attribution} — "
                "it should not be cited as reliable"
            )

    # Score credibility
    credibility_score = 50.0
    if url:
        credibility_score = _score_domain(url)

    if is_retracted:
        credibility_score = max(0.0, credibility_score - 60)
    if not is_accessible:
        credibility_score = max(0.0, credibility_score - 20)

    # Flag low-credibility sources
    if url:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain in LOW_CREDIBILITY_DOMAINS:
            issues.append(f"Source domain ({domain}) has low credibility rating")

    suggested_alternative: str | None = None
    if is_retracted:
        suggested_alternative = await _suggest_alternative_via_gemini(text, "retracted")
    elif not is_accessible:
        suggested_alternative = await _suggest_alternative_via_gemini(text, "inaccessible")

    return {
        "original_citation": text,
        "citation_url": url or None,
        "is_accessible": is_accessible,
        "is_retracted": is_retracted,
        "retraction_sources": retraction_sources if is_retracted else [],
        "credibility_score": credibility_score,
        "issues": issues if issues else None,
        "suggested_alternative": suggested_alternative,
    }


async def analyze_all_citations(citations: list[dict], warnings: list | None = None) -> list[dict]:
    """Analyze a batch of citations in parallel.

    Cap at 20 to avoid hammering external APIs. Each per-citation analysis
    has its own retry/backoff via the underlying HTTP helpers, so running
    them concurrently is safe.
    """
    if len(citations) > 20 and warnings is not None:
        warnings.append({
            "type": "citations_capped",
            "module": "citation_analyzer",
            "total": len(citations),
            "analyzed": 20,
        })

    capped = citations[:20]
    raw_results = await asyncio.gather(
        *[analyze_citation(c) for c in capped],
        return_exceptions=True,
    )

    results: list[dict] = []
    for cit, r in zip(capped, raw_results):
        if isinstance(r, Exception):
            logger.warning("Citation analysis failed for %s: %s", cit.get("url"), type(r).__name__)
            if warnings is not None:
                warnings.append({
                    "type": "citation_analysis_failed",
                    "module": "citation_analyzer",
                    "url": cit.get("url"),
                    "error": type(r).__name__,
                })
            continue
        results.append(r)
    return results
