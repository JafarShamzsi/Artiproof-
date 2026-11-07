"""
Topic analyzer — checks whether papers are published in journals relevant to their content.
Uses Gemini for NLP similarity analysis.
"""

import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.config import settings
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)

BATCH_SIZE = 15

_client: "genai.Client | None" = None


def _gemini_client() -> "genai.Client | None":
    """Lazy module-level singleton — one Client per process, not per call."""
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

TOPIC_PROMPT = """You are an academic topic relevance analyst. For each paper below, assess how well the paper's topic matches the journal/venue it was published in.

Score each from 0.0 (completely irrelevant to the journal) to 1.0 (perfect match).

PAPERS:
{papers}

Return a JSON array:
[
  {{"index": 0, "topic_match_score": 0.85, "reason": "Machine learning paper in ML journal — good match"}},
  {{"index": 1, "topic_match_score": 0.2, "reason": "Biology paper published in a computer science venue — poor match"}}
]

Return ONLY the JSON array, no other text."""


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini(prompt: str) -> str:
    client = _gemini_client()
    if client is None:
        return ""  # caller already guarded on settings.GEMINI_API_KEY
    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
        ),
    )
    return (response.text or "").strip()


async def _process_batch(batch: list[tuple[int, dict]]) -> list[dict]:
    """Score one batch. Returns list of {index, topic_match_score} dicts.

    `index` is the position within the batch — caller maps it back to the
    original publication index.
    """
    formatted = "\n".join(
        f"[{idx}] Title: \"{p['title']}\" — Journal/Venue: \"{p['journal']}\""
        for idx, (_, p) in enumerate(batch)
    )

    try:
        raw = await _call_gemini(TOPIC_PROMPT.format(papers=formatted))
    except Exception as e:
        logger.error("Topic analysis batch failed: %s", type(e).__name__)
        return []

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()

    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini topic analysis response")
        return []

    if not isinstance(results, list):
        return []
    return results


async def analyze_topic_relevance(publications: list[dict]) -> list[dict]:
    """
    Analyze whether papers are published in topically relevant journals.

    Batches are processed concurrently rather than sequentially.
    """
    papers_with_venue = [
        (i, p) for i, p in enumerate(publications)
        if p.get("journal") and p.get("title")
    ]

    if not papers_with_venue:
        return publications

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, skipping topic analysis")
        for p in publications:
            p["topic_match_score"] = None
        return publications

    batches = [
        papers_with_venue[i:i + BATCH_SIZE]
        for i in range(0, len(papers_with_venue), BATCH_SIZE)
    ]

    batch_results = await asyncio.gather(
        *[_process_batch(b) for b in batches],
        return_exceptions=True,
    )

    for batch, results in zip(batches, batch_results):
        if isinstance(results, Exception):
            logger.warning("Topic batch raised: %s", type(results).__name__)
            continue
        for item in results:
            idx_in_batch = item.get("index", -1)
            if 0 <= idx_in_batch < len(batch):
                orig_idx = batch[idx_in_batch][0]
                publications[orig_idx]["topic_match_score"] = max(
                    0.0, min(1.0, float(item.get("topic_match_score", 0.5)))
                )

    for p in publications:
        if "topic_match_score" not in p:
            p["topic_match_score"] = None

    return publications
