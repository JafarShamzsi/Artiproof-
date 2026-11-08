"""
Claim extractor — uses Gemini to break article text into individual verifiable claims.
"""

import asyncio
import json
import logging
from typing import Optional

from app.config import settings
from app.constants import ANALYSIS_MAX_CLAIMS_TOTAL, ANALYSIS_WINDOW_CONCURRENCY
from app.services.gemini import call_gemini
from app.services.source_verification.chunker import analyzed_chars, chunk_text
from app.services.source_verification.language import LanguageResult, language_directive
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 15000
MAX_CLAIMS = 15

EXTRACTION_PROMPT = """You are a fact-checking assistant. Analyze the following article text and extract all specific, verifiable factual claims.

For each claim, provide:
- claim_text: The exact factual statement being made
- position: Approximate character offset in the original text (start, end)
- category: One of "statistic", "event", "attribution", "scientific", "policy", "historical", "other"

Rules:
- Only extract claims that can be verified against external sources
- Skip opinions, rhetorical questions, and subjective statements
- Each claim should be a single, specific, testable statement
- Extract at most 15 claims (focus on the most important ones)

Return valid JSON array. Example:
[
  {{
    "claim_text": "Global temperatures rose by 1.5C since pre-industrial times",
    "position": {{"start": 245, "end": 310}},
    "category": "scientific"
  }}
]

ARTICLE TEXT:
---
{text}
---

Return ONLY the JSON array, no other text."""


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini(prompt: str) -> str:
    # Delegate to the centralized client so usage_metadata + latency
    # land in gemini_metrics. Returns "" when GEMINI_API_KEY is unset
    # (caller already guarded on this).
    return await call_gemini(prompt, operation="claim_extractor")


async def extract_claims(
    text: str,
    warnings: Optional[list] = None,
    language: Optional[LanguageResult] = None,
) -> list[dict]:
    """Extract verifiable factual claims from article text using Gemini.

    Args:
        text: full article text
        warnings: optional list the caller owns; this function appends
            structured warnings (truncation, fallback, parse failures) so
            the orchestrator can persist them to model_metadata.
        language: optional detected document language. When non-English a
            directive is prepended to the prompt so claims are extracted and
            labelled natively; the EXTRACTION_PROMPT template is unchanged.

    Returns list of dicts with keys: claim_text, position, category
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning empty claims")
        if warnings is not None:
            warnings.append({"type": "missing_gemini_key", "module": "claim_extractor"})
        return []

    if len(text.strip()) < 50:
        return []

    original_length = len(text)
    truncated = text[:MAX_TEXT_CHARS]
    if original_length > MAX_TEXT_CHARS and warnings is not None:
        warnings.append({
            "type": "text_truncated",
            "module": "claim_extractor",
            "original_length": original_length,
            "analyzed_length": MAX_TEXT_CHARS,
        })

    try:
        directive = language_directive(language, task="extract every specific, verifiable factual claim")
        raw = await _call_gemini(directive + EXTRACTION_PROMPT.format(text=truncated))
    except Exception as e:
        # Already retried by the decorator. Log type so we can audit which
        # failure modes happen in prod.
        logger.error("claim extraction call failed: %s", type(e).__name__)
        if warnings is not None:
            warnings.append({
                "type": "claim_extraction_failed",
                "module": "claim_extractor",
                "error": type(e).__name__,
            })
        return []

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()

    try:
        claims = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini claims response as JSON")
        if warnings is not None:
            warnings.append({"type": "invalid_json", "module": "claim_extractor"})
        return []

    if not isinstance(claims, list):
        logger.error("Gemini returned non-list for claims: %s", type(claims))
        if warnings is not None:
            warnings.append({"type": "invalid_shape", "module": "claim_extractor"})
        return []

    validated = []
    for c in claims:
        if isinstance(c, dict) and "claim_text" in c:
            validated.append({
                "claim_text": str(c["claim_text"]),
                "position": c.get("position", {"start": 0, "end": 0}),
                "category": c.get("category", "other"),
            })

    if len(validated) > MAX_CLAIMS and warnings is not None:
        warnings.append({
            "type": "claims_capped",
            "module": "claim_extractor",
            "extracted": len(validated),
            "kept": MAX_CLAIMS,
        })
    return validated[:MAX_CLAIMS]


async def extract_claims_full(
    text: str,
    warnings: Optional[list] = None,
    language: Optional[LanguageResult] = None,
    max_windows: Optional[int] = None,
) -> list[dict]:
    """Extract claims across the WHOLE document via overlapping windows.

    Each window is one ``extract_claims`` LLM call (bounded concurrency, metered
    through the usual chokepoint). Claim ``position`` offsets are corrected back
    to the original document, and near-duplicate claims from the overlaps are
    merged. When the document exceeds the window budget, only the leading
    windows are analyzed and an honest ``text_truncated`` warning records the
    real coverage (analyzed vs total chars) for the coverage badge.

    ``max_windows`` caps how many windows (LLM calls) this analysis may spend;
    ``None`` analyzes every window.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning empty claims")
        if warnings is not None:
            warnings.append({"type": "missing_gemini_key", "module": "claim_extractor"})
        return []

    if len(text.strip()) < 50:
        return []

    chunks = chunk_text(text)
    budget = len(chunks) if max_windows is None else max(1, max_windows)
    analyzed = chunks[:budget]

    if len(chunks) > len(analyzed) and warnings is not None:
        warnings.append({
            "type": "text_truncated",
            "module": "claim_extractor",
            "original_length": len(text),
            "analyzed_length": analyzed_chars(analyzed),
        })

    sem = asyncio.Semaphore(ANALYSIS_WINDOW_CONCURRENCY)

    async def _extract_window(chunk) -> list[dict]:
        async with sem:
            # Per-window warnings are dropped: windows are < MAX_TEXT_CHARS so
            # they never self-truncate, and budget/cap warnings are recorded at
            # the document level above/below.
            claims = await extract_claims(chunk.text, warnings=None, language=language)
        for c in claims:
            pos = c.get("position")
            if isinstance(pos, dict):
                c["position"] = {
                    "start": int(pos.get("start", 0) or 0) + chunk.start,
                    "end": int(pos.get("end", 0) or 0) + chunk.start,
                }
        return claims

    per_window = await asyncio.gather(*[_extract_window(c) for c in analyzed])

    # Merge in document order, de-duplicating near-identical claims from the
    # overlap regions (normalize whitespace + case).
    seen: set[str] = set()
    merged: list[dict] = []
    for claims in per_window:
        for c in claims:
            key = " ".join(str(c.get("claim_text", "")).lower().split())
            if key and key not in seen:
                seen.add(key)
                merged.append(c)

    if len(merged) > ANALYSIS_MAX_CLAIMS_TOTAL and warnings is not None:
        warnings.append({
            "type": "claims_capped",
            "module": "claim_extractor",
            "extracted": len(merged),
            "kept": ANALYSIS_MAX_CLAIMS_TOTAL,
        })
    return merged[:ANALYSIS_MAX_CLAIMS_TOTAL]
