"""
Source verification orchestrator — coordinates the full Module 1 pipeline.

Steps:
1. Extract text (scrape URL / read PDF with positions / use raw text)
2. Extract claims (Gemini)
3. Fact-check each claim + detect AI content (parallel)
4. Analyze citations
5. Trace origins for false/misleading claims
6. [PDF only] Generate annotated PDF with highlights
7. Calculate overall credibility score
8. Save all results to database

The step-level broad excepts here are intentional: a single step failure
should yield an "error" event for that step and continue, not abort the
whole pipeline. Tightening them would break that resilience contract.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import CREDIBILITY_SCORE_MAX, CREDIBILITY_SCORE_MIN
from app.models.source_check import (
    SourceCheck,
    ClaimAnalysis,
    AIDetectionResult,
    CitationCheck,
)
from app.schemas.breakdown import FORMULA_VERSION
from app.services.source_verification.scraper import scrape_url
from app.services.source_verification.claim_extractor import extract_claims
from app.services.source_verification.fact_checker import verify_claim
from app.services.source_verification.ai_detector import detect_ai_content
from app.services.source_verification.citation_analyzer import analyze_all_citations
from app.services.source_verification.origin_tracer import trace_origin
from app.utils.retry import HTTP_RETRY_EXCEPTIONS

logger = logging.getLogger(__name__)


# The step-level except blocks below split into two paths so the log
# level reflects what actually happened:
#   - HTTP_RETRY_EXCEPTIONS  → logger.warning (network blip / upstream
#     flaked even after the retry decorator); pipeline continues with
#     a warning recorded.
#   - everything else → logger.exception (real bug); pipeline still
#     continues — partial-failure tolerance is intentional, see the
#     module docstring above — but the stack trace lands in Sentry.
#
# Both paths still append to self._warnings so the UI shows the caveat.


# Scoring weights — bumping these requires bumping FORMULA_VERSION
WEIGHT_FALSE_CLAIM = 15.0
WEIGHT_MISLEADING = 10.0
WEIGHT_PARTIALLY_TRUE = 5.0
WEIGHT_UNVERIFIED = 3.0
WEIGHT_AI_PER_PERCENT_OVER_50 = 0.3
WEIGHT_RETRACTED_CITATION = 15.0
WEIGHT_INACCESSIBLE_CITATION = 5.0


class SourceVerificationOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Per-pipeline tracking. Reset at the top of run_pipeline_streaming
        # so the orchestrator can be reused across requests.
        self._warnings: list[dict] = []
        self._apis_used: list[str] = []
        self._fallback_used = False
        self._text_was_truncated = False

    def _track_api(self, name: str) -> None:
        if name not in self._apis_used:
            self._apis_used.append(name)

    async def create_check(
        self,
        user_id: str,
        input_type: str,
        input_content: str,
        original_pdf_path: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Create a new SourceCheck record and return its ID.

        ``organization_id`` is propagated from the caller (route layer
        reads it off ``current_user.organization_id``) so org admins can
        eventually surface their team's analyses. NULL means private to
        the user — see app/models/source_check.py docstring.
        """
        check = SourceCheck(
            id=str(uuid.uuid4()),
            user_id=user_id,
            organization_id=organization_id,
            input_type=input_type,
            input_content=input_content,
            original_pdf_path=original_pdf_path,
            status="pending",
        )
        self.db.add(check)
        await self.db.commit()
        return check.id

    async def run_pipeline(self, check_id: str) -> None:
        """Run the full verification pipeline (non-streaming)."""
        async for _ in self.run_pipeline_streaming(check_id):
            pass

    async def run_pipeline_streaming(self, check_id: str) -> AsyncGenerator[dict, None]:
        """Run the full pipeline, yielding progress events for SSE."""
        # Reset per-run state
        self._warnings = []
        self._apis_used = []
        self._fallback_used = False
        self._text_was_truncated = False

        # ── Governance: snapshot the prompt bundle at pipeline start ──
        # Live hashes are written into model_metadata at save time so
        # disputes can be replayed against the exact prompt revision
        # that produced the score. Drift (a prompt edited without a
        # PROMPT_VERSION bump) fires a Sentry warning via the helper.
        # Deferred import: src_verification/__init__.py imports from
        # this module, so a top-level import here would be circular.
        from app.services.source_verification import (
            PROMPT_HASHES,
            PROMPT_VERSION,
            compute_live_prompt_hashes,
        )
        from app.governance import check_prompt_drift

        self._prompt_version = PROMPT_VERSION
        self._prompt_hashes_live = compute_live_prompt_hashes()
        self._prompt_drift_detected = check_prompt_drift(
            engine="source_verification",
            expected=PROMPT_HASHES,
            live=self._prompt_hashes_live,
        )

        result = await self.db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
        check = result.scalar_one_or_none()
        if not check:
            yield {"step": "error", "status": "failed", "detail": "Source check not found", "progress": 0}
            return

        check.status = "processing"
        await self.db.commit()
        yield {"step": "started", "status": "processing", "detail": "Pipeline started", "progress": 0.05}

        text = check.input_content
        citations_from_scraper = []
        pdf_extracted_data = None  # Position data for PDF annotation

        # ── Step 1: Extract text ──
        if check.input_type == "document" and check.original_pdf_path:
            yield {"step": "extracting_text", "status": "processing", "detail": "Extracting text from PDF...", "progress": 0.08}
            try:
                from app.services.source_verification.pdf_processor import extract_text_with_positions
                pdf_extracted_data = extract_text_with_positions(check.original_pdf_path)
                text = pdf_extracted_data.get("full_text", "")
                page_count = len(pdf_extracted_data.get("pages", []))
                check.input_title = check.input_title or f"PDF Document ({page_count} pages)"
                self._track_api("pdf_processor")
                yield {"step": "extracting_text", "status": "done", "detail": f"Extracted {len(text)} chars from {page_count} pages", "progress": 0.15}
            except Exception as e:
                logger.exception("PDF text extraction failed")
                self._warnings.append({"type": "pdf_extraction_failed", "error": type(e).__name__})
                yield {"step": "extracting_text", "status": "error", "detail": str(e), "progress": 0.15}

        elif check.input_type == "url":
            yield {"step": "scraping", "status": "processing", "detail": "Fetching article from URL...", "progress": 0.1}
            try:
                scraped = await scrape_url(check.input_content)
                self._track_api("url_scraper")
                if scraped.get("error"):
                    yield {"step": "scraping", "status": "warning", "detail": f"Scraping issue: {scraped['error']}", "progress": 0.15}
                if scraped.get("body"):
                    text = scraped["body"]
                if scraped.get("title"):
                    check.input_title = scraped["title"]
                citations_from_scraper = scraped.get("citations", [])
                yield {"step": "scraping", "status": "done", "detail": f"Extracted {len(text)} chars", "progress": 0.15}
            except HTTP_RETRY_EXCEPTIONS as e:
                logger.warning("Scraping transient failure: %s", e)
                self._warnings.append({"type": "scraping_failed", "error": type(e).__name__, "transient": True})
                yield {"step": "scraping", "status": "error", "detail": str(e), "progress": 0.15}
            except Exception as e:
                logger.exception("Scraping failed")
                self._warnings.append({"type": "scraping_failed", "error": type(e).__name__})
                yield {"step": "scraping", "status": "error", "detail": str(e), "progress": 0.15}

        if not text or len(text.strip()) < 50:
            check.status = "failed"
            check.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield {"step": "error", "status": "failed", "detail": "Insufficient text content to analyze", "progress": 1.0}
            return

        text_length = len(text)

        # ── Step 2: Extract claims ──
        yield {"step": "extracting_claims", "status": "processing", "detail": "Extracting factual claims...", "progress": 0.2}
        try:
            claims = await extract_claims(text, warnings=self._warnings)
            self._track_api("gemini")
            yield {"step": "extracting_claims", "status": "done", "detail": f"Found {len(claims)} claims", "progress": 0.3}
        except HTTP_RETRY_EXCEPTIONS as e:
            logger.warning("Claim extraction transient failure: %s", e)
            claims = []
            self._warnings.append({"type": "claim_extraction_failed", "error": type(e).__name__, "transient": True})
            yield {"step": "extracting_claims", "status": "error", "detail": str(e), "progress": 0.3}
        except Exception as e:
            logger.exception("Claim extraction failed")
            claims = []
            self._warnings.append({"type": "claim_extraction_failed", "error": type(e).__name__})
            yield {"step": "extracting_claims", "status": "error", "detail": str(e), "progress": 0.3}

        # ── Step 3+4: Fact-check + AI detection (parallel) ──
        yield {"step": "analyzing", "status": "processing", "detail": "Fact-checking claims and detecting AI content...", "progress": 0.35}

        async def _fact_check_all():
            results = []
            for claim in claims:
                fc = await verify_claim(claim["claim_text"], text[:1000])
                results.append({**claim, **fc})
            return results

        try:
            fact_check_results, ai_results = await asyncio.gather(
                _fact_check_all(),
                detect_ai_content(text, warnings=self._warnings),
            )
            if claims:
                self._track_api("google_factcheck")
            if any(r.get("detection_method") == "heuristic-fallback" for r in ai_results):
                self._fallback_used = True
        except HTTP_RETRY_EXCEPTIONS as e:
            logger.warning("Parallel analysis transient failure: %s", e)
            fact_check_results = []
            ai_results = []
            self._warnings.append({"type": "parallel_analysis_failed", "error": type(e).__name__, "transient": True})
            yield {"step": "analyzing", "status": "error", "detail": str(e), "progress": 0.6}
        except Exception as e:
            logger.exception("Parallel analysis failed")
            fact_check_results = []
            ai_results = []
            self._warnings.append({"type": "parallel_analysis_failed", "error": type(e).__name__})
            yield {"step": "analyzing", "status": "error", "detail": str(e), "progress": 0.6}

        yield {"step": "fact_checking", "status": "done", "detail": f"Verified {len(fact_check_results)} claims", "progress": 0.55}
        yield {"step": "ai_detection", "status": "done", "detail": f"Analyzed {len(ai_results)} paragraphs", "progress": 0.6}

        # ── Step 5: Analyze citations ──
        yield {"step": "citations", "status": "processing", "detail": "Checking citations...", "progress": 0.65}
        try:
            citation_results = await analyze_all_citations(citations_from_scraper, warnings=self._warnings)
            if citations_from_scraper:
                # Both retraction APIs are queried per citation; record both
                # so users can see the analysis hit independent sources.
                self._track_api("crossref")
                self._track_api("openalex")
            yield {"step": "citations", "status": "done", "detail": f"Checked {len(citation_results)} citations", "progress": 0.7}
        except HTTP_RETRY_EXCEPTIONS as e:
            logger.warning("Citation analysis transient failure: %s", e)
            citation_results = []
            self._warnings.append({"type": "citation_analysis_failed", "error": type(e).__name__, "transient": True})
            yield {"step": "citations", "status": "error", "detail": str(e), "progress": 0.7}
        except Exception as e:
            logger.exception("Citation analysis failed")
            citation_results = []
            self._warnings.append({"type": "citation_analysis_failed", "error": type(e).__name__})
            yield {"step": "citations", "status": "error", "detail": str(e), "progress": 0.7}

        # ── Step 6: Trace origins ──
        yield {"step": "origin_tracing", "status": "processing", "detail": "Tracing misinformation origins...", "progress": 0.75}
        misinfo_claims = [c for c in fact_check_results if c.get("verdict") in ("false", "misleading")]
        for claim_data in misinfo_claims:
            try:
                trace = await trace_origin(claim_data["claim_text"], claim_data["verdict"], claim_data.get("explanation", ""))
                if trace:
                    claim_data["origin_trace"] = trace
            except HTTP_RETRY_EXCEPTIONS as e:
                logger.warning("Origin trace transient failure: %s", e)
                self._warnings.append({"type": "origin_trace_failed", "transient": True})
            except Exception:
                logger.exception("Origin trace failed for claim")
                self._warnings.append({"type": "origin_trace_failed"})
        yield {"step": "origin_tracing", "status": "done", "detail": f"Traced {len(misinfo_claims)} claims", "progress": 0.8}

        # ── Step 7: Save results ──
        yield {"step": "saving", "status": "processing", "detail": "Saving results...", "progress": 0.85}
        try:
            await self._save_results(check, fact_check_results, ai_results, citation_results, text_length)
        except Exception as e:
            logger.exception("Failed to save results")
            check.status = "failed"
            check.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield {"step": "error", "status": "failed", "detail": str(e), "progress": 1.0}
            return

        # ── Step 8 [PDF only]: Generate annotated PDF ──
        if pdf_extracted_data and check.original_pdf_path:
            yield {"step": "generating_annotations", "status": "processing", "detail": "Creating annotated PDF...", "progress": 0.9}
            try:
                from app.services.source_verification.pdf_processor import map_all_findings_to_positions
                from app.services.source_verification.pdf_annotator import create_annotated_pdf

                claims_q = await self.db.execute(
                    select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check.id)
                )
                saved_claims = [
                    {"id": c.id, "claim_text": c.claim_text, "verdict": c.verdict,
                     "confidence": c.confidence, "position_in_text": c.position_in_text}
                    for c in claims_q.scalars().all()
                ]

                ai_q = await self.db.execute(
                    select(AIDetectionResult).where(AIDetectionResult.source_check_id == check.id)
                )
                saved_ai = [
                    {"id": a.id, "paragraph_text": a.paragraph_text, "ai_probability": a.ai_probability}
                    for a in ai_q.scalars().all()
                ]

                cit_q = await self.db.execute(
                    select(CitationCheck).where(CitationCheck.source_check_id == check.id)
                )
                saved_cits = [
                    {"id": c.id, "original_citation": c.original_citation,
                     "is_retracted": c.is_retracted, "is_accessible": c.is_accessible}
                    for c in cit_q.scalars().all()
                ]

                position_map = map_all_findings_to_positions(
                    pdf_extracted_data, saved_claims, saved_ai, saved_cits
                )

                annotated_path = create_annotated_pdf(
                    check.original_pdf_path, position_map,
                    saved_claims, saved_ai, saved_cits,
                )

                check.text_position_map = position_map
                check.annotated_pdf_path = annotated_path
                await self.db.commit()

                yield {"step": "generating_annotations", "status": "done", "detail": "Annotated PDF ready", "progress": 0.95}
            except Exception as e:
                logger.exception("PDF annotation failed")
                self._warnings.append({"type": "pdf_annotation_failed", "error": type(e).__name__})
                # Persist the warning so the user/UI knows the analysis is
                # complete but no annotated PDF was produced.
                if check.model_metadata is not None:
                    check.model_metadata = {
                        **check.model_metadata,
                        "processing_warnings": list(check.model_metadata.get("processing_warnings", []))
                        + [{"type": "pdf_annotation_failed", "error": type(e).__name__}],
                    }
                    await self.db.commit()
                yield {
                    "step": "generating_annotations", "status": "warning",
                    "detail": "Analysis complete; annotated PDF could not be generated",
                    "progress": 0.95,
                }

        yield {"step": "complete", "status": "completed", "detail": "Analysis complete", "progress": 1.0}

    def _calculate_credibility(
        self,
        fact_check_results: list[dict],
        ai_percentage: float,
        citation_results: list[dict],
    ) -> tuple[float, dict]:
        """Compute the credibility score and the breakdown that explains it.

        The numeric output matches the previous formula exactly so existing
        seeded scores stay valid; only the breakdown is new.
        """
        score = 100.0
        deductions: list[dict] = []

        for fc in fact_check_results:
            verdict = fc.get("verdict", "unverified")
            conf = fc.get("confidence", 0.5)
            weight = {
                "false": WEIGHT_FALSE_CLAIM,
                "misleading": WEIGHT_MISLEADING,
                "partially_true": WEIGHT_PARTIALLY_TRUE,
                "unverified": WEIGHT_UNVERIFIED,
            }.get(verdict)
            if weight is None:
                continue
            impact = -round(weight * conf, 2)
            score += impact
            deductions.append({
                "reason": f"{verdict}_claim",
                "impact": impact,
                "detail": {
                    "claim": fc.get("claim_text", "")[:120],
                    "confidence": round(conf, 2),
                    "weight": weight,
                },
            })

        if ai_percentage > 50:
            impact = -round((ai_percentage - 50) * WEIGHT_AI_PER_PERCENT_OVER_50, 2)
            score += impact
            deductions.append({
                "reason": "ai_content_detected",
                "impact": impact,
                "detail": {
                    "ai_percentage": round(ai_percentage, 1),
                    "threshold": 50,
                    "per_percent_weight": WEIGHT_AI_PER_PERCENT_OVER_50,
                },
            })

        retracted = sum(1 for cr in citation_results if cr.get("is_retracted"))
        if retracted:
            impact = -round(retracted * WEIGHT_RETRACTED_CITATION, 2)
            score += impact
            deductions.append({
                "reason": "retracted_citations",
                "impact": impact,
                "detail": {"count": retracted, "weight_each": WEIGHT_RETRACTED_CITATION},
            })

        inaccessible = sum(1 for cr in citation_results if not cr.get("is_accessible", True))
        if inaccessible:
            impact = -round(inaccessible * WEIGHT_INACCESSIBLE_CITATION, 2)
            score += impact
            deductions.append({
                "reason": "inaccessible_citations",
                "impact": impact,
                "detail": {"count": inaccessible, "weight_each": WEIGHT_INACCESSIBLE_CITATION},
            })

        final = max(CREDIBILITY_SCORE_MIN, min(CREDIBILITY_SCORE_MAX, round(score, 1)))
        confidence = self._calculate_confidence(fact_check_results, citation_results)

        breakdown = {
            "base": 100.0,
            "deductions": deductions,
            "warnings": [w.get("type", "") for w in self._warnings],
            "final": final,
            "confidence": confidence,
            "formula_version": FORMULA_VERSION,
        }
        return final, breakdown

    def _calculate_confidence(
        self,
        fact_check_results: list[dict],
        citation_results: list[dict],
    ) -> float:
        """Estimate how confident we are in the score (0-1).

        Lower confidence when many claims were unverified, citations were
        unreachable, text was truncated, or we fell back to heuristics.
        """
        factors: list[float] = []

        if fact_check_results:
            verified = sum(1 for c in fact_check_results if c.get("verdict") not in ("unverified", None))
            factors.append(verified / len(fact_check_results))

        if citation_results:
            accessible = sum(1 for c in citation_results if c.get("is_accessible", True))
            factors.append(accessible / len(citation_results))

        if self._text_was_truncated:
            factors.append(0.7)
        if self._fallback_used:
            factors.append(0.6)

        if not factors:
            return 0.5
        return round(sum(factors) / len(factors), 2)

    async def _save_results(
        self,
        check: SourceCheck,
        fact_check_results: list[dict],
        ai_results: list[dict],
        citation_results: list[dict],
        text_length: int = 0,
    ) -> None:
        """Persist all analysis results plus score breakdown and model metadata."""
        misinfo_count = 0
        for fc in fact_check_results:
            verdict = fc.get("verdict", "unverified")
            if verdict in ("false", "misleading"):
                misinfo_count += 1
            self.db.add(ClaimAnalysis(
                id=str(uuid.uuid4()), source_check_id=check.id,
                claim_text=fc["claim_text"], verdict=verdict,
                confidence=fc.get("confidence", 0.5),
                explanation=fc.get("explanation", ""),
                true_version=fc.get("true_version"),
                sources=fc.get("sources"), origin_trace=fc.get("origin_trace"),
                position_in_text=fc.get("position"),
            ))

        ai_total = 0.0
        for ai in ai_results:
            ai_total += ai.get("ai_probability", 0.5)
            self.db.add(AIDetectionResult(
                id=str(uuid.uuid4()), source_check_id=check.id,
                paragraph_index=ai["paragraph_index"],
                paragraph_text=ai["paragraph_text"][:5000],
                ai_probability=ai["ai_probability"],
                detection_method=ai.get("detection_method", "unknown"),
            ))

        for cr in citation_results:
            self.db.add(CitationCheck(
                id=str(uuid.uuid4()), source_check_id=check.id,
                original_citation=cr["original_citation"],
                citation_url=cr.get("citation_url"),
                is_accessible=cr.get("is_accessible", True),
                is_retracted=cr.get("is_retracted", False),
                credibility_score=cr.get("credibility_score"),
                issues=cr.get("issues"),
                suggested_alternative=cr.get("suggested_alternative"),
            ))

        ai_percentage = (ai_total / len(ai_results) * 100) if ai_results else 0.0

        # Detect post-hoc whether claim_extractor truncated the text. This is
        # also recorded by claim_extractor itself in self._warnings.
        self._text_was_truncated = any(
            w.get("type") == "text_truncated" for w in self._warnings
        )

        credibility, breakdown = self._calculate_credibility(
            fact_check_results, ai_percentage, citation_results,
        )

        check.overall_credibility_score = credibility
        check.ai_content_percentage = round(ai_percentage, 1)
        check.misinfo_claims_found = misinfo_count
        check.score_breakdown = breakdown
        # All metadata goes through the Pydantic governance schema so
        # a typo or missing field surfaces at save time, not at audit
        # time three months later when someone tries to reproduce a
        # disputed score.
        from app.schemas.governance import build_model_metadata

        check.model_metadata = build_model_metadata(
            model_provider="google",
            model_name=settings.GEMINI_MODEL,
            formula_version=FORMULA_VERSION,
            prompt_version=self._prompt_version,
            prompt_hashes=self._prompt_hashes_live,
            prompt_drift_detected=self._prompt_drift_detected,
            apis_used=self._apis_used,
            fallback_used=self._fallback_used,
            processing_warnings=self._warnings,
            context={
                "text_length": text_length,
                "text_truncated": self._text_was_truncated,
                "claims_extracted": len(fact_check_results),
                "paragraphs_analyzed": len(ai_results),
            },
        )
        check.status = "completed"
        check.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
