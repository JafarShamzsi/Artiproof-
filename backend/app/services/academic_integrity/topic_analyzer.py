"""
Topic analyzer — checks whether papers are published in journals relevant to their content.
Uses Gemini for NLP similarity analysis.
"""

import json
import logging

import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

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


async def analyze_topic_relevance(publications: list[dict]) -> list[dict]:
    """
    Analyze whether papers are published in topically relevant journals.

    Takes a list of publication dicts (title, journal, year).
    Returns list with added topic_match_score field.
    """
    # Filter to papers that have both title and journal
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

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Process in batches of 15
    batch_size = 15
    for batch_start in range(0, len(papers_with_venue), batch_size):
        batch = papers_with_venue[batch_start:batch_start + batch_size]

        formatted = "\n".join(
            f"[{idx}] Title: \"{p['title']}\" — Journal/Venue: \"{p['journal']}\""
            for idx, (_, p) in enumerate(batch)
        )

        try:
            response = await model.generate_content_async(
                TOPIC_PROMPT.format(papers=formatted),
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

            results = json.loads(raw)
            if isinstance(results, list):
                for item in results:
                    idx = item.get("index", -1)
                    if 0 <= idx < len(batch):
                        orig_idx = batch[idx][0]
                        publications[orig_idx]["topic_match_score"] = max(
                            0.0, min(1.0, float(item.get("topic_match_score", 0.5)))
                        )

        except json.JSONDecodeError:
            logger.error("Failed to parse Gemini topic analysis response")
        except Exception:
            logger.exception("Topic analysis batch failed")

    # Fill in missing scores
    for p in publications:
        if "topic_match_score" not in p:
            p["topic_match_score"] = None

    return publications
