"""
Origin tracer — traces the origin and spread of misinformation claims using Gemini.
"""

import json
import logging

import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

TRACE_PROMPT = """You are a misinformation analyst. A claim has been identified as FALSE or MISLEADING. Trace its likely origin and spread.

CLAIM: "{claim_text}"
VERDICT: {verdict}
EXPLANATION: {explanation}

Based on your knowledge, analyze:
1. Where did this false claim likely originate? (platform, publication, or individual)
2. When was it first seen or popularized?
3. How did it spread? Which platforms amplified it?
4. What made it convincing or viral?

Return valid JSON:
{{
  "origin_platform": "Name of the platform/source where it likely originated",
  "first_seen": "Approximate date or time period when first observed",
  "spread_path": [
    {{"platform": "Platform name", "description": "How it spread there", "approximate_date": "When"}}
  ],
  "amplification_factors": ["List of factors that helped this spread"],
  "confidence": 0.0 to 1.0
}}

If you cannot determine the origin with reasonable confidence, set confidence below 0.3 and explain in the spread_path.

Return ONLY the JSON object, no other text."""


async def trace_origin(claim_text: str, verdict: str, explanation: str) -> dict | None:
    """
    Trace the origin of a misinformation claim.

    Only runs for claims with verdict "false" or "misleading".
    Returns origin trace dict or None if not applicable / unable to trace.
    """
    if verdict not in ("false", "misleading"):
        return None

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, skipping origin trace")
        return None

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    try:
        response = await model.generate_content_async(
            TRACE_PROMPT.format(
                claim_text=claim_text,
                verdict=verdict,
                explanation=explanation[:500],
            ),
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=2048,
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

        trace = json.loads(raw)

        if not isinstance(trace, dict):
            return None

        return {
            "origin_platform": trace.get("origin_platform", "Unknown"),
            "first_seen": trace.get("first_seen", "Unknown"),
            "spread_path": trace.get("spread_path", []),
            "amplification_factors": trace.get("amplification_factors", []),
            "confidence": max(0.0, min(1.0, float(trace.get("confidence", 0.3)))),
        }

    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini origin trace response")
        return None
    except Exception:
        logger.exception("Origin tracing failed")
        return None
