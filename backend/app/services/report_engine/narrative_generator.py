"""Report narratives.

These summaries are built **deterministically** from the structured analysis
results — the score, per-claim verdicts, AI percentage, citation health, and
integrity flags are all already computed, so the "narrative" is just faithful
prose over known numbers. That removes a per-report LLM call and, more
importantly, any chance of the model inventing a finding that isn't in the
data.

The LLM is kept only as an opt-in *polish* pass (``NARRATIVE_LLM_POLISH``):
when enabled it rewrites from the same structured inputs for nicer flow, and
falls back to the deterministic draft on any failure. Default is off.
"""

import logging

from app.config import settings
from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)

# Kept for the opt-in LLM polish path. Unchanged so prompt governance (if it
# ever registers these) stays stable.
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


# ─── Deterministic rendering ───────────────────────────────────────────────

# Score bands match the product's high/mid/low thresholds (see DESIGN.md).
def _band(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "high"
    if score >= 40:
        return "mid"
    return "low"


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or singular + "s")


def _render_source_check_narrative(check_data: dict) -> str:
    title = check_data.get("input_title") or "The submitted source"
    score = check_data.get("overall_credibility_score")
    ai_pct = check_data.get("ai_content_percentage") or 0
    misinfo = check_data.get("misinfo_claims_found") or 0
    claims = check_data.get("claims") or []
    citations = check_data.get("citations") or []
    band = _band(score)

    score_txt = f"{round(score)}/100" if score is not None else "not available"
    assess = {
        "high": "appears broadly credible",
        "mid": "shows a mix of supported and questionable material",
        "low": "appears unreliable",
        "unknown": "could not be conclusively assessed",
    }[band]
    p1 = f"{title} {assess}, with an overall credibility score of {score_txt}."

    n = len(claims)
    if n:
        counts: dict[str, int] = {}
        for c in claims:
            v = str(c.get("verdict") or "unverified").lower()
            counts[v] = counts.get(v, 0) + 1
        labels = [
            ("verified as accurate", "true"),
            ("found false", "false"),
            ("flagged as misleading", "misleading"),
            ("partially accurate", "partially_true"),
            ("left unverified", "unverified"),
        ]
        parts = [f"{counts[key]} {label}" for label, key in labels if counts.get(key)]
        detail = "; ".join(parts) if parts else "no individual verdicts were recorded"
        p2 = f"Of {n} factual {_plural(n, 'claim')} extracted, {detail}."
        if misinfo:
            p2 += (
                f" {misinfo} {_plural(misinfo, 'claim')} {_plural(misinfo, 'was', 'were')} "
                "judged false or misleading and weigh most heavily on the score."
            )
    else:
        p2 = "No discrete factual claims were extracted from this source."

    if ai_pct >= 70:
        ai_txt = f"A high share of the text (~{round(ai_pct)}%) shows signals consistent with AI generation"
    elif ai_pct >= 40:
        ai_txt = f"A moderate share of the text (~{round(ai_pct)}%) shows possible AI-generation signals"
    else:
        ai_txt = f"AI-generation signals were low (~{round(ai_pct)}%)"
    p3 = f"{ai_txt}. This estimate is probabilistic, not proof of authorship."

    if citations:
        retracted = sum(1 for c in citations if c.get("is_retracted"))
        inaccessible = sum(1 for c in citations if not c.get("is_accessible", True))
        bits = [f"{len(citations)} {_plural(len(citations), 'citation')} checked"]
        if retracted:
            bits.append(f"{retracted} retracted")
        if inaccessible:
            bits.append(f"{inaccessible} inaccessible")
        cite_txt = ", ".join(bits) + "."
    else:
        cite_txt = "No citations were detected to verify."
    rec = {
        "high": "Readers can treat the source as generally reliable while noting any caveats above.",
        "mid": "Treat specific claims with caution and corroborate the flagged items before relying on them.",
        "low": "Independent corroboration is recommended before relying on this source.",
        "unknown": "Further review is recommended before relying on this source.",
    }[band]
    p4 = f"{cite_txt} {rec}"

    return "\n\n".join([p1, p2, p3, p4])


