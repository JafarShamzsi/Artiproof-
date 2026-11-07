"""
Citation analyzer — checks citations for accessibility, retractions, and credibility.
"""

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

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


async def check_url_accessible(url: str) -> bool:
    """Check if a URL is accessible via HEAD request."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "ArtiProof/1.0"},
        ) as client:
            resp = await client.head(url)
            return resp.status_code < 400
    except Exception:
        return False


async def check_retraction_crossref(doi: str) -> bool:
    """Check if a DOI has been retracted via CrossRef API."""
    if not doi:
        return False

    # Normalize DOI
    doi = doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]
    elif doi.startswith("doi:"):
        doi = doi[4:]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.crossref.org/works/{doi}",
                headers={"User-Agent": "ArtiProof/1.0 (mailto:info@example.invalid)"},
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            message = data.get("message", {})

            # Check for retraction
            update_to = message.get("update-to", [])
            for update in update_to:
                if update.get("type") == "retraction":
                    return True

            # Check for "Retracted" in title
            titles = message.get("title", [])
            for t in titles:
                if "retract" in t.lower():
                    return True

            return False
    except Exception:
        logger.debug("CrossRef check failed for DOI %s", doi)
        return False


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
            issues.append("Source URL is not accessible (broken link or removed)")

    # Check retraction status
    is_retracted = False
    doi = _extract_doi(url) if url else None
    if doi:
        is_retracted = await check_retraction_crossref(doi)
        if is_retracted:
            issues.append("This paper has been RETRACTED — it should not be cited as reliable")

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

    return {
        "original_citation": text,
        "citation_url": url or None,
        "is_accessible": is_accessible,
        "is_retracted": is_retracted,
        "credibility_score": credibility_score,
        "issues": issues if issues else None,
        "suggested_alternative": None,  # TODO: use Gemini to suggest alternatives
    }


async def analyze_all_citations(citations: list[dict]) -> list[dict]:
    """Analyze a batch of citations. Runs sequentially to avoid hammering external APIs."""
    results = []
    for citation in citations[:20]:  # Cap at 20
        result = await analyze_citation(citation)
        results.append(result)
    return results
