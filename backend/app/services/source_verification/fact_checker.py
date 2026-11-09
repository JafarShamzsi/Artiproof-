"""
Fact checker — verifies individual claims using Google Fact Check API and Gemini analysis.
"""

import json
import logging
import math
from typing import Optional

import httpx

from app.config import settings
from app.services.gemini import call_gemini
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, HTTP_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)


def normalize_factcheck_rating(rating: str) -> str:
    """Interpret known rating labels only; unfamiliar publisher scales abstain."""
    if not isinstance(rating, str):
        return "unverified"
    normalized = " ".join(rating.casefold().split())
    labels = {
        "true": "true", "correct": "true", "accurate": "true",
        "false": "false", "incorrect": "false", "wrong": "false",
        "not true": "false", "inaccurate": "false", "pants on fire": "false",
        "mostly true": "partially_true", "partially true": "partially_true",
        "half true": "partially_true", "half-true": "partially_true",
        "mostly false": "misleading", "misleading": "misleading",
        "mixture": "misleading",
    }
    return labels.get(normalized, "unverified")

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
async def _fetch_google_factcheck(claim_text: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={
                "query": claim_text[:200],
                "key": settings.GOOGLE_FACTCHECK_API_KEY,
                "languageCode": "en",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def check_with_google_factcheck(claim_text: str) -> list[dict]:
    """Query Google Fact Check Tools API for existing fact-checks on this claim."""
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        return []

    try:
        data = await _fetch_google_factcheck(claim_text)
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


async def verify_claim(claim_text: str, article_context: str = "") -> dict:
    """
    Verify a single claim using Google Fact Check API + Gemini analysis.

    Returns dict with: verdict, confidence, explanation, true_version, sources
    """
    # Step 1: Check Google Fact Check API for existing fact-checks
    factcheck_results = await check_with_google_factcheck(claim_text)

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
            verdicts = {
                normalize_factcheck_rating(r.get("rating", ""))
                for r in factcheck_results
            }
            # Search results concern similar claims and can disagree. Never
            # select a reassuring verdict just because that review was first.
            verdict = verdicts.pop() if len(verdicts) == 1 else "unverified"
            return {
                "verdict": verdict,
                "confidence": 0.0 if verdict == "unverified" else 0.6,
                "explanation": (
                    "Existing reviews of similar claims have conflicting or unsupported ratings; manual review is required."
                    if verdict == "unverified" else
                    "Existing reviews of similar claims agree on this rating. Confirm that the reviewed claim matches the submitted claim."
                ),
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
        raw = await _call_gemini_verify(
            VERIFICATION_PROMPT.format(
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
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        confidence = float(result.get("confidence", 0.5))
        if not math.isfinite(confidence):
            raise ValueError("Expected finite confidence")
    except (json.JSONDecodeError, TypeError, ValueError, OverflowError):
        logger.error("Failed to parse Gemini fact-check response")
        return {
            "verdict": "unverified",
            "confidence": 0.3,
            "explanation": "AI analysis returned unparseable results.",
            "true_version": None,
            "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results],
        }

    # Generated verdicts, confidence and URLs are not retrieved evidence. Even
    # FactCheck search results concern *similar* claims, not a validated match.
    # Preserve suggestions as advisory prose without unlocking a credibility score.
    return {
        "verdict": "unverified",
        "confidence": 0.0,
        "explanation": "Advisory model analysis; not verified evidence. " + str(result.get("explanation", "Manual review required.")),
        "true_version": None,
        "sources": [{"name": r["publisher"], "url": r["url"]} for r in factcheck_results][:10],
    }


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini_verify(prompt: str) -> str:
    return await call_gemini(
        prompt,
        operation="fact_checker",
        temperature=0.1,
        max_output_tokens=2048,
    )
