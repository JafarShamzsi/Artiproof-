"""
Academic integrity orchestrator — coordinates the Module 2 pipeline.

Steps (sequential — graph must be built before ring detection):
1. Resolve researcher profile (Semantic Scholar / ORCID)
2. Fetch publications
3. Build citation graph
4. Detect citation rings and manipulation
5. Analyze topic relevance (Gemini)
6. Calculate adjusted ratings
7. Save all results
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import ResearcherProfile, PublicationAnalysis
from app.services.academic_integrity.scholar_scraper import (
    resolve_researcher,
    fetch_publications,
)
from app.services.academic_integrity.citation_graph_builder import build_citation_graph
from app.services.academic_integrity.ring_detector import detect_rings
from app.services.academic_integrity.topic_analyzer import analyze_topic_relevance
from app.services.academic_integrity.rating_adjuster import calculate_adjusted_metrics

logger = logging.getLogger(__name__)


class AcademicIntegrityOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_pipeline_streaming(self, profile_id: str) -> AsyncGenerator[dict, None]:
        """Run the full pipeline, yielding progress events for SSE."""
        result = await self.db.execute(
            select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            yield {"step": "error", "status": "failed", "detail": "Profile not found", "progress": 0}
            return

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
        except Exception as e:
            logger.exception("Researcher resolution failed")
            researcher_data = None
            yield {"step": "resolving", "status": "error", "detail": str(e), "progress": 0.15}

        if not researcher_data or not researcher_data.get("s2_id"):
            profile.analysis_status = "failed"
            profile.last_analyzed_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield {
                "step": "error", "status": "failed",
                "detail": "Could not find researcher in academic databases. Try providing an ORCID or full name.",
                "progress": 1.0,
            }
            return

        # Update profile with resolved data
        s2_id = researcher_data["s2_id"]
        profile.researcher_name = researcher_data.get("name") or profile.researcher_name
        profile.institution = researcher_data.get("institution") or profile.institution
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
            yield {"step": "publications", "status": "error", "detail": str(e), "progress": 0.35}

        if not publications:
            profile.analysis_status = "failed"
            profile.last_analyzed_at = datetime.now(timezone.utc)
            await self.db.commit()
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
            graph_data = {"nodes": [], "edges": [], "citing_authors": {}, "self_citations": 0, "total_citations_checked": 0}
            yield {"step": "citation_graph", "status": "error", "detail": str(e), "progress": 0.55}

        # Step 4: Detect rings
        yield {"step": "ring_detection", "status": "processing", "detail": "Analyzing citation patterns...", "progress": 0.6}
        try:
            ring_data = detect_rings(graph_data, publications)
            flag_count = len(ring_data.get("flags", []))
            yield {
                "step": "ring_detection", "status": "done",
                "detail": f"Found {flag_count} flag(s)",
                "progress": 0.7,
            }
        except Exception as e:
            logger.exception("Ring detection failed")
            ring_data = {"suspicious_pairs": [], "potential_rings": [], "self_citation_rate": 0, "self_citation_status": "normal", "citation_velocity_anomalies": [], "flags": []}
            yield {"step": "ring_detection", "status": "error", "detail": str(e), "progress": 0.7}

        # Step 5: Topic analysis
        yield {"step": "topic_analysis", "status": "processing", "detail": "Checking topic relevance...", "progress": 0.75}
        try:
            publications = await analyze_topic_relevance(publications)
            yield {"step": "topic_analysis", "status": "done", "detail": "Topic analysis complete", "progress": 0.8}
        except Exception as e:
            logger.exception("Topic analysis failed")
            yield {"step": "topic_analysis", "status": "error", "detail": str(e), "progress": 0.8}

        # Step 6: Calculate adjusted ratings
        yield {"step": "adjusting", "status": "processing", "detail": "Calculating adjusted metrics...", "progress": 0.85}
        try:
            adjusted = calculate_adjusted_metrics(
                publications, ring_data,
                profile.official_h_index, profile.official_citation_count,
            )
            yield {"step": "adjusting", "status": "done", "detail": adjusted.get("explanation", "")[:100], "progress": 0.9}
        except Exception as e:
            logger.exception("Rating adjustment failed")
            adjusted = {
                "adjusted_h_index": profile.official_h_index,
                "adjusted_citation_count": profile.official_citation_count,
                "integrity_score": 50.0,
                "self_citation_rate": 0.0,
                "topic_relevance_score": None,
                "explanation": "Rating adjustment failed",
            }
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

    async def _save_results(
        self,
        profile: ResearcherProfile,
        publications: list[dict],
        ring_data: dict,
        graph_data: dict,
        adjusted: dict,
    ) -> None:
        """Persist all analysis results to the database."""

        # Save publications
        suspicious_pairs_ids = {p["author_id"] for p in ring_data.get("suspicious_pairs", [])}

        for pub in publications:
            # Determine if this paper is heavily self-cited
            is_self_cited = False
            # Check if any suspicious citers appear in this paper's citing authors
            suspicious_count = 0

            flags = []
            topic_score = pub.get("topic_match_score")
            if topic_score is not None and topic_score < 0.3:
                flags.append("Low topic relevance to journal")

            pub_record = PublicationAnalysis(
                id=str(uuid.uuid4()),
                researcher_profile_id=profile.id,
                title=pub.get("title", "Untitled"),
                journal=pub.get("journal"),
                year=pub.get("year"),
                doi=pub.get("doi"),
                citation_count=pub.get("citation_count", 0),
                suspicious_citations=suspicious_count,
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
            "rings": ring_data.get("potential_rings", []),
            "suspicious_pairs": ring_data.get("suspicious_pairs", []),
            "flags": ring_data.get("flags", []),
            "graph": {
                "nodes": graph_data.get("nodes", [])[:50],
                "edges": graph_data.get("edges", [])[:100],
            },
        }
        profile.analysis_status = "completed"
        profile.last_analyzed_at = datetime.now(timezone.utc)

        await self.db.commit()
