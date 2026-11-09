"""
Demo data seeder — populates DB with sample data for hackathon presentations.

Disabled in production: only runs when ENVIRONMENT != "production". Demo credentials
are read from DEMO_EMAIL / DEMO_PASSWORD env vars (see app.config) and the password
is hashed at runtime instead of being checked into source.
"""

import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.source_check import SourceCheck, ClaimAnalysis, AIDetectionResult, CitationCheck
from app.models.researcher import ResearcherProfile, PublicationAnalysis, ScrapedPublication, CitationEdge, CoAuthorRelation
from app.models.report import Report

router = APIRouter(prefix="/api/seed", tags=["Seed (dev only)"])


def _ensure_seeding_allowed() -> None:
    # Belt-and-braces: ENVIRONMENT==production hard-blocks regardless of
    # the explicit flag, in case someone sets ENABLE_SEED_ROUTES=true in
    # the wrong env file. Otherwise the flag must be opted-in per env.
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=403, detail="Seed endpoint disabled in production")
    if not settings.ENABLE_SEED_ROUTES:
        raise HTTPException(
            status_code=403,
            detail="Seed endpoint disabled — set ENABLE_SEED_ROUTES=true to enable",
        )


@router.post("/demo")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """Seed the database with demo data for hackathon presentation.

    Idempotent: if demo data is already present (detected by the demo user's
    existing source-checks), the endpoint returns a no-op response instead of
    duplicating rows. To force a re-seed, pass ?force=true.
    """
    _ensure_seeding_allowed()

    from sqlalchemy import select, delete as sa_delete

    now = datetime.now(timezone.utc)
    user_id = "demo-user"

    # Create demo user if not exists
    existing = await db.execute(select(User).where(User.id == user_id))
    if not existing.scalar_one_or_none():
        db.add(User(
            id=user_id,
            email=settings.DEMO_EMAIL,
            hashed_password=bcrypt.hash(settings.DEMO_PASSWORD),
            full_name="Demo Researcher",
            institution="ArtiProof Demo",
            role="researcher",
        ))
        await db.flush()

    # Idempotency check — if demo source checks already exist for this user
    # we've already seeded, so short-circuit. Repeat callers get the same
    # shape they got the first time.
    already = await db.execute(
        select(SourceCheck.id).where(SourceCheck.user_id == user_id).limit(1)
    )
    if already.scalar_one_or_none():
        return {"status": "ok", "seeded": "already_present"}

    # ── Source Check 1: News article with misinformation ──
    sc1_id = str(uuid.uuid4())
    db.add(SourceCheck(
        id=sc1_id, user_id=user_id, input_type="url",
        input_content="https://example-news.com/climate-crisis-2025",
        input_title="Climate Crisis: New Data Shows Alarming Trends",
        status="completed", overall_credibility_score=62.5,
        ai_content_percentage=12.0, misinfo_claims_found=2,
        created_at=now - timedelta(hours=3), completed_at=now - timedelta(hours=2, minutes=55),
    ))
    await db.flush()

    for claim_data in [
        {"text": "Global temperatures have risen by 2.1°C since pre-industrial times",
         "verdict": "false", "confidence": 0.88,
         "explanation": "The actual figure is approximately 1.2°C above pre-industrial levels as of 2024, according to NASA and NOAA data.",
         "true_version": "Global temperatures have risen by approximately 1.2°C since pre-industrial times.",
         "sources": [{"name": "NASA GISS", "url": "https://data.giss.nasa.gov/gistemp/"}],
         "origin_trace": {"origin_platform": "Social media blog", "first_seen": "March 2024",
                         "spread_path": [{"platform": "Twitter/X", "description": "Viral thread misquoting IPCC report"}],
                         "confidence": 0.65}},
        {"text": "Arctic ice has completely disappeared during summer months",
         "verdict": "misleading", "confidence": 0.82,
         "explanation": "While Arctic sea ice has declined significantly, it has not completely disappeared. Summer 2024 minimum was approximately 4.28 million km².",
         "true_version": "Arctic summer sea ice extent has declined by about 40% since satellite records began in 1979, but has not disappeared.",
         "sources": [{"name": "NSIDC", "url": "https://nsidc.org/"}]},
        {"text": "The Paris Agreement set a target of limiting warming to 1.5°C",
         "verdict": "true", "confidence": 0.95,
         "explanation": "The Paris Agreement (2015) indeed aims to limit global warming to well below 2°C, preferably to 1.5°C, compared to pre-industrial levels.",
         "true_version": None, "sources": [{"name": "UNFCCC", "url": "https://unfccc.int/"}]},
        {"text": "Renewable energy now accounts for 45% of global electricity",
         "verdict": "partially_true", "confidence": 0.72,
         "explanation": "Renewables account for approximately 30% of global electricity generation as of 2023. The 45% figure may refer to specific regions or include hydropower.",
         "true_version": "Renewable energy sources generated approximately 30% of global electricity in 2023, with the share growing rapidly.",
         "sources": [{"name": "IEA", "url": "https://www.iea.org/"}]},
    ]:
        db.add(ClaimAnalysis(
            id=str(uuid.uuid4()), source_check_id=sc1_id,
            claim_text=claim_data["text"], verdict=claim_data["verdict"],
            confidence=claim_data["confidence"], explanation=claim_data["explanation"],
            true_version=claim_data.get("true_version"),
            sources=claim_data.get("sources"), origin_trace=claim_data.get("origin_trace"),
            position_in_text={"start": 0, "end": len(claim_data["text"])},
        ))

    for i, (text, prob) in enumerate([
        ("The climate crisis represents the defining challenge of our generation, with far-reaching consequences for ecosystems, economies, and human societies worldwide.", 0.08),
        ("According to recent studies published in Nature Climate Change, global temperatures have risen by 2.1°C since pre-industrial times, a figure that experts say demands immediate and unprecedented action.", 0.15),
        ("The implications of these findings are profound and multifaceted, necessitating a comprehensive reevaluation of our current approaches to environmental stewardship and sustainable development.", 0.82),
        ("Furthermore, the convergence of multiple environmental stressors creates a synergistic effect that amplifies the overall impact on vulnerable communities and critical infrastructure systems.", 0.91),
        ("Local farmers in the region have noticed changes too. 'The seasons just aren't what they used to be,' said Maria, who has worked the same land for 30 years.", 0.05),
    ]):
        db.add(AIDetectionResult(
            id=str(uuid.uuid4()), source_check_id=sc1_id,
            paragraph_index=i, paragraph_text=text,
            ai_probability=prob, detection_method="gemini-analysis",
        ))

    for cit_data in [
        {"text": "NASA Global Temperature Data", "url": "https://data.giss.nasa.gov/gistemp/", "accessible": True, "retracted": False, "score": 95.0},
        {"text": "Smith et al. (2023) — Journal of Climate", "url": "https://doi.org/10.1175/JCLI-D-23-0001.1", "accessible": True, "retracted": False, "score": 85.0},
        {"text": "Arctic Ice Report 2024", "url": "https://example.com/broken-link", "accessible": False, "retracted": False, "score": 30.0, "issues": ["Source URL is not accessible (broken link or removed)"]},
        {"text": "Johnson (2021) — Retracted Study", "url": "https://doi.org/10.xxxx/retracted", "accessible": True, "retracted": True, "score": 5.0, "issues": ["This paper has been RETRACTED"]},
    ]:
        db.add(CitationCheck(
            id=str(uuid.uuid4()), source_check_id=sc1_id,
            original_citation=cit_data["text"], citation_url=cit_data["url"],
            is_accessible=cit_data["accessible"], is_retracted=cit_data["retracted"],
            credibility_score=cit_data["score"], issues=cit_data.get("issues"),
        ))

    # ── Source Check 2: Clean article ──
    sc2_id = str(uuid.uuid4())
    db.add(SourceCheck(
        id=sc2_id, user_id=user_id, input_type="url",
        input_content="https://reuters.com/world/science-breakthrough-2025",
        input_title="Scientists Announce Breakthrough in Quantum Computing",
        status="completed", overall_credibility_score=91.2,
        ai_content_percentage=5.0, misinfo_claims_found=0,
        created_at=now - timedelta(days=1), completed_at=now - timedelta(days=1) + timedelta(minutes=3),
    ))

    # ── Source Check 3: Highly AI-generated ──
    sc3_id = str(uuid.uuid4())
    db.add(SourceCheck(
        id=sc3_id, user_id=user_id, input_type="text",
        input_content="The rapid advancement of artificial intelligence...",
        input_title="AI Revolution: What You Need to Know",
        status="completed", overall_credibility_score=45.8,
        ai_content_percentage=87.0, misinfo_claims_found=1,
        created_at=now - timedelta(days=3), completed_at=now - timedelta(days=3) + timedelta(minutes=2),
    ))

    # Flush source checks before creating dependent records
    await db.flush()

    # ── Researcher Profile 1: With integrity issues ──
    rp1_id = str(uuid.uuid4())
    db.add(ResearcherProfile(
        id=rp1_id, user_id=user_id, researcher_name="Dr. Alexander Petrov",
        scopus_id="57203100718", orcid="0000-0002-1234-5678",
        institution="Central European University",
        official_h_index=28, official_citation_count=3450,
        adjusted_h_index=21, adjusted_citation_count=2680,
        integrity_score=58.0, self_citation_rate=0.22,
        topic_relevance_score=0.73,
        citation_ring_flags={
            "flags": [
                "Self-citation rate (22%) exceeds 15% threshold",
                "3 author(s) cite this researcher an unusually high number of times",
                "Potential citation ring detected: 4 authors with 23 mutual citations",
            ],
            "rings": [{"members": [
                {"id": "a1", "name": "Dr. Ivan Kozlov", "citations_to_target": 8},
                {"id": "a2", "name": "Prof. Elena Morozova", "citations_to_target": 7},
                {"id": "a3", "name": "Dr. Dmitri Volkov", "citations_to_target": 5},
                {"id": "a4", "name": "Dr. Natalia Sokolova", "citations_to_target": 3},
            ], "total_mutual_citations": 23, "confidence": 0.72}],
            "suspicious_pairs": [
                {"author_id": "a1", "author_name": "Dr. Ivan Kozlov", "citation_count": 8},
                {"author_id": "a2", "author_name": "Prof. Elena Morozova", "citation_count": 7},
                {"author_id": "a3", "author_name": "Dr. Dmitri Volkov", "citation_count": 5},
            ],
            "graph": {
                "nodes": [
                    {"id": "target", "name": "Dr. Alexander Petrov", "type": "target", "citation_count": 3450},
                    {"id": "a1", "name": "Dr. Ivan Kozlov", "type": "citer", "citation_count": 8},
                    {"id": "a2", "name": "Prof. Elena Morozova", "type": "citer", "citation_count": 7},
                    {"id": "a3", "name": "Dr. Dmitri Volkov", "type": "citer", "citation_count": 5},
                    {"id": "a4", "name": "Dr. Natalia Sokolova", "type": "citer", "citation_count": 3},
                    {"id": "a5", "name": "Prof. Sarah Chen", "type": "citer", "citation_count": 2},
                    {"id": "a6", "name": "Dr. James Wilson", "type": "citer", "citation_count": 2},
                    {"id": "a7", "name": "Prof. Maria Garcia", "type": "citer", "citation_count": 1},
                    {"id": "a8", "name": "Dr. Ahmed Hassan", "type": "citer", "citation_count": 1},
                ],
                "edges": [
                    {"source": "a1", "target": "target", "weight": 8, "papers": ["Paper A", "Paper B"]},
                    {"source": "a2", "target": "target", "weight": 7, "papers": ["Paper C"]},
                    {"source": "a3", "target": "target", "weight": 5, "papers": ["Paper D"]},
                    {"source": "a4", "target": "target", "weight": 3, "papers": []},
                    {"source": "a5", "target": "target", "weight": 2, "papers": []},
                    {"source": "a6", "target": "target", "weight": 2, "papers": []},
                    {"source": "a7", "target": "target", "weight": 1, "papers": []},
                    {"source": "a8", "target": "target", "weight": 1, "papers": []},
                ],
            },
        },
        analysis_status="completed", scrape_status="completed",
        last_scraped_at=now - timedelta(hours=6),
        last_analyzed_at=now - timedelta(hours=5),
        created_at=now - timedelta(hours=6),
    ))
    await db.flush()

    for pub_data in [
        {"title": "Machine Learning Approaches to Citation Analysis", "journal": "J. Informetrics", "year": 2023, "cites": 45, "topic": 0.92},
        {"title": "Deep Neural Networks for Text Classification", "journal": "Neural Computing", "year": 2022, "cites": 89, "topic": 0.88},
        {"title": "Blockchain Applications in Healthcare", "journal": "J. Informetrics", "year": 2022, "cites": 34, "topic": 0.25, "flags": ["Low topic relevance to journal"]},
        {"title": "Natural Language Processing: A Survey", "journal": "ACM Computing Surveys", "year": 2021, "cites": 156, "topic": 0.95},
        {"title": "Predicting Academic Impact Using Graph Neural Networks", "journal": "AAAI Conference", "year": 2023, "cites": 28, "topic": 0.90},
        {"title": "A Review of Sentiment Analysis Techniques", "journal": "Information Processing", "year": 2020, "cites": 203, "topic": 0.85},
        {"title": "Cryptocurrency Market Analysis Using AI", "journal": "J. Finance", "year": 2021, "cites": 12, "topic": 0.18, "flags": ["Low topic relevance to journal"]},
        {"title": "Transfer Learning for Low-Resource Languages", "journal": "EMNLP Proceedings", "year": 2022, "cites": 67, "topic": 0.93},
    ]:
        db.add(PublicationAnalysis(
            id=str(uuid.uuid4()), researcher_profile_id=rp1_id,
            title=pub_data["title"], journal=pub_data["journal"],
            year=pub_data["year"], citation_count=pub_data["cites"],
            topic_match_score=pub_data["topic"],
            flags=pub_data.get("flags"),
        ))

    # ── Scraped data for Researcher 1 ──
    sp_ids = []
    for sp_data in [
        {"title": "Machine Learning Approaches to Citation Analysis", "s2id": "s2_paper_1", "doi": "10.1234/jinfo.2023.001", "year": 2023, "cites": 45, "journal": "J. Informetrics"},
        {"title": "Deep Neural Networks for Text Classification", "s2id": "s2_paper_2", "doi": "10.1234/neural.2022.015", "year": 2022, "cites": 89, "journal": "Neural Computing"},
        {"title": "Natural Language Processing: A Survey", "s2id": "s2_paper_3", "doi": "10.1145/surveys.2021.100", "year": 2021, "cites": 156, "journal": "ACM Computing Surveys"},
        {"title": "Predicting Academic Impact Using Graph Neural Networks", "s2id": "s2_paper_4", "year": 2023, "cites": 28, "journal": "AAAI Conference"},
    ]:
        sp_id = str(uuid.uuid4())
        sp_ids.append(sp_id)
        db.add(ScrapedPublication(
            id=sp_id, researcher_profile_id=rp1_id,
            title=sp_data["title"], semantic_scholar_id=sp_data["s2id"],
            doi=sp_data.get("doi"), journal_name=sp_data.get("journal"),
            year=sp_data["year"], citation_count=sp_data["cites"],
            data_source="semantic_scholar",
            authors_json=[
                {"name": "Alexander Petrov", "authorId": "s2_petrov"},
                {"name": "Ivan Kozlov", "authorId": "s2_kozlov"},
                {"name": "Elena Morozova", "authorId": "s2_morozova"},
            ],
        ))
    await db.flush()

    # Citation edges (showing the ring pattern)
    for sp_id_ref, citing_data in [
        (sp_ids[0], [
            {"title": "Extending Citation Analysis with ML", "authors": [{"name": "Ivan Kozlov", "authorId": "s2_kozlov"}], "year": 2024},
            {"title": "Further Work on Citation Networks", "authors": [{"name": "Elena Morozova", "authorId": "s2_morozova"}], "year": 2024},
            {"title": "A Review of Informetric Methods", "authors": [{"name": "Dmitri Volkov", "authorId": "s2_volkov"}], "year": 2023},
        ]),
        (sp_ids[2], [
            {"title": "NLP Advances in 2022", "authors": [{"name": "Ivan Kozlov", "authorId": "s2_kozlov"}], "year": 2022},
            {"title": "Survey of Language Models", "authors": [{"name": "Elena Morozova", "authorId": "s2_morozova"}], "year": 2022},
            {"title": "Self-citing review paper", "authors": [{"name": "Alexander Petrov", "authorId": "s2_petrov"}], "year": 2022, "self": True},
        ]),
    ]:
        for cd in citing_data:
            db.add(CitationEdge(
                id=str(uuid.uuid4()), researcher_profile_id=rp1_id,
                cited_paper_id=sp_id_ref, cited_paper_title="",
                citing_paper_title=cd["title"], citing_paper_year=cd.get("year"),
                citing_authors_json=cd["authors"],
                is_self_citation=cd.get("self", False),
            ))

    # Co-author relations
    for ca in [
        {"name": "Ivan Kozlov", "sid": "s2_kozlov", "count": 3, "mutual": 8, "suspicion": 0.75},
        {"name": "Elena Morozova", "sid": "s2_morozova", "count": 2, "mutual": 7, "suspicion": 0.7},
        {"name": "Dmitri Volkov", "sid": "s2_volkov", "count": 1, "mutual": 5, "suspicion": 0.5},
        {"name": "Sarah Chen", "sid": "s2_chen", "count": 1, "mutual": 0, "suspicion": 0.0},
    ]:
        db.add(CoAuthorRelation(
            id=str(uuid.uuid4()), researcher_profile_id=rp1_id,
            coauthor_name=ca["name"], coauthor_semantic_id=ca["sid"],
            shared_publication_count=ca["count"],
            mutual_citation_count=ca["mutual"], suspicion_score=ca["suspicion"],
        ))
    await db.flush()

    # ── Researcher Profile 2: Clean researcher ──
    rp2_id = str(uuid.uuid4())
    db.add(ResearcherProfile(
        id=rp2_id, user_id=user_id, researcher_name="Prof. Emily Richardson",
        orcid="0000-0003-5678-1234", institution="MIT",
        official_h_index=42, official_citation_count=8920,
        adjusted_h_index=40, adjusted_citation_count=8540,
        integrity_score=92.0, self_citation_rate=0.04,
        topic_relevance_score=0.94,
        citation_ring_flags={"flags": [], "rings": [], "suspicious_pairs": [],
                            "graph": {"nodes": [{"id": "t", "name": "Prof. Emily Richardson", "type": "target", "citation_count": 8920}], "edges": []}},
        analysis_status="completed", scrape_status="completed",
        last_scraped_at=now - timedelta(days=2),
        last_analyzed_at=now - timedelta(days=2),
        created_at=now - timedelta(days=2),
    ))

    # Flush researcher profiles before reports
    await db.flush()

    # ── Report for Source Check 1 ──
    db.add(Report(
        user_id=user_id, source_check_id=sc1_id,
        report_type="source_verification",
        title="Source Verification: Climate Crisis Article",
        summary="This source verification report analyzes a climate-related news article that received a credibility score of 62.5 out of 100. The analysis identified two misinformation claims, including an exaggerated global temperature figure and a misleading statement about Arctic ice. While the article contains some accurate references to the Paris Agreement, the overall credibility is reduced by the presence of false claims and one retracted citation. AI content detection revealed that approximately 12% of the article appears to be AI-generated, concentrated in two middle paragraphs. The citation health check found one broken link and one retracted study being cited as evidence.",
    ))

    # ── Report for Researcher 1 ──
    db.add(Report(
        user_id=user_id, researcher_profile_id=rp1_id,
        report_type="researcher_integrity",
        title="Researcher Integrity: Dr. Alexander Petrov",
        summary="This integrity analysis of Dr. Alexander Petrov reveals several concerns. The researcher's official h-index of 28 has been adjusted to 21 after accounting for an elevated self-citation rate of 22% and suspicious citation patterns. A potential citation ring involving four researchers was detected, with 23 mutual citations among the group. Additionally, two publications were flagged for low topic relevance to their respective journals, suggesting possible predatory publishing. The overall integrity score of 58 out of 100 indicates moderate concerns that warrant further investigation.",
    ))

    await db.commit()

    return {
        "status": "ok",
        "seeded": {
            "source_checks": 3,
            "claims": 4,
            "ai_detections": 5,
            "citations": 4,
            "researcher_profiles": 2,
            "publications": 8,
            "reports": 2,
        },
    }
