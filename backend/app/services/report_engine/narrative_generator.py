"""
Narrative generator — uses Gemini to write human-readable report summaries.
"""

import json
import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_client: "genai.Client | None" = None


def _gemini_client() -> "genai.Client | None":
    """Lazy module-level singleton — one Client per process, not per call."""
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client

SOURCE_CHECK_PROMPT = """You are writing an executive summary for a source verification report. Write a clear, professional 3-4 paragraph narrative.

ARTICLE TITLE: {title}
INPUT TYPE: {input_type}
CREDIBILITY SCORE: {credibility_score}/100
AI CONTENT PERCENTAGE: {ai_percentage}%
MISINFORMATION CLAIMS FOUND: {misinfo_count}

CLAIMS ANALYSIS:
{claims_summary}

CITATION ISSUES:
{citation_summary}

Write a concise narrative that:
1. Opens with the overall assessment (credible/concerning/unreliable)
2. Summarizes the key findings from claims analysis
3. Notes any AI content detection results
4. Concludes with citation health and recommendations

Use professional, objective language. No markdown formatting — plain paragraphs only.
Keep it under 400 words."""

RESEARCHER_PROMPT = """You are writing an executive summary for an academic integrity analysis report. Write a clear, professional 3-4 paragraph narrative.

RESEARCHER: {name}
INSTITUTION: {institution}
OFFICIAL H-INDEX: {h_index}
ADJUSTED H-INDEX: {adjusted_h}
OFFICIAL CITATIONS: {citations}
ADJUSTED CITATIONS: {adjusted_citations}
INTEGRITY SCORE: {integrity_score}/100
SELF-CITATION RATE: {self_cite_rate}%
PUBLICATIONS ANALYZED: {pub_count}

INTEGRITY FLAGS:
{flags}

Write a concise narrative that:
1. Opens with the overall integrity assessment
2. Explains what adjustments were made to the metrics and why
3. Describes any citation manipulation patterns found
4. Concludes with an overall recommendation

Use professional, objective language. No markdown formatting — plain paragraphs only.
Keep it under 400 words."""


async def generate_source_check_narrative(check_data: dict) -> str:
    """Generate a narrative summary for a source verification report."""
    claims = check_data.get("claims", [])
    citations = check_data.get("citations", [])

    claims_summary = "No claims analyzed."
    if claims:
        lines = []
        for c in claims[:10]:
            lines.append(f"- \"{c.get('claim_text', '')[:80]}\" — {c.get('verdict', 'unverified').upper()}")
        claims_summary = "\n".join(lines)

    citation_summary = "No citations checked."
    if citations:
        retracted = sum(1 for c in citations if c.get("is_retracted"))
        inaccessible = sum(1 for c in citations if not c.get("is_accessible", True))
        citation_summary = f"{len(citations)} citations checked. {retracted} retracted, {inaccessible} inaccessible."

    prompt = SOURCE_CHECK_PROMPT.format(
        title=check_data.get("input_title") or "Untitled",
        input_type=check_data.get("input_type", "text"),
        credibility_score=check_data.get("overall_credibility_score", 0),
        ai_percentage=check_data.get("ai_content_percentage", 0),
        misinfo_count=check_data.get("misinfo_claims_found", 0),
        claims_summary=claims_summary,
        citation_summary=citation_summary,
    )

    return await _generate(prompt)


async def generate_researcher_narrative(profile_data: dict) -> str:
    """Generate a narrative summary for a researcher integrity report."""
    ring_flags = profile_data.get("citation_ring_flags") or {}
    flags = ring_flags.get("flags", [])
    flags_text = "\n".join(f"- {f}" for f in flags) if flags else "No integrity flags."

    prompt = RESEARCHER_PROMPT.format(
        name=profile_data.get("researcher_name", "Unknown"),
        institution=profile_data.get("institution") or "Unknown",
        h_index=profile_data.get("official_h_index") or "N/A",
        adjusted_h=profile_data.get("adjusted_h_index") or "N/A",
        citations=profile_data.get("official_citation_count") or "N/A",
        adjusted_citations=profile_data.get("adjusted_citation_count") or "N/A",
        integrity_score=profile_data.get("integrity_score") or "N/A",
        self_cite_rate=round((profile_data.get("self_citation_rate") or 0) * 100, 1),
        pub_count=len(profile_data.get("publications", [])),
        flags=flags_text,
    )

    return await _generate(prompt)


async def _generate(prompt: str) -> str:
    """Call Gemini to generate text."""
    if not settings.GEMINI_API_KEY:
        return "Report narrative unavailable — AI service not configured."

    client = _gemini_client()
    if client is None:
        return "Report narrative unavailable — AI service not configured."

    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        return (response.text or "").strip()
    except Exception:
        logger.exception("Narrative generation failed")
        return "Report narrative generation encountered an error."
