"""
Fact checker — verifies individual claims using Google Fact Check API and Gemini analysis.
"""

import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.gemini import call_gemini
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
                "claim_text": item.get("text", ""),
            })
    return results


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

    Returns dict with: verdict, confidence, explanation, true_version, sources
    """
    # Step 1: Check Google Fact Check API for existing fact-checks, in the
    # document's language when known.
    lang_code = language.code if (language is not None and language.is_known) else "en"
    factcheck_results = await check_with_google_factcheck(claim_text, language_code=lang_code)

    factcheck_context = ""
    if factcheck_results:
        lines = ["Existing fact-checks found for similar claims:"]
        for r in factcheck_results:
            lines.append(f"  - {r['publisher']}: rated \"{r['rating']}\" — {r['title']}")
        factcheck_context = "\n".join(lines)
    else:
        factcheck_context = "No existing fact-checks were found for this claim."

    # Step 2: Use Gemini for deeper analysis
    if not settings.GEMINI_API_KEY:
        # If no API key, use fact-check results only
        if factcheck_results:
            rating = factcheck_results[0].get("rating", "").lower()
            verdict = "unverified"
            if any(w in rating for w in ["true", "correct", "accurate"]):
                verdict = "true"
            elif any(w in rating for w in ["false", "wrong", "incorrect", "pants on fire"]):
                verdict = "false"
            elif any(w in rating for w in ["mislead", "mostly", "half", "mixture"]):
                verdict = "misleading"
            return {
                "verdict": verdict,
                "confidence": 0.6,
                "explanation": f"Based on fact-check by {factcheck_results[0]['publisher']}: {factcheck_results[0].get('rating', 'N/A')}",
                "true_version": None,
                "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results],
            }
        return {
            "verdict": "unverified",
            "confidence": 0.3,
            "explanation": "Unable to verify — no API key configured and no existing fact-checks found.",
            "true_version": None,
            "sources": [],
        }

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
            "confidence": 0.2,
            "explanation": "Verification service unavailable.",
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results],
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
            "confidence": 0.3,
            "explanation": "AI analysis returned unparseable results.",
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results],
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

    valid_verdicts = {"true", "false", "misleading", "unverified", "partially_true"}
    verdict = result.get("verdict", "unverified")
    if verdict not in valid_verdicts:
        verdict = "unverified"

    return {
        "verdict": verdict,
        "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.5)))),
        "explanation": str(result.get("explanation", "Analysis completed.")),
        "true_version": result.get("true_version"),
        "sources": sources[:10],
    }


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini_verify(prompt: str) -> str:
    return await call_gemini(
        prompt,
        operation="fact_checker",
        temperature=0.1,
        max_output_tokens=2048,
    )
