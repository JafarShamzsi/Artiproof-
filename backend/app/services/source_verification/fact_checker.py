"""
Fact checker — verifies individual claims using Google Fact Check API and Gemini analysis.
"""

import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.gemini import call_gemini
from app.services.source_verification.evidence_retrieval import retrieve_evidence
from app.services.source_verification.language import LanguageResult, language_directive
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, HTTP_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)

VERIFICATION_PROMPT = """You are an expert fact-checker. Verify the following claim and provide your analysis.

CLAIM: "{claim_text}"

CONTEXT FROM ARTICLE: "{context}"

{factcheck_context}

Analyze this claim carefully. Consider:
1. Is this claim factually accurate based on your knowledge?
2. Are there any nuances or misleading aspects?
3. What is the correct version if the claim is wrong or misleading?

Return valid JSON with these fields:
{{
  "verdict": "true" | "false" | "misleading" | "unverified" | "partially_true",
  "confidence": 0.0 to 1.0,
  "explanation": "Detailed explanation of why this verdict was reached",
  "true_version": "The correct information if the claim is false/misleading, or null if true",
  "sources": ["List of source names/URLs that support the verdict"]
}}

Return ONLY the JSON object, no other text."""


@with_retry(max_retries=2, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _fetch_google_factcheck(claim_text: str, language_code: str = "en") -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={
                "query": claim_text[:200],
                "key": settings.GOOGLE_FACTCHECK_API_KEY,
                "languageCode": language_code,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def check_with_google_factcheck(claim_text: str, language_code: str = "en") -> list[dict]:
    """Query Google Fact Check Tools API for existing fact-checks on this claim."""
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        return []

    try:
        data = await _fetch_google_factcheck(claim_text, language_code=language_code)
    except httpx.HTTPStatusError as e:
        # 404/no results is expected for many claims; only log unusual codes.
        if e.response.status_code not in (400, 404):
            logger.warning("Google Fact Check returned %d", e.response.status_code)
        return []
    except (httpx.TimeoutException, httpx.ConnectError):
        logger.warning("Google Fact Check unreachable")
        return []
    except json.JSONDecodeError:
        logger.error("Google Fact Check returned invalid JSON")
        return []

    results = []
    for item in data.get("claims", [])[:3]:
        for review in item.get("claimReview", []):
            results.append({
                "publisher": review.get("publisher", {}).get("name", "Unknown"),
                "url": review.get("url", ""),
                "title": review.get("title", ""),
                "rating": review.get("textualRating", ""),
                "review_date": review.get("reviewDate", ""),
                "claim_text": item.get("text", ""),
            })
    return results


def _earliest_review(factcheck_results: list[dict]) -> dict | None:
    """The most authoritative existing fact-check for a claim: prefer the
    earliest-dated review (ISO dates sort lexicographically), else the first.
    Used to attribute *who independently flagged the claim and when* — grounded
    data, instead of asking an LLM to speculate about a claim's "origin"."""
    reviews = [r for r in factcheck_results if r.get("publisher")]
    if not reviews:
        return None
    dated = [r for r in reviews if r.get("review_date")]
    chosen = min(dated, key=lambda r: r["review_date"]) if dated else reviews[0]
    return {
        "publisher": chosen.get("publisher"),
        "url": chosen.get("url") or None,
        "rating": chosen.get("rating") or None,
        "review_date": chosen.get("review_date") or None,
    }


# Map a fact-checker's free-text rating to a verdict. Order matters: the most
# severe interpretation wins (a "mostly false" rating is treated as false).
_RATING_VERDICTS = (
    (("false", "wrong", "incorrect", "pants on fire", "fake", "fabricated"), "false"),
    (("mislead", "mostly", "half", "mixture", "partly", "exaggerat"), "misleading"),
    (("true", "correct", "accurate", "verified"), "true"),
)


def _rating_to_verdict(rating: str) -> str | None:
    r = (rating or "").lower()
    for keys, verdict in _RATING_VERDICTS:
        if any(k in r for k in keys):
            return verdict
    return None


def _verdict_from_factcheck(factcheck_results: list[dict]) -> "tuple[str, float] | None":
    """A deterministic verdict from existing reputable fact-checks, or None when
    the ratings don't clearly decide. The most severe rating wins; agreement
    across fact-checkers raises confidence."""
    verdicts = [
        v for v in (_rating_to_verdict(r.get("rating", "")) for r in factcheck_results) if v
    ]
    if not verdicts:
        return None
    for severe in ("false", "misleading", "true"):
        if severe in verdicts:
            return severe, round(min(0.95, 0.6 + 0.1 * verdicts.count(severe)), 2)
    return None


def _unverified_confidence(evidence_count: int) -> float:
    """Low confidence for an undecided claim, nudged up slightly when at least
    some reference material was retrieved."""
    return round(0.25 + min(0.15, 0.05 * evidence_count), 2)


async def verify_claim(
    claim_text: str,
    article_context: str = "",
    language: Optional[LanguageResult] = None,
) -> dict:
    """
    Verify a single claim using Google Fact Check API + Gemini analysis.

    When ``language`` is a confident non-English detection, the Google Fact
    Check query uses that language code (was hardcoded to English) and a
    directive is prepended to the Gemini prompt so the explanation is written
    natively. The verdict enum stays English (it's whitelist-validated).

    The verdict is grounded in reference evidence retrieved for the claim
    (Wikipedia, in the document's language); retrieved sources are folded into
    ``sources`` and the passages are returned in ``evidence``.

    Returns dict with: verdict, confidence, explanation, true_version, sources,
    evidence
    """
    # Step 1: Check Google Fact Check API for existing fact-checks, in the
    # document's language when known.
    lang_code = language.code if (language is not None and language.is_known) else "en"
    factcheck_results = await check_with_google_factcheck(claim_text, language_code=lang_code)
    factcheck_review = _earliest_review(factcheck_results)

    # Step 2: Retrieve reference evidence to ground the verdict (Wikipedia, in
    # the document's language). Free, no key, best-effort — [] on any failure.
    evidence = await retrieve_evidence(claim_text, language_code=lang_code)
    evidence_dicts = [
        {"title": e.title, "url": e.url, "snippet": e.snippet, "source": e.source}
        for e in evidence
    ]
    evidence_sources = [{"name": e.title, "url": e.url} for e in evidence]

    context_lines: list[str] = []
    if factcheck_results:
        context_lines.append("Existing fact-checks found for similar claims:")
        for r in factcheck_results:
            context_lines.append(f"  - {r['publisher']}: rated \"{r['rating']}\" — {r['title']}")
    if evidence:
        context_lines.append(
            "Reference evidence retrieved for this claim — ground your verdict in "
            "these sources and cite the ones you rely on:"
        )
        for e in evidence:
            context_lines.append(f"  - {e.title}: {e.snippet} ({e.url})")
    if not context_lines:
        context_lines.append("No existing fact-checks or reference evidence were found for this claim.")
    factcheck_context = "\n".join(context_lines)

    # Step 3: Deterministic short-circuit — a reputable existing fact-check is
    # more reliable than an LLM guess, and skips the (highest-frequency) call.
    decided = _verdict_from_factcheck(factcheck_results)
    if decided is not None:
        verdict, confidence = decided
        top = factcheck_results[0]
        return {
            "verdict": verdict,
            "confidence": confidence,
            "explanation": (
                f"Matches an existing fact-check by {top['publisher']} "
                f"(rated \"{top.get('rating', 'N/A')}\")."
            ),
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results]
            + evidence_sources,
            "evidence": evidence_dicts,
            "factcheck_review": factcheck_review,
        }

    # Step 4: No reputable fact-check decided it. With no LLM we don't guess —
    # return an honest "unverified" with whatever evidence we gathered.
    if not settings.GEMINI_API_KEY:
        return {
            "verdict": "unverified",
            "confidence": _unverified_confidence(len(evidence)),
            "explanation": "No reputable fact-check decided this claim and AI verification is not configured.",
            "true_version": None,
            "sources": evidence_sources,
            "evidence": evidence_dicts,
            "factcheck_review": factcheck_review,
        }

    # Step 5: LLM reasoning for the genuinely-undecided residue.
    context_snippet = article_context[:500] if article_context else "No additional context available."

    try:
        directive = language_directive(language, task="verify the claim above")
        raw = await _call_gemini_verify(
            directive
            + VERIFICATION_PROMPT.format(
                claim_text=claim_text,
                context=context_snippet,
                factcheck_context=factcheck_context,
            )
        )
    except Exception as e:
        logger.error("Gemini verify call failed: %s", type(e).__name__)
        return {
            "verdict": "unverified",
            "confidence": _unverified_confidence(len(evidence)),
            "explanation": "Verification service unavailable.",
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results] + evidence_sources,
            "evidence": evidence_dicts,
            "factcheck_review": factcheck_review,
        }

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini fact-check response")
        return {
            "verdict": "unverified",
            "confidence": _unverified_confidence(len(evidence)),
            "explanation": "AI analysis returned unparseable results.",
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results] + evidence_sources,
            "evidence": evidence_dicts,
            "factcheck_review": factcheck_review,
        }

    sources = result.get("sources", [])
    if isinstance(sources, list):
        normalized = []
        for s in sources:
            if isinstance(s, str):
                normalized.append({"name": s, "url": ""})
            elif isinstance(s, dict):
                normalized.append(s)
        sources = normalized
    else:
        sources = []
    for r in factcheck_results:
        sources.append({"name": r["publisher"], "url": r["url"]})
    sources.extend(evidence_sources)

    valid_verdicts = {"true", "false", "misleading", "unverified", "partially_true"}
    verdict = result.get("verdict", "unverified")
    if verdict not in valid_verdicts:
        verdict = "unverified"

    # Calibrate the model's self-reported confidence: corroborating independent
    # sources raise it; an "unverified" verdict is capped (we couldn't decide).
    confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    if verdict == "unverified":
        confidence = min(confidence, 0.5)
    else:
        confidence = min(0.97, confidence + 0.05 * len(factcheck_results) + 0.03 * len(evidence))

    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "explanation": str(result.get("explanation", "Analysis completed.")),
        "true_version": result.get("true_version"),
        "sources": sources[:10],
        "evidence": evidence_dicts,
        "factcheck_review": factcheck_review,
    }


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini_verify(prompt: str) -> str:
    return await call_gemini(
        prompt,
        operation="fact_checker",
        temperature=0.1,
        max_output_tokens=2048,
    )
