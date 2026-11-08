"""AI content detection — per-paragraph probability the text is AI-generated.

The primary path is a deterministic **statistical/stylometric** detector — no
model, no network: it looks at sentence-length uniformity (burstiness), n-gram
repetition, and (for English) formulaic transitions + the absence of
contractions. AI text tends to be flatter: uniform sentence lengths, repeated
n-grams, heavy formal transitions, no contractions.

Two enhancements are OFF by default (deterministic-first):
  * ``AI_DETECT_PERPLEXITY`` blends in a small-LM perplexity signal (needs the
    optional transformers/torch extras; a no-op when they're absent).
  * ``AI_DETECT_LLM_CROSSCHECK`` also runs the LLM and blends its scores in.
"""

import json
import logging
import re
from typing import Optional

from app.config import settings
from app.services.gemini import call_gemini
from app.services.source_verification.language import LanguageResult, language_directive
from app.services.source_verification.perplexity import perplexity_ai_signal
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


# ─── Statistical detector (primary, deterministic) ─────────────────────────

# English-only cues — only applied for English text (gated by english_signals).
_TRANSITIONS = {
    "however", "furthermore", "moreover", "additionally", "consequently",
    "nevertheless", "therefore", "thus", "in conclusion",
}
_CONTRACTIONS = {
    "don't", "can't", "won't", "isn't", "aren't", "it's", "i'm", "we're",
    "they're", "didn't", "doesn't",
}
_SENT_SPLIT = re.compile(r"[.!?…]+")


def _paragraph_ai_score(paragraph: str, english_signals: bool) -> float:
    """Stylometric AI-likelihood for one paragraph, in [0, 1]. Baseline 0.5;
    signals push up (more AI-like) or down (more human)."""
    words = paragraph.split()
    wc = len(words)
    score = 0.5

    # Burstiness: AI text has low sentence-length variance (language-agnostic).
    sent_lens = [len(s.split()) for s in _SENT_SPLIT.split(paragraph) if s.strip()]
    if len(sent_lens) >= 3:
        mean = sum(sent_lens) / len(sent_lens)
        if mean > 0:
            std = (sum((x - mean) ** 2 for x in sent_lens) / len(sent_lens)) ** 0.5
            cv = std / mean
            if cv < 0.25:
                score += 0.18
            elif cv < 0.45:
                score += 0.08
            elif cv > 0.85:
                score -= 0.12

    # n-gram repetition: AI text reuses bigrams more (language-agnostic).
    if wc >= 20:
        lowered = [w.lower() for w in words]
        bigrams = list(zip(lowered, lowered[1:]))
        if bigrams:
            rep = 1 - len(set(bigrams)) / len(bigrams)
            if rep > 0.20:
                score += 0.12
            elif rep > 0.12:
                score += 0.06
            elif rep < 0.04:
                score -= 0.05

    # English-only cues — skipped for confident non-English text so a naturally
    # human Russian/Azerbaijani paragraph isn't scored AI-like for lacking them.
    if english_signals:
        trans = sum(1 for w in words if w.lower().rstrip(",.:;") in _TRANSITIONS)
        if wc > 0 and trans / wc > 0.02:
            score += 0.1
        if wc > 30 and not any(w.lower() in _CONTRACTIONS for w in words):
            score += 0.05

    return max(0.0, min(1.0, score))


def _statistical_detection(paragraphs: list[str], english_signals: bool = True) -> list[dict]:
    """Deterministic stylometric AI-likelihood per paragraph (the primary path)."""
    return [
        {
            "paragraph_index": i,
            "paragraph_text": p,
            "ai_probability": round(_paragraph_ai_score(p, english_signals), 4),
            "detection_method": "statistical",
        }
        for i, p in enumerate(paragraphs)
    ]


def _strip_code_fences(raw: str) -> str:
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()
    return raw


# ─── Optional LLM cross-check ──────────────────────────────────────────────


async def _llm_detection(
    capped: list[str],
    language: Optional[LanguageResult],
    warnings: Optional[list],
) -> Optional[dict]:
    """Per-paragraph AI scores from the LLM as ``{index: score}``, or None on
    any failure (so the caller keeps the statistical scores)."""
    formatted = "\n\n".join(f"[Paragraph {i}]: {p[:500]}" for i, p in enumerate(capped))
    try:
        directive = language_directive(
            language, task="estimate the AI-generation probability of each paragraph"
        )
        raw = await _call_gemini(directive + DETECTION_PROMPT.format(paragraphs=formatted))
    except Exception as e:
        logger.error("AI detection cross-check call failed: %s", type(e).__name__)
        if warnings is not None:
            warnings.append(
                {"type": "ai_crosscheck_failed", "module": "ai_detector", "error": type(e).__name__}
            )
        return None

    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        logger.error("Failed to parse AI detection cross-check response")
        return None
    if not isinstance(data, list):
        return None

    out: dict[int, float] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        idx = item.get("index", -1)
        if isinstance(idx, int) and 0 <= idx < len(capped):
            out[idx] = max(0.0, min(1.0, float(item.get("ai_probability", 0.5))))
    return out or None


async def detect_ai_content(
    text: str,
    warnings: Optional[list] = None,
    language: Optional[LanguageResult] = None,
) -> list[dict]:
    """Per-paragraph AI-likelihood. Deterministic statistical primary, with
    optional perplexity + LLM blends (both off by default).

    Returns list of dicts with: paragraph_index, paragraph_text, ai_probability,
    detection_method.
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

    # English-only cues only make sense for English; skip for confident
    # non-English text.
    english_signals = language is None or not language.is_known

    # Primary: deterministic statistical detection (no key, no network).
    results = _statistical_detection(capped, english_signals=english_signals)

    # Optional: blend a perplexity-model signal (off by default; no-op if the
    # optional deps aren't installed).
    if settings.AI_DETECT_PERPLEXITY:
        for r in results:
            sig = perplexity_ai_signal(r["paragraph_text"])
            if sig is not None:
                r["ai_probability"] = round((r["ai_probability"] + sig) / 2, 4)
                r["detection_method"] = "statistical+perplexity"

    # Optional: blend an LLM cross-check (off by default).
    if settings.AI_DETECT_LLM_CROSSCHECK and settings.GEMINI_API_KEY:
        llm = await _llm_detection(capped, language, warnings)
        if llm:
            for r in results:
                ls = llm.get(r["paragraph_index"])
                if ls is not None:
                    r["ai_probability"] = round((r["ai_probability"] + ls) / 2, 4)
                    r["detection_method"] = (
                        r["detection_method"] + "+llm"
                        if "llm" not in r["detection_method"]
                        else r["detection_method"]
                    )

    return results
