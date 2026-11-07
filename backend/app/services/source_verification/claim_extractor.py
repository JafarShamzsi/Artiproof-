"""
Claim extractor — uses Gemini to break article text into individual verifiable claims.
"""

import json
import logging

import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

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
  {
    "claim_text": "Global temperatures rose by 1.5°C since pre-industrial times",
    "position": {"start": 245, "end": 310},
    "category": "scientific"
  }
]

ARTICLE TEXT:
---
{text}
---

Return ONLY the JSON array, no other text."""


async def extract_claims(text: str) -> list[dict]:
    """
    Extract verifiable factual claims from article text using Gemini.

    Returns list of dicts with keys: claim_text, position, category
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning empty claims")
        return []

    if len(text.strip()) < 50:
        return []

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Truncate very long texts to stay within token limits
    truncated = text[:15000]

    try:
        response = await model.generate_content_async(
            EXTRACTION_PROMPT.format(text=truncated),
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )

        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

        claims = json.loads(raw)

        if not isinstance(claims, list):
            logger.error("Gemini returned non-list for claims: %s", type(claims))
            return []

        # Validate structure
        validated = []
        for c in claims:
            if isinstance(c, dict) and "claim_text" in c:
                validated.append({
                    "claim_text": str(c["claim_text"]),
                    "position": c.get("position", {"start": 0, "end": 0}),
                    "category": c.get("category", "other"),
                })
        return validated[:15]

    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini claims response as JSON")
        return []
    except Exception:
        logger.exception("Claim extraction failed")
        return []
