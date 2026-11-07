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
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_check import (
    SourceCheck,
    ClaimAnalysis,
    AIDetectionResult,
    CitationCheck,
)
from app.services.source_verification.scraper import scrape_url
from app.services.source_verification.claim_extractor import extract_claims
from app.services.source_verification.fact_checker import verify_claim
from app.services.source_verification.ai_detector import detect_ai_content
from app.services.source_verification.citation_analyzer import analyze_all_citations
from app.services.source_verification.origin_tracer import trace_origin

logger = logging.getLogger(__name__)


class SourceVerificationOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_check(
        self,
        user_id: str,
        input_type: str,
        input_content: str,
        original_pdf_path: Optional[str] = None,
    ) -> str:
        """Create a new SourceCheck record and return its ID."""
        check = SourceCheck(
            id=str(uuid.uuid4()),
            user_id=user_id,
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
            # PDF document — extract text with position data
            yield {"step": "extracting_text", "status": "processing", "detail": "Extracting text from PDF...", "progress": 0.08}
            try:
                from app.services.source_verification.pdf_processor import extract_text_with_positions
                pdf_extracted_data = extract_text_with_positions(check.original_pdf_path)
                text = pdf_extracted_data.get("full_text", "")
                page_count = len(pdf_extracted_data.get("pages", []))
                check.input_title = check.input_title or f"PDF Document ({page_count} pages)"
                yield {"step": "extracting_text", "status": "done", "detail": f"Extracted {len(text)} chars from {page_count} pages", "progress": 0.15}
            except Exception as e:
                logger.exception("PDF text extraction failed")
                yield {"step": "extracting_text", "status": "error", "detail": str(e), "progress": 0.15}

        elif check.input_type == "url":
            yield {"step": "scraping", "status": "processing", "detail": "Fetching article from URL...", "progress": 0.1}
            try:
                scraped = await scrape_url(check.input_content)
                if scraped.get("error"):
                    yield {"step": "scraping", "status": "warning", "detail": f"Scraping issue: {scraped['error']}", "progress": 0.15}
                if scraped.get("body"):
                    text = scraped["body"]
                if scraped.get("title"):
                    check.input_title = scraped["title"]
                citations_from_scraper = scraped.get("citations", [])
                yield {"step": "scraping", "status": "done", "detail": f"Extracted {len(text)} chars", "progress": 0.15}
            except Exception as e:
                logger.exception("Scraping failed")
                yield {"step": "scraping", "status": "error", "detail": str(e), "progress": 0.15}

        if not text or len(text.strip()) < 50:
            check.status = "failed"
            check.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield {"step": "error", "status": "failed", "detail": "Insufficient text content to analyze", "progress": 1.0}
            return

        # ── Step 2: Extract claims ──
        yield {"step": "extracting_claims", "status": "processing", "detail": "Extracting factual claims...", "progress": 0.2}
        try:
            claims = await extract_claims(text)
            yield {"step": "extracting_claims", "status": "done", "detail": f"Found {len(claims)} claims", "progress": 0.3}
        except Exception as e:
            logger.exception("Claim extraction failed")
            claims = []
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
                detect_ai_content(text),
            )
        except Exception as e:
            logger.exception("Parallel analysis failed")
            fact_check_results = []
            ai_results = []
            yield {"step": "analyzing", "status": "error", "detail": str(e), "progress": 0.6}

        yield {"step": "fact_checking", "status": "done", "detail": f"Verified {len(fact_check_results)} claims", "progress": 0.55}
        yield {"step": "ai_detection", "status": "done", "detail": f"Analyzed {len(ai_results)} paragraphs", "progress": 0.6}

        # ── Step 5: Analyze citations ──
        yield {"step": "citations", "status": "processing", "detail": "Checking citations...", "progress": 0.65}
        try:
            citation_results = await analyze_all_citations(citations_from_scraper)
            yield {"step": "citations", "status": "done", "detail": f"Checked {len(citation_results)} citations", "progress": 0.7}
        except Exception as e:
            logger.exception("Citation analysis failed")
            citation_results = []
            yield {"step": "citations", "status": "error", "detail": str(e), "progress": 0.7}

        # ── Step 6: Trace origins ──
        yield {"step": "origin_tracing", "status": "processing", "detail": "Tracing misinformation origins...", "progress": 0.75}
        misinfo_claims = [c for c in fact_check_results if c.get("verdict") in ("false", "misleading")]
        for claim_data in misinfo_claims:
            try:
                trace = await trace_origin(claim_data["claim_text"], claim_data["verdict"], claim_data.get("explanation", ""))
                if trace:
                    claim_data["origin_trace"] = trace
            except Exception:
                logger.exception("Origin trace failed for claim")
        yield {"step": "origin_tracing", "status": "done", "detail": f"Traced {len(misinfo_claims)} claims", "progress": 0.8}

        # ── Step 7: Save results ──
        yield {"step": "saving", "status": "processing", "detail": "Saving results...", "progress": 0.85}
        try:
            await self._save_results(check, fact_check_results, ai_results, citation_results)
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
                # Build position map and annotated PDF
                from app.services.source_verification.pdf_processor import map_all_findings_to_positions
                from app.services.source_verification.pdf_annotator import create_annotated_pdf

                # Reload saved records to get IDs
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
                yield {"step": "generating_annotations", "status": "error", "detail": str(e), "progress": 0.95}

        yield {"step": "complete", "status": "completed", "detail": "Analysis complete", "progress": 1.0}

    async def _save_results(
        self,
        check: SourceCheck,
        fact_check_results: list[dict],
        ai_results: list[dict],
        citation_results: list[dict],
    ) -> None:
        """Persist all analysis results to the database."""
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

        credibility = 100.0
        for fc in fact_check_results:
            v = fc.get("verdict", "unverified")
            conf = fc.get("confidence", 0.5)
            if v == "false":
                credibility -= 15 * conf
            elif v == "misleading":
                credibility -= 10 * conf
            elif v == "partially_true":
                credibility -= 5 * conf
            elif v == "unverified":
                credibility -= 3 * conf

        if ai_percentage > 50:
            credibility -= (ai_percentage - 50) * 0.3

        retracted = sum(1 for cr in citation_results if cr.get("is_retracted"))
        inaccessible = sum(1 for cr in citation_results if not cr.get("is_accessible", True))
        credibility -= retracted * 15
        credibility -= inaccessible * 5
        credibility = max(0.0, min(100.0, credibility))

        check.overall_credibility_score = round(credibility, 1)
        check.ai_content_percentage = round(ai_percentage, 1)
        check.misinfo_claims_found = misinfo_count
        check.status = "completed"
        check.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
