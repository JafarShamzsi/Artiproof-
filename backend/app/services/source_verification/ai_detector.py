"""
AI content detector — analyzes each paragraph for probability of being AI-generated.
"""

import json
import logging
import re

import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

DETECTION_PROMPT = """You are an AI-generated content detector. Analyze each paragraph below and estimate the probability that it was written by an AI language model (0.0 = definitely human, 1.0 = definitely AI).

Consider these signals:
- Overly uniform sentence length and structure
- Generic phrasing without specific personal voice
- Lack of domain-specific errors humans would make
- Excessive hedging or qualifying language
- Perfect grammar with no colloquialisms
- Formulaic transitions between ideas

PARAGRAPHS (numbered):
{paragraphs}

Return a JSON array with one object per paragraph:
[
  {{"index": 0, "ai_probability": 0.15, "reason": "Contains personal anecdotes and informal tone"}},
  {{"index": 1, "ai_probability": 0.85, "reason": "Uniform structure, generic phrasing"}}
]

Return ONLY the JSON array, no other text."""


def _split_paragraphs(text: str) -> list[str]:
    """Split text into meaningful paragraphs."""
    # Split on double newlines or single newlines followed by a capital letter
    raw_paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw_paragraphs:
        p = p.strip()
        if len(p) >= 30:  # Skip very short fragments
            paragraphs.append(p)
    return paragraphs


async def detect_ai_content(text: str) -> list[dict]:
    """
    Analyze text for AI-generated content, paragraph by paragraph.

    Returns list of dicts with: paragraph_index, paragraph_text, ai_probability, detection_method
    """
    paragraphs = _split_paragraphs(text)

    if not paragraphs:
        return []

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning heuristic AI detection")
        return _heuristic_detection(paragraphs)

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Format paragraphs for the prompt (limit to 20 paragraphs)
    capped = paragraphs[:20]
    formatted = "\n\n".join(
        f"[Paragraph {i}]: {p[:500]}" for i, p in enumerate(capped)
    )

    try:
        response = await model.generate_content_async(
            DETECTION_PROMPT.format(paragraphs=formatted),
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

        results_raw = json.loads(raw)

        if not isinstance(results_raw, list):
            return _heuristic_detection(capped)

        results = []
        for item in results_raw:
            idx = item.get("index", 0)
            if idx < len(capped):
                results.append({
                    "paragraph_index": idx,
                    "paragraph_text": capped[idx],
                    "ai_probability": max(0.0, min(1.0, float(item.get("ai_probability", 0.5)))),
                    "detection_method": "gemini-analysis",
                })

        # Fill in any paragraphs that Gemini skipped
        covered = {r["paragraph_index"] for r in results}
        for i, p in enumerate(capped):
            if i not in covered:
                results.append({
                    "paragraph_index": i,
                    "paragraph_text": p,
                    "ai_probability": 0.5,
                    "detection_method": "gemini-analysis",
                })

        results.sort(key=lambda r: r["paragraph_index"])
        return results

    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini AI detection response")
        return _heuristic_detection(capped)
    except Exception:
        logger.exception("AI detection failed")
        return _heuristic_detection(capped)


def _heuristic_detection(paragraphs: list[str]) -> list[dict]:
    """Simple heuristic fallback for AI detection when Gemini is unavailable."""
    results = []
    for i, p in enumerate(paragraphs):
        words = p.split()
        word_count = len(words)

        score = 0.5  # Start neutral

        # Long, uniform sentences → more likely AI
        sentences = re.split(r"[.!?]+", p)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        if sentence_lengths:
            avg_len = sum(sentence_lengths) / len(sentence_lengths)
            if 15 <= avg_len <= 25 and len(sentence_lengths) > 2:
                variance = sum((l - avg_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
                if variance < 20:  # Very uniform
                    score += 0.15

        # High ratio of transition words → more likely AI
        transitions = {"however", "furthermore", "moreover", "additionally", "consequently", "nevertheless", "in conclusion"}
        transition_count = sum(1 for w in words if w.lower().rstrip(",.:;") in transitions)
        if word_count > 0 and transition_count / max(word_count, 1) > 0.02:
            score += 0.1

        # No contractions or informal language → more likely AI
        contractions = {"don't", "can't", "won't", "isn't", "aren't", "it's", "i'm", "we're", "they're"}
        has_informal = any(w.lower() in contractions for w in words)
        if not has_informal and word_count > 30:
            score += 0.05

        results.append({
            "paragraph_index": i,
            "paragraph_text": p,
            "ai_probability": max(0.0, min(1.0, score)),
            "detection_method": "heuristic-fallback",
        })

    return results
