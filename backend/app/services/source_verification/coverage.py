"""Surface analysis coverage caveats from ``model_metadata``.

The pipeline records structured warnings as it goes — ``text_truncated``,
``claims_capped``, ``paragraphs_capped``, ``fallback_heuristic`` — into
``SourceCheck.model_metadata.processing_warnings``. They've always been
persisted, but the UI never showed them, so users saw a confident score
without knowing the analysis only looked at the first 15K chars / 20
paragraphs / 15 claims of their submission.

This module translates those warnings + the ``context`` block into a
user-facing ``CoverageSummary`` the response schema can include verbatim.

Keep the rendering logic here (not in the orchestrator) so re-running an
older check picks up improved phrasing automatically, without a backfill
migration.
"""

from __future__ import annotations

from typing import Any

from app.schemas.source_check import CoverageNote, CoverageSummary


def _ctx(metadata: dict) -> dict:
    return (metadata.get("context") or {}) if isinstance(metadata, dict) else {}


def _warnings(metadata: dict) -> list[dict]:
    raw = metadata.get("processing_warnings") if isinstance(metadata, dict) else None
    if not isinstance(raw, list):
        return []
    return [w for w in raw if isinstance(w, dict)]


def build_coverage(model_metadata: Any) -> CoverageSummary | None:
    """Build a CoverageSummary or return None when the analysis was clean
    (no warnings + full headline numbers unknown). Callers can render the
    summary even when ``notes`` is empty — the headline numbers alone
    let the UI say "analyzed 15 claims across 7,420 characters"."""
    if not isinstance(model_metadata, dict):
        return None

    ctx = _ctx(model_metadata)
    warnings = _warnings(model_metadata)

    notes: list[CoverageNote] = []
    claims_analyzed: int | None = ctx.get("claims_extracted")
    paragraphs_analyzed: int | None = ctx.get("paragraphs_analyzed")
    text_chars_total: int | None = ctx.get("text_length")
    text_chars_analyzed: int | None = (
        text_chars_total if not ctx.get("text_truncated") else None
    )
    claims_extracted_total: int | None = None
    paragraphs_total: int | None = None

    for w in warnings:
        kind = str(w.get("type") or "")
        if kind == "text_truncated":
            original = int(w.get("original_length") or 0) or None
            analyzed = int(w.get("analyzed_length") or 0) or None
            text_chars_total = original or text_chars_total
            text_chars_analyzed = analyzed or text_chars_analyzed
            if original and analyzed and original > analyzed:
                notes.append(
                    CoverageNote(
                        kind=kind,
                        severity="warning",
                        headline=f"Analyzed first {analyzed:,} of {original:,} characters",
                        detail=(
                            "Long inputs are truncated to keep analysis tractable. "
                            "Claims past this point were not extracted or fact-checked."
                        ),
                    )
                )
        elif kind == "claims_capped":
            extracted = int(w.get("extracted") or 0) or None
            kept = int(w.get("kept") or 0) or None
            if extracted and kept:
                claims_extracted_total = extracted
                claims_analyzed = kept
                notes.append(
                    CoverageNote(
                        kind=kind,
                        severity="info",
                        headline=f"Verified {kept} of {extracted} extracted claims",
                        detail=(
                            "The model surfaced more claims than we fact-check per analysis. "
                            "We keep the top-priority claims; remaining were not verified."
                        ),
                    )
                )
        elif kind == "paragraphs_capped":
            total = int(w.get("total") or 0) or None
            analyzed = int(w.get("analyzed") or 0) or None
            if total and analyzed and total > analyzed:
                paragraphs_total = total
                paragraphs_analyzed = analyzed
                notes.append(
                    CoverageNote(
                        kind=kind,
                        severity="warning",
                        headline=f"AI detection sampled {analyzed} of {total} paragraphs",
                        detail=(
                            "AI-likelihood was computed on a leading sample; remaining "
                            "paragraphs were not scored. The percentage is a sample estimate, "
                            "not a whole-document measure."
                        ),
                    )
                )
        elif kind == "fallback_heuristic":
            module = str(w.get("module") or "analysis")
            notes.append(
                CoverageNote(
                    kind=kind,
                    severity="warning",
                    headline=f"{module.replace('_', ' ').title()} used heuristic fallback",
                    detail=(
                        "The primary model was unavailable for this step, so a coarse "
                        "rule-based estimator stood in. Confidence is correspondingly lower."
                    ),
                )
            )
        elif kind == "missing_gemini_key":
            notes.append(
                CoverageNote(
                    kind=kind,
                    severity="warning",
                    headline="Claim extraction disabled (no API key)",
                    detail=(
                        "Gemini API key isn't configured on this deployment, so no "
                        "claims were extracted and no claim-level fact-check ran."
                    ),
                )
            )
        elif kind == "citation_extraction_unsupported":
            notes.append(CoverageNote(
                kind=kind, severity="warning", headline="Bibliography not checked",
                detail="PDF and pasted-text references are not yet extracted into the citation checker. Missing citation findings do not establish a clean bibliography.",
            ))
        elif kind == "insufficient_verification_evidence":
            notes.append(CoverageNote(
                kind=kind, severity="warning", headline="Credibility score unavailable",
                detail="Required verification evidence is missing or a required step failed. Available findings do not establish overall accuracy.",
            ))
        elif kind == "insufficient_source_text":
            notes.append(
                CoverageNote(
                    kind=kind,
                    severity="warning",
                    headline="Source content unavailable",
                    detail=(
                        "The source did not yield enough readable text. No claim "
                        "verification or AI assessment was performed; retry with "
                        "readable content."
                    ),
                )
            )
        elif kind in (
            "pdf_extraction_failed",
            "scraping_failed",
            "claim_extraction_failed",
            "citation_analysis_failed",
            "parallel_analysis_failed",
            "fact_check_failed",
            "ai_detection_failed",
            "claim_verification_unavailable",
            "analysis_failed",
            "attempts_exhausted",
            "pdf_annotation_failed",
        ):
            notes.append(
                CoverageNote(
                    kind=kind,
                    severity="warning",
                    headline=f"{kind.replace('_', ' ').capitalize()}",
                    detail=(
                        "A pipeline step errored out and was skipped. Surrounding "
                        "results are still valid; this step's findings are missing."
                    ),
                )
            )

    return CoverageSummary(
        notes=notes,
        claims_analyzed=claims_analyzed,
        claims_extracted=claims_extracted_total or claims_analyzed,
        paragraphs_analyzed=paragraphs_analyzed,
        paragraphs_total=paragraphs_total or paragraphs_analyzed,
        text_chars_analyzed=text_chars_analyzed,
        text_chars_total=text_chars_total,
    )
