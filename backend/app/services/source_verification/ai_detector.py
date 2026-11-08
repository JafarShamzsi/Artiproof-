"""
AI content detector — analyzes each paragraph for probability of being AI-generated.
"""

import json
import logging
import re
from typing import Optional

from app.config import settings
from app.services.gemini import call_gemini
from app.services.source_verification.language import LanguageResult, language_directive
from app.utils.retry import GEMINI_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)

MAX_PARAGRAPHS = 20

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


@with_retry(max_retries=2, exceptions=GEMINI_RETRY_EXCEPTIONS)
async def _call_gemini(prompt: str) -> str:
    return await call_gemini(prompt, operation="ai_detector")


def _split_paragraphs(text: str) -> list[str]:
    """Split text into meaningful paragraphs."""
    raw_paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw_paragraphs:
        p = p.strip()
        if len(p) >= 30:
            paragraphs.append(p)
    return paragraphs


async def detect_ai_content(
    text: str,
    warnings: Optional[list] = None,
    language: Optional[LanguageResult] = None,
) -> list[dict]:
    """Analyze text for AI-generated content, paragraph by paragraph.

    Args:
        text: full article text
        warnings: optional list the caller owns for capturing structured warnings.
        language: optional detected document language. Non-English documents
            get a directive on the Gemini prompt, and the heuristic fallback
            skips its English-only signals (transition words, contractions).

    Returns list of dicts with: paragraph_index, paragraph_text, ai_probability, detection_method
    """
    paragraphs = _split_paragraphs(text)

    if not paragraphs:
        return []

    if len(paragraphs) > MAX_PARAGRAPHS and warnings is not None:
        warnings.append({
            "type": "paragraphs_capped",
            "module": "ai_detector",
            "total": len(paragraphs),
            "analyzed": MAX_PARAGRAPHS,
        })
    capped = paragraphs[:MAX_PARAGRAPHS]

    # English-specific heuristic signals (transition words, contractions) only
    # make sense for English; for a confident non-English language we skip them
    # and lean on the language-agnostic structural signal instead.
    english_signals = language is None or not language.is_known

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning heuristic AI detection")
        if warnings is not None:
            warnings.append({"type": "fallback_heuristic", "module": "ai_detector"})
        return _heuristic_detection(capped, english_signals=english_signals)

    formatted = "\n\n".join(
        f"[Paragraph {i}]: {p[:500]}" for i, p in enumerate(capped)
    )

    try:
        directive = language_directive(language, task="estimate the AI-generation probability of each paragraph")
        raw = await _call_gemini(directive + DETECTION_PROMPT.format(paragraphs=formatted))
    except Exception as e:
        logger.error("AI detection call failed: %s, using heuristic", type(e).__name__)
        if warnings is not None:
            warnings.append({
                "type": "fallback_heuristic",
                "module": "ai_detector",
                "error": type(e).__name__,
            })
        return _heuristic_detection(capped, english_signals=english_signals)

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()

    try:
        results_raw = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini AI detection response")
        if warnings is not None:
            warnings.append({"type": "invalid_json", "module": "ai_detector"})
        return _heuristic_detection(capped, english_signals=english_signals)

    if not isinstance(results_raw, list):
        return _heuristic_detection(capped, english_signals=english_signals)

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


def _heuristic_detection(paragraphs: list[str], english_signals: bool = True) -> list[dict]:
    """Simple heuristic fallback for AI detection when Gemini is unavailable.

    ``english_signals`` gates the English-specific cues (transition words,
    contractions). For confident non-English text we skip those and rely only
    on the language-agnostic sentence-length-uniformity signal, so a naturally
    human Russian/Azerbaijani paragraph isn't scored as "more AI-like" purely
    for lacking English markers.
    """
    results = []
    for i, p in enumerate(paragraphs):
        words = p.split()
        word_count = len(words)

        score = 0.5

        sentences = re.split(r"[.!?]+", p)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        if sentence_lengths:
            avg_len = sum(sentence_lengths) / len(sentence_lengths)
            if 15 <= avg_len <= 25 and len(sentence_lengths) > 2:
                variance = sum((l - avg_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
                if variance < 20:
                    score += 0.15

        if english_signals:
            transitions = {"however", "furthermore", "moreover", "additionally", "consequently", "nevertheless", "in conclusion"}
            transition_count = sum(1 for w in words if w.lower().rstrip(",.:;") in transitions)
            if word_count > 0 and transition_count / max(word_count, 1) > 0.02:
                score += 0.1

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
