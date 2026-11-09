"""
Narrative generator — uses Gemini to write human-readable report summaries.
"""

import json
import logging

from app.config import settings
from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)

SOURCE_CHECK_PROMPT = """You are writing an executive summary for a source verification report. Write a clear, professional 3-4 paragraph narrative.

ARTICLE TITLE: {title}
INPUT TYPE: {input_type}
CREDIBILITY SCORE: {credibility_score}/100
ASSESSMENT COVERAGE STATUS: {assessment_status}
AI CONTENT PERCENTAGE: {ai_percentage}%
MISINFORMATION CLAIMS FOUND: {misinfo_count}

CLAIMS ANALYSIS:
{claims_summary}

CITATION ISSUES:
{citation_summary}

Write a concise narrative that:
1. Describes recorded findings and the analyzed sample, without certifying overall accuracy
2. Summarizes the key findings from claims analysis
3. Describes AI style estimates separately from factual accuracy, without claiming proof of authorship
4. Notes unverified claims, missing references and inaccessible links as unknowns, not proof of falsehood

A high score does not establish a reliable source or complete verification. Recommend inspection of supporting evidence and coverage.

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

OBSERVED SAMPLE PATTERNS:
{flags}

Write a concise narrative that:
1. Describes the available citation sample and its limitations
2. Explains adjusted metrics as estimates extrapolated from sampled self-citations, not exact recomputations
3. Describes incoming citation concentration without claiming reciprocity, citation rings, intent or misconduct
4. Recommends evidence review without declaring the researcher cleared, exemplary or unreliable

The score is a heuristic, not a validated probability of integrity. Missing findings do not prove a clean record.

Use professional, objective language. No markdown formatting — plain paragraphs only.
Keep it under 400 words."""


async def generate_source_check_narrative(check_data: dict) -> str:
    """Generate a narrative summary for a source verification report."""
    if check_data.get("overall_credibility_score") is None:
        return (
            "Credibility score unavailable: required verification evidence is missing "
            "or a required step failed. Review the available individual findings. "
            "Missing analysis does not establish overall accuracy or inaccuracy."
        )
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
        assessment_status=(check_data.get("score_breakdown") or {}).get("assessment_status", "unknown"),
        ai_percentage=check_data.get("ai_content_percentage", 0),
        misinfo_count=check_data.get("misinfo_claims_found", 0),
        claims_summary=claims_summary,
        citation_summary=citation_summary,
    )

    return await _generate(prompt)


async def generate_researcher_narrative(profile_data: dict) -> str:
    """Generate a narrative summary for a researcher integrity report."""
    if profile_data.get("integrity_score") is None:
        return (
            "Researcher assessment unavailable: citation evidence is missing or incomplete, "
            "or a required analysis step failed. Available publications do not establish "
            "integrity or misconduct. Adjusted metrics and self-citation rate are not assessed."
        )
    ring_flags = profile_data.get("citation_ring_flags") or {}
    flags = ring_flags.get("flags", [])
    flags_text = "\n".join(f"- {f}" for f in flags) if flags else "No listed sample patterns; this does not establish absence of misconduct."

    prompt = RESEARCHER_PROMPT.format(
        name=profile_data.get("researcher_name", "Unknown"),
        institution=profile_data.get("institution") or "Unknown",
        h_index=profile_data.get("official_h_index") if profile_data.get("official_h_index") is not None else "N/A",
        adjusted_h=profile_data.get("adjusted_h_index") if profile_data.get("adjusted_h_index") is not None else "N/A",
        citations=profile_data.get("official_citation_count") if profile_data.get("official_citation_count") is not None else "N/A",
        adjusted_citations=profile_data.get("adjusted_citation_count") if profile_data.get("adjusted_citation_count") is not None else "N/A",
        integrity_score=profile_data["integrity_score"],
        self_cite_rate=round(profile_data["self_citation_rate"] * 100, 1) if profile_data.get("self_citation_rate") is not None else "Not assessed",
        pub_count=len(profile_data.get("publications", [])),
        flags=flags_text,
    )

    return await _generate(prompt)


async def _generate(prompt: str) -> str:
    """Call Gemini to generate text."""
    if not settings.GEMINI_API_KEY:
        return "Report narrative unavailable — AI service not configured."

    try:
        text = await call_gemini(
            prompt,
            operation="narrative_generator",
            temperature=0.4,
            max_output_tokens=2048,
        )
        # An empty string here means GEMINI_API_KEY was unset or the
        # API returned no text — both surface as the same operator-facing
        # message rather than the empty narrative.
        return ("Advisory AI-generated summary; not verified evidence.\n\n" + text
                if text else "Report narrative unavailable — AI service returned no text.")
    except Exception as exc:
        logger.error("Narrative generation failed: %s", type(exc).__name__)
        return "Report narrative generation encountered an error."
