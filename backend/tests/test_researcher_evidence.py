"""Missing citation evidence must not become reassurance or ring accusations."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from contextlib import asynccontextmanager

import httpx
import pytest

from app.models.researcher import PublicationAnalysis
from app.models.researcher_snapshot import ResearcherSnapshot
from app.services.academic_integrity import citation_graph_builder as graph_builder
from app.services.academic_integrity import orchestrator as aio
from app.services.academic_integrity import scholar_scraper
from app.services.academic_integrity.rating_adjuster import calculate_adjusted_metrics
from app.services.academic_integrity.ring_detector import detect_rings


def _pub(paper_id="p1"):
    return {"paper_id": paper_id, "title": paper_id, "citation_count": 20}


@pytest.mark.asyncio
@pytest.mark.parametrize("status, payload, expected", [
    (200, {"data": []}, []), (429, {"error": "unavailable"}, None),
    (503, {}, None), (200, {"data": {}}, None), (200, {}, None),
])
async def test_provider_distinguishes_empty_page_from_unavailable(respx_mock, status, payload, expected):
    respx_mock.get(f"{scholar_scraper.S2_BASE}/paper/p1/citations").mock(
        return_value=httpx.Response(status, json=payload),
    )
    assert await scholar_scraper.fetch_paper_citations("p1") == expected


@pytest.mark.asyncio
async def test_provider_network_failure_is_not_an_empty_citation_sample(respx_mock):
    respx_mock.get(f"{scholar_scraper.S2_BASE}/paper/p1/citations").mock(side_effect=httpx.ConnectError("offline"))
    assert await scholar_scraper.fetch_paper_citations("p1") is None


@pytest.mark.asyncio
async def test_graph_deduplicates_relationships_and_authors(monkeypatch):
    citing = {"paper_id": "c1", "authors": [{"id": "target"}, {"id": "target"}, {"id": "other"}]}
    fetch = AsyncMock(return_value=[citing, citing])
    monkeypatch.setattr(graph_builder, "fetch_paper_citations", fetch)
    graph = await graph_builder.build_citation_graph("target", [_pub(), _pub()])
    assert graph["total_citations_checked"] == 1
    assert graph["self_citations"] == 1
    assert graph["per_paper_citations"]["p1"]["self_citations"] == 1
    assert graph["edges"][0]["weight"] == 1
    assert graph["relationships"] == [{"citing_paper_id": "c1", "cited_paper_id": "p1", "author_ids": ["target", "other"]}]
    fetch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("second_page", [None, [{"paper_id": "unknown-author", "authors": []}]])
async def test_partial_citation_evidence_withholds_assessment(monkeypatch, second_page):
    monkeypatch.setattr(graph_builder, "fetch_paper_citations", AsyncMock(side_effect=[
        [{"paper_id": "c1", "authors": [{"id": "other"}]}], second_page,
    ]))
    pubs = [_pub(), _pub("p2")]
    graph = await graph_builder.build_citation_graph("target", pubs)
    assert graph["citation_evidence_status"] == "partial"
    patterns = detect_rings(graph, pubs)
    result = calculate_adjusted_metrics(pubs, patterns, 2, 40)
    for key in ("integrity_score", "adjusted_h_index", "adjusted_citation_count", "self_citation_rate"):
        assert result[key] is None
    assert result["breakdown"]["confidence"] == 0


@pytest.mark.asyncio
async def test_star_graph_keeps_paper_evidence_without_ring_penalties(monkeypatch):
    rows = [{"paper_id": f"c{author}{i}", "authors": [{"id": author, "name": author}]}
            for author in ("a", "b", "c") for i in range(4)]
    monkeypatch.setattr(graph_builder, "fetch_paper_citations", AsyncMock(return_value=rows))
    pubs = [_pub()]
    graph = await graph_builder.build_citation_graph("target", pubs)
    patterns = detect_rings(graph, pubs)
    assert patterns["potential_rings"] == []
    assert patterns["suspicious_pairs"] == []
    assert len(patterns["citation_concentration"]) == 3
    for author in patterns["citation_concentration"]:
        assert len(author["relationships"]) == 4
        assert all(r["cited_paper_id"] == "p1" and author["id"] in r["author_ids"] for r in author["relationships"])
    result = calculate_adjusted_metrics(pubs, patterns, 1, 12)
    assert result["integrity_score"] == 100
    assert result["adjusted_citation_count"] == 12
    assert result["breakdown"]["adjustments"] == []
    assert "not a finding about misconduct" in result["explanation"]


@pytest.mark.parametrize("patterns", [
    {}, {"total_citations_checked": 0, "citation_evidence_status": "succeeded", "self_citation_rate": 0},
    {"total_citations_checked": 100, "citation_evidence_status": "unavailable", "self_citation_rate": 0},
])
def test_missing_or_zero_citations_cannot_produce_clearance(patterns):
    result = calculate_adjusted_metrics([_pub()] * 20, patterns, 10, 1000)
    assert result["integrity_score"] is None
    assert result["breakdown"]["final"] is None
    assert result["breakdown"]["confidence"] == 0


def test_conflicting_official_zero_does_not_fall_back_to_publication_metrics():
    result = calculate_adjusted_metrics([_pub()], {
        "total_citations_checked": 1, "citation_evidence_status": "succeeded", "self_citation_rate": 0,
    }, 0, 0)
    assert result["adjusted_h_index"] is None
    assert result["adjusted_citation_count"] is None
    assert "official_metrics_conflict" in result["breakdown"]["warnings"]


def _profile(score=70):
    return SimpleNamespace(
        id="profile", user_id="owner", researcher_name="Researcher", institution="Institute",
        scopus_id=None, google_scholar_id=None, orcid=None, research_fields=[],
        official_h_index=20, official_citation_count=1000, adjusted_h_index=10,
        adjusted_citation_count=800, integrity_score=score, self_citation_rate=0.2,
        topic_relevance_score=0.7, total_publications=20,
        citation_ring_flags={"rings": []}, integrity_breakdown={"final": score}, model_metadata={},
        last_analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), analysis_status="pending",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("previous_score", [70, None])
@pytest.mark.parametrize("failure", ["resolve", "publications", "graph", "patterns", "topic", "adjustment", "no_citations"])
async def test_pipeline_failures_clear_stale_assessments_and_snapshot_prior_revision(monkeypatch, failure, previous_score):
    profile = _profile(previous_score)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: profile)),
                         add=Mock(), commit=AsyncMock())
    monkeypatch.setattr(aio, "resolve_researcher", AsyncMock(return_value=None if failure == "resolve" else {
        "s2_id": "target", "name": "Researcher", "h_index": 0, "citation_count": 0,
    }))
    monkeypatch.setattr(aio, "fetch_publications", AsyncMock(return_value=[] if failure == "publications" else [_pub()]))
    graph = {"nodes": [], "edges": [], "total_citations_checked": 0 if failure == "no_citations" else 1,
             "self_citations": 0, "citation_evidence_status": "succeeded", "per_paper_citations": {}}
    monkeypatch.setattr(aio, "build_citation_graph", AsyncMock(side_effect=RuntimeError("offline")) if failure == "graph" else AsyncMock(return_value=graph))
    monkeypatch.setattr(aio, "analyze_topic_relevance", AsyncMock(side_effect=RuntimeError("offline")) if failure == "topic" else AsyncMock(return_value=[_pub()]))
    if failure == "patterns":
        monkeypatch.setattr(aio, "detect_rings", Mock(side_effect=RuntimeError("unavailable")))
    if failure == "adjustment":
        monkeypatch.setattr(aio, "calculate_adjusted_metrics", Mock(side_effect=RuntimeError("unavailable")))
    events = [e async for e in aio.AcademicIntegrityOrchestrator(db).run_pipeline_streaming(profile.id)]
    assert profile.integrity_score is None
    assert profile.adjusted_h_index is None
    assert profile.adjusted_citation_count is None
    assert profile.self_citation_rate is None
    assert profile.integrity_breakdown["final"] is None
    assert profile.integrity_breakdown["confidence"] == 0
    assert profile.integrity_breakdown["formula_version"] == "1.1"
    assert profile.citation_ring_flags["rings"] == []
    assert profile.citation_ring_flags["suspicious_pairs"] == []
    assert any(w["type"] == "insufficient_citation_evidence" for w in profile.model_metadata["processing_warnings"])
    snapshots = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], ResearcherSnapshot)]
    assert len(snapshots) == 1
    assert snapshots[0].official_h_index == 20
    assert snapshots[0].official_citation_count == 1000
    assert snapshots[0].integrity_score == previous_score
    assert events[-1]["status"] == ("failed" if failure in {"resolve", "publications"} else "completed")
    if failure == "resolve":
        assert profile.official_h_index is None
        assert profile.official_citation_count is None
    else:
        assert profile.official_h_index == 0  # A fresh provider zero is retained.
    if failure in {"resolve", "publications"}:
        assert profile.total_publications is None
    assert any("DELETE FROM publication_analyses" in str(call.args[0]) for call in db.execute.call_args_list)
    for call in db.add.call_args_list:
        if isinstance(call.args[0], PublicationAnalysis):
            assert call.args[0].suspicious_citations == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["collector_failed", "collector_crash", "analysis_failed", "analysis_crash", "completed"])
async def test_worker_captures_revision_before_collection_and_reports_real_terminal_status(monkeypatch, outcome):
    from app import database
    from app.tasks.researcher_tasks import _run_pipeline
    from app.services.scrapers import scrape_orchestrator

    profile = _profile()
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: profile)),
                         add=Mock(), commit=AsyncMock(), rollback=AsyncMock())

    @asynccontextmanager
    async def session():
        yield db

    class Collector:
        def __init__(self, db):
            pass

        async def run_scraping(self, profile_id):
            profile.official_h_index = 99
            profile.official_citation_count = 9999
            if outcome == "collector_crash":
                raise RuntimeError("collector unavailable")
            yield {"status": "failed" if outcome == "collector_failed" else "completed"}

    monkeypatch.setattr(database, "async_session", session)
    monkeypatch.setattr(scrape_orchestrator, "ScrapeOrchestrator", Collector)
    monkeypatch.setattr(aio, "resolve_researcher", AsyncMock(return_value=None if outcome == "analysis_failed" else {
        "s2_id": "target", "name": "Researcher", "h_index": 3, "citation_count": 30,
    }))
    monkeypatch.setattr(aio, "fetch_publications", AsyncMock(return_value=[_pub()]))
    monkeypatch.setattr(aio, "build_citation_graph", AsyncMock(return_value={
        "nodes": [], "edges": [], "total_citations_checked": 5, "self_citations": 0,
        "citation_evidence_status": "succeeded", "per_paper_citations": {},
    }))
    monkeypatch.setattr(aio, "analyze_topic_relevance", AsyncMock(return_value=[_pub()]))
    if outcome == "analysis_crash":
        async def crash(self, profile_id):
            raise RuntimeError("analysis unavailable")
            yield  # Make this an async generator, as the caller expects.
        monkeypatch.setattr(aio.AcademicIntegrityOrchestrator, "run_pipeline_streaming", crash)

    result = await _run_pipeline(profile.id)
    assert result["status"] == ("completed" if outcome == "completed" else "failed")
    snapshots = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], ResearcherSnapshot)]
    assert len(snapshots) == 1
    assert snapshots[0].official_h_index == 20  # Before collector overwrote it with 99.
    assert snapshots[0].official_citation_count == 1000
    if outcome != "completed":
        assert profile.analysis_status == "failed"
        assert profile.integrity_score is None
        assert profile.adjusted_h_index is None
    else:
        assert profile.integrity_score == 100
        assert profile.official_h_index == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("module, resource_name", [("researcher", "profile"), ("source_check", "check")])
async def test_stream_observes_committed_events_without_running_pipeline(monkeypatch, module, resource_name):
    from importlib import import_module
    from app.services import analysis_runs
    router = import_module("app.routers." + module)
    resource = SimpleNamespace(id="resource", user_id="owner", current_run_id="run")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: resource)),
                         commit=AsyncMock(), rollback=AsyncMock())
    observed = []
    async def observe(run_id, request, *, after):
        observed.append((run_id, after))
        yield {"event": "complete", "data": "committed-result"}
    monkeypatch.setattr(analysis_runs, "observe_run", observe)
    monkeypatch.setattr(router, "decode_stream_ticket", lambda *_: "owner")
    request = SimpleNamespace(headers={"last-event-id": "27"})
    endpoint = router.stream_researcher_analysis if module == "researcher" else router.stream_source_check
    for _ in range(2):
        response = await endpoint(resource.id, request, "local-ticket", db)
        assert [ev async for ev in response.body_iterator] == [{"event": "complete", "data": "committed-result"}]
    assert observed == [("run", 27), ("run", 27)]
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_legacy_resource_requires_explicit_rerun(monkeypatch):
    from app.routers import researcher as router
    from fastapi import HTTPException
    profile = SimpleNamespace(id="profile", user_id="owner", current_run_id=None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: profile)))
    monkeypatch.setattr(router, "decode_stream_ticket", lambda *_: "owner")
    with pytest.raises(HTTPException) as error:
        await router.stream_researcher_analysis(profile.id, SimpleNamespace(headers={}), "local-ticket", db)
    assert error.value.status_code == 409
