"""
Academic integrity orchestrator — coordinates the Module 2 pipeline.

Steps (sequential — graph must be built before ring detection):
1. Resolve researcher profile (Semantic Scholar / ORCID / Scopus / Google Scholar)
2. Fetch publications
3. Build citation graph
4. Summarize incoming citation patterns (no ring inference)
5. Analyze topic relevance (Gemini)
6. Calculate adjusted ratings
7. Save all results

The step-level broad excepts here are intentional: a single step failure
should yield an "error" event for that step and continue. Tightening would
break the resilience contract.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.researcher import ResearcherProfile, PublicationAnalysis
from app.schemas.breakdown import RESEARCHER_FORMULA_VERSION as FORMULA_VERSION
from app.services.academic_integrity.scholar_scraper import (
    resolve_researcher,
    fetch_publications,
)
from app.services.academic_integrity.citation_graph_builder import build_citation_graph
from app.services.academic_integrity.ring_detector import detect_rings
from app.services.academic_integrity.topic_analyzer import analyze_topic_relevance
from app.services.academic_integrity.rating_adjuster import calculate_adjusted_metrics, unavailable_adjustment

logger = logging.getLogger(__name__)


# A paper is "heavily self-cited" if more than this fraction of its citations
# come from the target researcher.
SELF_CITED_HEAVILY_THRESHOLD = 0.25


def revision_snapshot(profile: ResearcherProfile) -> dict | None:
    if profile.last_analyzed_at is None and profile.integrity_breakdown is None and profile.integrity_score is None:
        return None
    snapshot = {key: getattr(profile, key) for key in (
        "official_h_index", "official_citation_count", "adjusted_h_index",
        "adjusted_citation_count", "integrity_score", "self_citation_rate",
        "topic_relevance_score", "total_publications", "citation_ring_flags",
        "integrity_breakdown", "model_metadata",
    )}
    snapshot["captured_at"] = profile.last_analyzed_at
    return snapshot


class AcademicIntegrityOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._warnings: list[dict] = []
        self._apis_used: list[str] = []
        self._fallback_used = False
        self._previous_snapshot = None
        self._snapshot_prepared = False
        self._revision_captured = False

    def _track_api(self, name: str) -> None:
        if name not in self._apis_used:
            self._apis_used.append(name)

    def _capture_revision(self, profile: ResearcherProfile) -> None:
        self._revision_captured = True
        self._previous_snapshot = revision_snapshot(profile)

    def restore_previous_revision(self, payload: dict) -> None:
        """Use the revision captured at submission, including after a retry."""
        self._previous_snapshot = dict(payload["values"]) if payload["has_revision"] else None
        if self._previous_snapshot and isinstance(self._previous_snapshot.get("captured_at"), str):
            self._previous_snapshot["captured_at"] = datetime.fromisoformat(self._previous_snapshot["captured_at"])
        self._revision_captured = True
        self._snapshot_prepared = True

    async def capture_previous_revision(self, profile_id: str) -> None:
        """Call before the separate collector changes any profile metrics."""
        result = await self.db.execute(select(ResearcherProfile).where(ResearcherProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is not None:
            self._capture_revision(profile)
            self._snapshot_prepared = True

    async def record_failed_attempt(self, profile_id: str, stage: Literal["data_collection_failed", "analysis_failed"] = "data_collection_failed") -> None:
        """A collector failure cannot leave the previous assessment current."""
        from app.services.academic_integrity import PROMPT_HASHES, PROMPT_VERSION, compute_live_prompt_hashes
        from app.governance import check_prompt_drift

        result = await self.db.execute(select(ResearcherProfile).where(ResearcherProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            return
        if not self._revision_captured:
            self._capture_revision(profile)
        self._prompt_version = PROMPT_VERSION
        self._prompt_hashes_live = compute_live_prompt_hashes()
        self._prompt_drift_detected = check_prompt_drift(
            engine="academic_integrity", expected=PROMPT_HASHES, live=self._prompt_hashes_live,
        )
        self._warnings.append({"type": stage})
        profile.official_h_index = None
        profile.official_citation_count = None
        await self._save_results(profile, [], {}, {}, unavailable_adjustment(
            "Researcher analysis failed; no current citation assessment is available.",
            [stage],
        ), terminal_status="failed")
        self._snapshot_prepared = False

    async def run_pipeline_streaming(self, profile_id: str) -> AsyncGenerator[dict, None]:
        """Run the full pipeline, yielding progress events for SSE."""
        self._warnings = []
        self._apis_used = []
        self._fallback_used = False

        # Governance snapshot — same contract as the source-verification
        # orchestrator. Deferred import to avoid the package <-> module
        # circular at top-level.
        from app.services.academic_integrity import (
            PROMPT_HASHES,
            PROMPT_VERSION,
            compute_live_prompt_hashes,
        )
        from app.governance import check_prompt_drift

        self._prompt_version = PROMPT_VERSION
        self._prompt_hashes_live = compute_live_prompt_hashes()
        self._prompt_drift_detected = check_prompt_drift(
            engine="academic_integrity",
            expected=PROMPT_HASHES,
            live=self._prompt_hashes_live,
        )

        result = await self.db.execute(
            select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            yield {"step": "error", "status": "failed", "detail": "Profile not found", "progress": 0}
            return

        # Capture the prior revision before resolution overwrites official
        # metrics. Unavailable revisions also need history and row replacement.
        if not self._snapshot_prepared:
            self._capture_revision(profile)
        self._snapshot_prepared = False

        # Telemetry plumbing: stash user_id + profile_id on ContextVars so
        # the centralized Gemini client can attribute its usage row to
        # this pipeline without us threading the id through every helper.
        from app.context import current_researcher_profile_id, current_user_id

        current_user_id.set(profile.user_id)
        current_researcher_profile_id.set(profile.id)

        profile.analysis_status = "processing"
        await self.db.commit()
        yield {"step": "started", "status": "processing", "detail": "Analysis started", "progress": 0.05}

        # Step 1: Resolve researcher profile
        yield {"step": "resolving", "status": "processing", "detail": "Looking up researcher...", "progress": 0.1}
        try:
            researcher_data = await resolve_researcher(
                name=profile.researcher_name,
                scopus_id=profile.scopus_id,
                google_scholar_id=profile.google_scholar_id,
                orcid=profile.orcid,
            )
            self._track_api("semantic_scholar")
            if profile.scopus_id:
                self._track_api("scopus")
            if profile.google_scholar_id:
                self._track_api("google_scholar")
            if profile.orcid:
                self._track_api("orcid")
        except Exception as e:
            logger.exception("Researcher resolution failed")
            researcher_data = None
            self._warnings.append({"type": "resolve_failed", "error": type(e).__name__})
            yield {"step": "resolving", "status": "error", "detail": str(e), "progress": 0.15}

        if not researcher_data or not researcher_data.get("s2_id"):
            profile.official_h_index = None
            profile.official_citation_count = None
            self._warnings.append({"type": "resolve_failed"})
            await self._save_results(profile, [], {}, {}, unavailable_adjustment(
                "Researcher identity could not be resolved; no citation assessment was performed.",
                [w["type"] for w in self._warnings],
            ), terminal_status="failed")
            yield {
                "step": "error", "status": "failed",
                "detail": "Could not find researcher in academic databases. Try providing an ORCID or full name.",
                "progress": 1.0,
            }
            return

        s2_id = researcher_data["s2_id"]
        profile.researcher_name = researcher_data.get("name") or profile.researcher_name
        profile.institution = researcher_data.get("institution") or profile.institution
        # Preserve genuine zeroes and do not reuse stale metrics when a fresh
        # provider response has no value. Previous metrics live in the snapshot.
        profile.official_h_index = researcher_data.get("h_index")
        profile.official_citation_count = researcher_data.get("citation_count")
        if researcher_data.get("orcid"):
            profile.orcid = researcher_data["orcid"]
        await self.db.commit()
        yield {"step": "resolving", "status": "done", "detail": f"Found: {profile.researcher_name}", "progress": 0.2}

        # Step 2: Fetch publications
        yield {"step": "publications", "status": "processing", "detail": "Fetching publications...", "progress": 0.25}
        try:
            publications = await fetch_publications(s2_id, limit=100)
            yield {"step": "publications", "status": "done", "detail": f"Found {len(publications)} papers", "progress": 0.35}
        except Exception as e:
            logger.exception("Publications fetch failed")
            publications = []
            self._warnings.append({"type": "publications_fetch_failed", "error": type(e).__name__})
            yield {"step": "publications", "status": "error", "detail": str(e), "progress": 0.35}

        if not publications:
            self._warnings.append({"type": "publications_unavailable"})
            await self._save_results(profile, [], {}, {}, unavailable_adjustment(
                "No publication inventory was available; no citation assessment was performed.",
                [w["type"] for w in self._warnings],
            ), terminal_status="failed")
            yield {"step": "error", "status": "failed", "detail": "No publications found", "progress": 1.0}
            return

        # Step 3: Build citation graph
        yield {"step": "citation_graph", "status": "processing", "detail": "Building citation network...", "progress": 0.4}
        try:
            graph_data = await build_citation_graph(s2_id, publications, max_papers_to_check=15)
            yield {
                "step": "citation_graph", "status": "done",
                "detail": f"Analyzed {graph_data['total_citations_checked']} citations, {len(graph_data['nodes'])} nodes",
                "progress": 0.55,
            }
        except Exception as e:
            logger.exception("Citation graph build failed")
            graph_data = {
                "nodes": [], "edges": [], "citing_authors": {},
                "self_citations": 0, "total_citations_checked": 0,
                "per_paper_citations": {},
                "citation_evidence_status": "unavailable",
            }
            self._warnings.append({"type": "citation_graph_failed", "error": type(e).__name__})
            yield {"step": "citation_graph", "status": "error", "detail": str(e), "progress": 0.55}

        # Step 4: Detect rings (field-aware thresholds)
        yield {"step": "ring_detection", "status": "processing", "detail": "Analyzing citation patterns...", "progress": 0.6}
        try:
            field = self._infer_field(researcher_data, profile)
            ring_data = detect_rings(graph_data, publications, field=field)
            flag_count = len(ring_data.get("flags", []))
            yield {
                "step": "ring_detection", "status": "done",
                "detail": f"Found {flag_count} flag(s) (field: {field or 'default'})",
                "progress": 0.7,
            }
        except Exception as e:
            logger.exception("Ring detection failed")
            ring_data = {
                "suspicious_pairs": [], "potential_rings": [], "self_citation_rate": None,
                "self_citation_status": "unavailable", "citation_velocity_anomalies": [], "flags": [],
                "total_citations_checked": graph_data.get("total_citations_checked", 0),
                "citation_evidence_status": "unavailable",
            }
            self._warnings.append({"type": "ring_detection_failed", "error": type(e).__name__})
            yield {"step": "ring_detection", "status": "error", "detail": str(e), "progress": 0.7}

        # Step 5: Topic analysis
        yield {"step": "topic_analysis", "status": "processing", "detail": "Checking topic relevance...", "progress": 0.75}
        try:
            publications = await analyze_topic_relevance(publications)
            if any(p.get("topic_match_score") is not None for p in publications):
                self._track_api("gemini")
            missing_topics = [p for p in publications if p.get("journal") and p.get("topic_match_score") is None]
            if missing_topics:
                self._warnings.append({"type": "topic_analysis_unavailable", "papers_unassessed": len(missing_topics)})
                yield {"step": "topic_analysis", "status": "warning", "detail": "Topic analysis unavailable for some eligible papers", "progress": 0.8}
            else:
                yield {"step": "topic_analysis", "status": "done", "detail": "Topic analysis complete" if any(p.get("journal") for p in publications) else "No journal metadata for topic assessment", "progress": 0.8}
        except Exception as e:
            logger.exception("Topic analysis failed")
            self._warnings.append({"type": "topic_analysis_failed", "error": type(e).__name__})
            yield {"step": "topic_analysis", "status": "error", "detail": str(e), "progress": 0.8}

        # Step 6: Calculate adjusted ratings
        yield {"step": "adjusting", "status": "processing", "detail": "Calculating adjusted metrics...", "progress": 0.85}
        try:
            adjusted = calculate_adjusted_metrics(
                publications, ring_data,
                profile.official_h_index, profile.official_citation_count,
                processing_warnings=self._warnings,
            )
            yield {"step": "adjusting", "status": "done", "detail": adjusted.get("explanation", "")[:100], "progress": 0.9}
        except Exception as e:
            logger.exception("Rating adjustment failed")
            self._warnings.append({"type": "rating_adjustment_failed", "error": type(e).__name__})
            adjusted = unavailable_adjustment("Rating adjustment failed; assessment unavailable.",
                                              [w["type"] for w in self._warnings])
            yield {"step": "adjusting", "status": "error", "detail": str(e), "progress": 0.9}

        # Step 7: Save everything
        yield {"step": "saving", "status": "processing", "detail": "Saving results...", "progress": 0.92}
        try:
            await self._save_results(profile, publications, ring_data, graph_data, adjusted)
            yield {"step": "saving", "status": "done", "detail": "Results saved", "progress": 0.98}
        except Exception as e:
            logger.exception("Failed to save results")
            profile.analysis_status = "failed"
            profile.last_analyzed_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield {"step": "error", "status": "failed", "detail": str(e), "progress": 1.0}
            return

        yield {"step": "complete", "status": "completed", "detail": "Analysis complete", "progress": 1.0}

    @staticmethod
    def _infer_field(researcher_data: dict | None, profile: ResearcherProfile) -> str | None:
        """Best-effort field inference for ring threshold tuning.

        Sources, in order: Scopus subject_areas, ResearcherProfile.research_fields.
        Returns None if we can't tell — ring_detector falls back to "default".
        """
        if researcher_data:
            areas = researcher_data.get("subject_areas") or []
            if areas:
                return str(areas[0]).lower()
        if profile.research_fields:
            fields = profile.research_fields
            if isinstance(fields, list) and fields:
                return str(fields[0]).lower()
        return None

    async def _save_results(
        self,
        profile: ResearcherProfile,
        publications: list[dict],
        ring_data: dict,
        graph_data: dict,
        adjusted: dict,
        terminal_status: str = "completed",
    ) -> None:
        """Persist all analysis results to the database.

        Capture the prior revision collected before provider resolution,
        including unavailable assessments. Replace per-publication rows on
        every attempt so unavailable reruns cannot accumulate stale findings.

        Also clears prior PublicationAnalysis rows on re-run to avoid
        duplicate-row pile-up; the snapshot preserves the historical
        scalar metrics, which is what users actually compare over time.
        """
        # ── Snapshot the prior state, if any ───────────────────────────────
        if self._previous_snapshot is not None:
            from app.models.researcher_snapshot import ResearcherSnapshot

            self.db.add(
                ResearcherSnapshot(
                    id=str(uuid.uuid4()),
                    researcher_profile_id=profile.id,
                    **self._previous_snapshot,
                )
            )

        # A previous unavailable assessment may also have publication rows.
        from sqlalchemy import delete as sa_delete

        await self.db.execute(
            sa_delete(PublicationAnalysis).where(
                PublicationAnalysis.researcher_profile_id == profile.id
            )
        )

        per_paper = graph_data.get("per_paper_citations", {})

        for pub in publications:
            paper_id = pub.get("paper_id")
            paper_stats = per_paper.get(paper_id, {})
            paper_total = paper_stats.get("total", 0)
            paper_self = paper_stats.get("self_citations", 0)

            # Heavily self-cited if a sizeable share of citations are self
            is_self_cited = (
                paper_total > 0
                and (paper_self / paper_total) > SELF_CITED_HEAVILY_THRESHOLD
            )

            flags = []
            topic_score = pub.get("topic_match_score")
            if topic_score is not None and topic_score < 0.3:
                flags.append("Low topic relevance to journal")
            if is_self_cited:
                self_rate = paper_self / max(paper_total, 1)
                flags.append(f"Heavily self-cited ({self_rate:.0%} of citations)")

            pub_record = PublicationAnalysis(
                id=str(uuid.uuid4()),
                researcher_profile_id=profile.id,
                title=pub.get("title", "Untitled"),
                journal=pub.get("journal"),
                year=pub.get("year"),
                doi=pub.get("doi"),
                citation_count=pub.get("citation_count", 0),
                suspicious_citations=0,  # Incoming concentration is not evidence of suspicious citations.
                topic_match_score=topic_score,
                is_self_cited_heavily=is_self_cited,
                flags=flags if flags else None,
            )
            self.db.add(pub_record)

        # Update profile with adjusted metrics
        profile.adjusted_h_index = adjusted["adjusted_h_index"]
        profile.adjusted_citation_count = adjusted["adjusted_citation_count"]
        profile.integrity_score = adjusted["integrity_score"]
        profile.self_citation_rate = adjusted["self_citation_rate"]
        profile.topic_relevance_score = adjusted.get("topic_relevance_score")
        profile.citation_ring_flags = {
            "rings": [],
            "suspicious_pairs": [],
            "frequent_citers": ring_data.get("frequent_citers", []),
            "citation_concentration": ring_data.get("citation_concentration", []),
            "citation_evidence_status": ring_data.get("citation_evidence_status", "unavailable"),
            "coverage": graph_data.get("coverage", {}),
            "limitation": ring_data.get("limitation", "Incoming citation samples do not establish citation rings or misconduct."),
            "flags": ring_data.get("flags", []),
            "graph": {
                "nodes": graph_data.get("nodes", [])[:50],
                "edges": graph_data.get("edges", [])[:100],
            },
        }
        profile.integrity_breakdown = adjusted.get("breakdown")
        profile.total_publications = len(publications) if publications else None
        if adjusted["integrity_score"] is None:
            self._warnings.append({"type": "insufficient_citation_evidence"})
        from app.schemas.governance import build_model_metadata

        profile.model_metadata = build_model_metadata(
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
                "publications_count": len(publications),
                "citations_checked": graph_data.get("total_citations_checked", 0),
                "field_used": ring_data.get("field_used"),
                "thresholds_used": ring_data.get("thresholds_used"),
                "citation_coverage": graph_data.get("coverage", {}),
                "assessment_status": "unavailable" if adjusted["integrity_score"] is None else "available",
            },
        )
        profile.analysis_status = terminal_status
        profile.last_analyzed_at = datetime.now(timezone.utc)

        await self.db.commit()
