"""Topic relevance — does a paper's subject match where it was published?

Previously this asked Gemini to score each (title, venue) pair. That's an
LLM guess over two short strings (and venue names like "Nature" carry no
topic). This version is deterministic and grounded in **OpenAlex** topic data:

- every OpenAlex *work* carries weighted ``concepts``;
- every OpenAlex *source* (venue) carries ``x_concepts`` — the topics its
  papers typically cover.

The score is the fraction of a paper's concept-weight that its venue routinely
covers. Papers without a DOI or without OpenAlex concept data are left unscored
(``None``) and excluded from the integrity average — we don't guess. No LLM.
"""

import asyncio
import logging

import httpx

from app.config import settings
from app.utils.retry import HTTP_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)

_OPENALEX = "https://api.openalex.org"
_MAX_CONCURRENCY = 6
# A venue concept must be at least this prominent to count as "typical" of it.
_SOURCE_CONCEPT_MIN_SCORE = 0.05


def _normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


@with_retry(max_retries=1, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _openalex_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_OPENALEX}{path}",
            params={"mailto": settings.CONTACT_EMAIL},
            headers={"User-Agent": f"ArtiProof/1.0 (mailto:{settings.CONTACT_EMAIL})"},
        )
        resp.raise_for_status()
        return resp.json()


def _concept_overlap(work_concepts: list[dict], source_concepts: list[dict]) -> float | None:
    """Fraction of the paper's concept-weight covered by the venue's typical
    concepts. ``None`` when the paper has no usable concepts."""
    weighted = [
        (c.get("id"), float(c.get("score") or 0.0))
        for c in work_concepts
        if c.get("id")
    ]
    weighted = [(cid, s) for cid, s in weighted if s > 0]
    total = sum(s for _, s in weighted)
    if not weighted or total <= 0:
        return None

    venue_ids = {
        c.get("id")
        for c in source_concepts
        if c.get("id") and float(c.get("score") or 0.0) >= _SOURCE_CONCEPT_MIN_SCORE
    }
    if not venue_ids:
        return None

    matched = sum(s for cid, s in weighted if cid in venue_ids)
    return max(0.0, min(1.0, matched / total))


async def _fetch_source_concepts(source_id: str) -> list[dict]:
    """Fetch a venue's typical concepts (``x_concepts``). ``[]`` on failure."""
    try:
        sid = str(source_id).rsplit("/", 1)[-1]
        src = await _openalex_get(f"/sources/{sid}")
        return src.get("x_concepts") or []
    except Exception:
        logger.debug("OpenAlex source lookup failed for %s", source_id, exc_info=True)
        return []


async def _score_paper(doi: str, source_cache: dict) -> float | None:
    """Score one paper via OpenAlex. ``None`` when it can't be grounded."""
    try:
        work = await _openalex_get(f"/works/https://doi.org/{_normalize_doi(doi)}")
    except Exception:
        logger.debug("OpenAlex work lookup failed for DOI %s", doi, exc_info=True)
        return None

    work_concepts = work.get("concepts") or []
    source = (work.get("primary_location") or {}).get("source") or {}
    source_id = source.get("id")
    if not work_concepts or not source_id:
        return None

    # Single-flight venue cache: a researcher reuses the same handful of venues
    # across many papers; concurrent papers sharing a venue await one fetch.
    if source_id not in source_cache:
        source_cache[source_id] = asyncio.ensure_future(_fetch_source_concepts(source_id))
    x_concepts = await source_cache[source_id]

    return _concept_overlap(work_concepts, x_concepts)


async def analyze_topic_relevance(publications: list[dict]) -> list[dict]:
    """Set ``topic_match_score`` (0..1, or ``None``) on each publication via
    OpenAlex concept overlap. Deterministic — no LLM."""
    source_cache: dict = {}
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def _run(pub: dict) -> None:
        doi = pub.get("doi")
        if not doi:
            pub["topic_match_score"] = None
            return
        async with sem:
            pub["topic_match_score"] = await _score_paper(doi, source_cache)

    await asyncio.gather(*[_run(p) for p in publications], return_exceptions=True)

    for p in publications:
        p.setdefault("topic_match_score", None)
    return publications
