"""
Scrape orchestrator — coordinates all scrapers, deduplicates data, stores to DB.

This is the DATA COLLECTION layer. It runs BEFORE the integrity analysis pipeline.
Flow: resolve researcher → scrape profile → scrape publications → scrape citations → build coauthor network → enrich.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import (
    ResearcherProfile,
    ScrapedPublication,
    CitationEdge,
    CoAuthorRelation,
)
from app.services.scrapers import semantic_scholar as s2
from app.services.scrapers import crossref_client as crossref
from app.services.scrapers.google_scholar import ScraperBlockedError

logger = logging.getLogger(__name__)


class ScrapeOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_scraping(self, profile_id: str) -> AsyncGenerator[dict, None]:
        """Run the full scraping pipeline with SSE progress events."""
        result = await self.db.execute(
            select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            yield _event("error", "failed", "Profile not found", 0)
            return

        profile.scrape_status = "scraping"
        await self.db.commit()

        # ── Step 1: Resolve researcher across platforms ──
        yield _event("resolving", "processing", "Finding researcher in academic databases...", 0.05)
        try:
            resolved = await self._resolve_researcher(profile)
            await self._update_profile_ids(profile, resolved)
            yield _event("resolving", "done", f"Found: {resolved.get('name', 'Unknown')}", 0.1)
        except Exception as e:
            logger.exception("Researcher resolution failed")
            profile.scrape_status = "failed"
            profile.scrape_error = str(e)
            await self.db.commit()
            yield _event("error", "failed", f"Could not find researcher: {e}", 1.0)
            return

        s2_id = resolved.get("semantic_scholar_id")
        if not s2_id:
            profile.scrape_status = "failed"
            profile.scrape_error = "Researcher not found in Semantic Scholar"
            await self.db.commit()
            yield _event("error", "failed", "Researcher not found in Semantic Scholar. Try providing an ORCID or full name.", 1.0)
            return

        # ── Step 2: Scrape profile data ──
        yield _event("profile", "processing", "Fetching profile metrics...", 0.15)
        try:
            author_data = await s2.get_author(s2_id)
            if author_data:
                profile.researcher_name = author_data.get("name") or profile.researcher_name
                affiliations = author_data.get("affiliations") or []
                profile.institution = affiliations[0] if affiliations else profile.institution
                profile.official_h_index = author_data.get("hIndex")
                profile.official_citation_count = author_data.get("citationCount")
                profile.total_publications = author_data.get("paperCount")
                ext_ids = author_data.get("externalIds") or {}
                if ext_ids.get("ORCID"):
                    profile.orcid = profile.orcid or ext_ids["ORCID"]
                await self.db.commit()
            yield _event("profile", "done", f"h-index: {profile.official_h_index}, citations: {profile.official_citation_count}", 0.2)
        except Exception as e:
            logger.exception("Profile scrape failed")
            yield _event("profile", "error", str(e), 0.2)

        # Try Google Scholar for i10-index and interests (optional, non-blocking)
        if profile.google_scholar_id:
            try:
                from app.services.scrapers.google_scholar import scrape_profile as gs_profile
                gs_data = await gs_profile(profile.google_scholar_id)
                profile.i10_index = gs_data.get("i10_index")
                profile.research_fields = gs_data.get("interests")
                await self.db.commit()
            except ScraperBlockedError:
                logger.info("Google Scholar blocked, continuing without GS data")
            except Exception:
                pass

        # ── Step 3: Scrape publications ──
        yield _event("publications", "processing", "Fetching publications...", 0.25)
        try:
            papers = await s2.get_author_papers(s2_id, limit=500)
            pub_count = 0
            for p in papers:
                ext_ids = p.get("externalIds") or {}
                pub = ScrapedPublication(
                    id=str(uuid.uuid4()),
                    researcher_profile_id=profile_id,
                    title=p.get("title", "Untitled"),
                    doi=ext_ids.get("DOI"),
                    semantic_scholar_id=p.get("paperId"),
                    abstract=p.get("abstract"),
                    journal_name=(p.get("journal") or {}).get("name"),
                    venue=p.get("venue"),
                    year=p.get("year"),
                    publication_type=(p.get("publicationTypes") or [None])[0],
                    citation_count=p.get("citationCount", 0),
                    influential_citation_count=p.get("influentialCitationCount", 0),
                    reference_count=p.get("referenceCount", 0),
                    authors_json=[
                        {"name": a.get("name"), "authorId": a.get("authorId")}
                        for a in (p.get("authors") or [])
                    ],
                    data_source="semantic_scholar",
                )
                self.db.add(pub)
                pub_count += 1

            await self.db.commit()
            yield _event("publications", "done", f"Scraped {pub_count} publications", 0.4)
        except Exception as e:
            logger.exception("Publication scrape failed")
            yield _event("publications", "error", str(e), 0.4)
            papers = []

        if not papers:
            profile.scrape_status = "completed"
            profile.last_scraped_at = datetime.now(timezone.utc)
            await self.db.commit()
            yield _event("complete", "completed", "Scraping complete (no publications found)", 1.0)
            return

        # ── Step 4: Scrape citations for top papers ──
        yield _event("citations", "processing", "Scraping citation data for top papers...", 0.45)
        try:
            edge_count = await self._scrape_citations(profile_id, profile.researcher_name, papers)
            yield _event("citations", "done", f"Collected {edge_count} citation edges", 0.7)
        except Exception as e:
            logger.exception("Citation scrape failed")
            yield _event("citations", "error", str(e), 0.7)

        # ── Step 5: Build co-author network ──
        yield _event("coauthors", "processing", "Building co-author network...", 0.75)
        try:
            coauthor_count = await self._build_coauthor_network(profile_id, profile.researcher_name, papers)
            yield _event("coauthors", "done", f"Found {coauthor_count} co-authors", 0.8)
        except Exception as e:
            logger.exception("Co-author network build failed")
            yield _event("coauthors", "error", str(e), 0.8)

        # ── Step 6: Enrich with CrossRef ──
        yield _event("enrichment", "processing", "Enriching data from CrossRef...", 0.85)
        try:
            enriched = await self._enrich_with_crossref(profile_id)
            yield _event("enrichment", "done", f"Enriched {enriched} papers", 0.9)
        except Exception as e:
            logger.exception("CrossRef enrichment failed")
            yield _event("enrichment", "error", str(e), 0.9)

        # ── Step 7: Mark complete ──
        profile.scrape_status = "completed"
        profile.last_scraped_at = datetime.now(timezone.utc)
        await self.db.commit()
        yield _event("scraping_complete", "done", "Data collection complete", 0.95)

    async def _resolve_researcher(self, profile: ResearcherProfile) -> dict:
        """Find the researcher across platforms and return unified IDs."""
        result: dict = {}

        # Extract scholar ID from URL if provided
        if profile.google_scholar_url:
            match = re.search(r"user=([^&]+)", profile.google_scholar_url)
            if match:
                profile.google_scholar_id = match.group(1)

        # Try ORCID → Semantic Scholar
        if profile.orcid:
            result["orcid"] = profile.orcid
            s2_author = await s2.find_by_orcid(profile.orcid)
            if s2_author:
                result["semantic_scholar_id"] = s2_author.get("authorId")
                result["name"] = s2_author.get("name")

        # Try name search on Semantic Scholar
        name = profile.researcher_name
        if name and not result.get("semantic_scholar_id"):
            matches = await s2.search_author(name, limit=3)
            if matches:
                best = max(matches, key=lambda x: x.get("citationCount", 0))
                result["semantic_scholar_id"] = best.get("authorId")
                result.setdefault("name", best.get("name"))

        result.setdefault("name", name)
        result["scholar_id"] = profile.google_scholar_id
        result["scopus_id"] = profile.scopus_id
        return result

    async def _update_profile_ids(self, profile: ResearcherProfile, resolved: dict):
        if resolved.get("semantic_scholar_id"):
            profile.semantic_scholar_id = resolved["semantic_scholar_id"]
        if resolved.get("name"):
            profile.researcher_name = resolved["name"]
        if resolved.get("orcid"):
            profile.orcid = resolved["orcid"]
        await self.db.commit()

    async def _scrape_citations(self, profile_id: str, researcher_name: str, papers: list) -> int:
        """Scrape citation edges for top 50 most-cited papers."""
        sorted_papers = sorted(papers, key=lambda p: p.get("citationCount", 0), reverse=True)
        top = sorted_papers[:50]
        total = 0

        # Load DB records to get IDs
        db_pubs = await self.db.execute(
            select(ScrapedPublication).where(ScrapedPublication.researcher_profile_id == profile_id)
        )
        s2_to_db: dict[str, str] = {}
        for pub in db_pubs.scalars().all():
            if pub.semantic_scholar_id:
                s2_to_db[pub.semantic_scholar_id] = pub.id

        for paper in top:
            s2_id = paper.get("paperId")
            if not s2_id or s2_id not in s2_to_db:
                continue

            try:
                citations = await s2.get_paper_citations(s2_id, limit=200)
            except Exception:
                continue

            for cite in citations:
                citing = cite.get("citingPaper", {})
                if not citing or not citing.get("title"):
                    continue

                citing_authors = [
                    {"name": a.get("name"), "authorId": a.get("authorId")}
                    for a in (citing.get("authors") or [])
                ]

                is_self = any(
                    _names_match(a.get("name", ""), researcher_name)
                    for a in citing_authors
                )

                self.db.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    researcher_profile_id=profile_id,
                    cited_paper_id=s2_to_db[s2_id],
                    cited_paper_title=paper.get("title", ""),
                    citing_paper_title=citing.get("title", ""),
                    citing_paper_semantic_id=citing.get("paperId"),
                    citing_paper_year=citing.get("year"),
                    citing_authors_json=citing_authors,
                    is_self_citation=is_self,
                ))
                total += 1

            if total % 500 == 0:
                await self.db.commit()

        await self.db.commit()
        return total

    async def _build_coauthor_network(self, profile_id: str, researcher_name: str, papers: list) -> int:
        coauthor_map: dict[str, dict] = {}

        for paper in papers:
            for author in (paper.get("authors") or []):
                name = (author.get("name") or "").strip()
                if not name or _names_match(name, researcher_name):
                    continue

                key = name.lower()
                if key not in coauthor_map:
                    coauthor_map[key] = {"name": name, "semantic_id": author.get("authorId"), "count": 0}
                coauthor_map[key]["count"] += 1
                if author.get("authorId") and not coauthor_map[key]["semantic_id"]:
                    coauthor_map[key]["semantic_id"] = author["authorId"]

        for data in coauthor_map.values():
            self.db.add(CoAuthorRelation(
                id=str(uuid.uuid4()),
                researcher_profile_id=profile_id,
                coauthor_name=data["name"],
                coauthor_semantic_id=data.get("semantic_id"),
                shared_publication_count=data["count"],
            ))

        await self.db.commit()
        return len(coauthor_map)

    async def _enrich_with_crossref(self, profile_id: str) -> int:
        result = await self.db.execute(
            select(ScrapedPublication).where(
                ScrapedPublication.researcher_profile_id == profile_id,
                ScrapedPublication.doi.isnot(None),
                ScrapedPublication.abstract.is_(None),
            ).limit(50)
        )
        papers = result.scalars().all()
        enriched = 0

        for paper in papers:
            try:
                cr = await crossref.lookup_doi(paper.doi)
                if cr:
                    if cr.get("abstract"):
                        paper.abstract = cr["abstract"]
                    if cr.get("journal") and not paper.journal_name:
                        paper.journal_name = cr["journal"]
                    if cr.get("issn"):
                        paper.journal_issn = cr["issn"]
                    enriched += 1
            except Exception:
                continue

        await self.db.commit()
        return enriched


def _event(step: str, status: str, detail: str, progress: float) -> dict:
    return {"step": step, "status": status, "detail": detail, "progress": progress}


def _names_match(name1: str, name2: str) -> bool:
    if not name1 or not name2:
        return False
    n1, n2 = name1.lower().strip(), name2.lower().strip()
    if n1 == n2:
        return True
    p1, p2 = n1.split(), n2.split()
    if len(p1) >= 2 and len(p2) >= 2:
        if p1[-1] == p2[-1] and p1[0][0] == p2[0][0]:
            return True
    return False