def _render_researcher_narrative(profile_data: dict) -> str:
    name = profile_data.get("researcher_name") or "The researcher"
    integrity = profile_data.get("integrity_score")
    band = _band(integrity)
    self_rate = round((profile_data.get("self_citation_rate") or 0) * 100, 1)
    h = profile_data.get("official_h_index")
    adj_h = profile_data.get("adjusted_h_index")
    cites = profile_data.get("official_citation_count")
    adj_cites = profile_data.get("adjusted_citation_count")
    pubs = len(profile_data.get("publications", []))
    ring_flags = profile_data.get("citation_ring_flags") or {}
    flags = ring_flags.get("flags", []) if isinstance(ring_flags, dict) else []

    score_txt = f"{round(integrity)}/100" if integrity is not None else "not available"
    assess = {
        "high": "shows no major integrity concerns",
        "mid": "shows some citation-pattern concerns",
        "low": "shows significant citation-integrity concerns",
        "unknown": "could not be conclusively assessed",
    }[band]
    p1 = (
        f"{name}'s publication record {assess}, with an integrity score of "
        f"{score_txt} across {pubs} {_plural(pubs, 'publication')}."
    )

    adj_bits = []
    if h is not None and adj_h is not None and adj_h != h:
        adj_bits.append(f"the h-index adjusts from {h} to {adj_h}")
    if cites is not None and adj_cites is not None and adj_cites != cites:
        adj_bits.append(f"citations adjust from {cites} to {adj_cites}")
    if adj_bits:
        p2 = (
            "After discounting self-citations and suspected citation-ring activity, "
            + " and ".join(adj_bits)
            + "."
        )
    else:
        p2 = "Adjusted metrics did not differ materially from the official figures."

    p3 = f"The self-citation rate is {self_rate}%."
    if flags:
        p3 += " Flags raised: " + "; ".join(str(f) for f in flags[:6]) + "."
    else:
        p3 += " No citation-ring or citation-velocity anomalies were flagged."

    rec = {
        "high": "The reported metrics appear trustworthy as stated.",
        "mid": "Interpret the headline metrics alongside the flagged patterns.",
        "low": "Headline metrics likely overstate impact; rely on the adjusted figures.",
        "unknown": "Further data is needed for a confident assessment.",
    }[band]

    return "\n\n".join([p1, p2, p3, rec])


# ─── Public API ────────────────────────────────────────────────────────────


async def generate_source_check_narrative(check_data: dict) -> str:
    """Narrative summary for a source-verification report.

    Deterministic by default; LLM polish only when ``NARRATIVE_LLM_POLISH``.
    """
    draft = _render_source_check_narrative(check_data)
    if not settings.NARRATIVE_LLM_POLISH:
        return draft

    claims = check_data.get("claims", [])
    citations = check_data.get("citations", [])
    claims_summary = "No claims analyzed."
    if claims:
        claims_summary = "\n".join(
            f"- \"{c.get('claim_text', '')[:80]}\" — {str(c.get('verdict', 'unverified')).upper()}"
            for c in claims[:10]
        )
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
    return (await _polish(prompt)) or draft


async def generate_researcher_narrative(profile_data: dict) -> str:
    """Narrative summary for a researcher-integrity report.

    Deterministic by default; LLM polish only when ``NARRATIVE_LLM_POLISH``.
    """
    draft = _render_researcher_narrative(profile_data)
    if not settings.NARRATIVE_LLM_POLISH:
        return draft

    ring_flags = profile_data.get("citation_ring_flags") or {}
    flags = ring_flags.get("flags", []) if isinstance(ring_flags, dict) else []
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
    return (await _polish(prompt)) or draft


async def _polish(prompt: str) -> str:
    """Optional LLM rewrite. Returns "" on any failure so the caller falls
    back to the deterministic draft."""
    if not settings.GEMINI_API_KEY:
        return ""
    try:
        text = await call_gemini(
            prompt,
            operation="narrative_generator",
            temperature=0.4,
            max_output_tokens=2048,
        )
        return text or ""
    except Exception:
        logger.exception("Narrative LLM polish failed")
        return ""
