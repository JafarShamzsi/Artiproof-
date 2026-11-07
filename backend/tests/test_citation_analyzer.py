"""Tests for citation analysis helpers.

Pure helpers (``_score_domain``, ``_extract_doi``) are tested directly.
Network paths (``check_url_accessible``, ``check_retraction_crossref``) are
tested via ``respx`` to mock httpx without spinning up a real server.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.source_verification import citation_analyzer as ca


class TestScoreDomain:
    def test_high_credibility_domain(self):
        assert ca._score_domain("https://www.nature.com/articles/foo") >= 80

    def test_low_credibility_domain(self):
        assert ca._score_domain("https://infowars.com/article") < 30

    def test_gov_domain_high(self):
        assert ca._score_domain("https://nasa.gov/missions") >= 80

    def test_edu_domain_high(self):
        assert ca._score_domain("https://stanford.edu/research") >= 80

    def test_unknown_domain_neutral(self):
        score = ca._score_domain("https://random-blog.example/post")
        assert 40 <= score <= 60

    def test_www_prefix_stripped(self):
        with_www = ca._score_domain("https://www.nature.com/foo")
        without_www = ca._score_domain("https://nature.com/foo")
        assert with_www == without_www

    def test_invalid_url_returns_neutral(self):
        # Falls back to 50 on parse failure
        assert ca._score_domain("not-a-url") == 50.0


class TestExtractDoi:
    def test_extracts_from_doi_org(self):
        assert ca._extract_doi("https://doi.org/10.1038/nature12345") == "10.1038/nature12345"

    def test_strips_query_string(self):
        assert ca._extract_doi("https://doi.org/10.1234/x?foo=bar") == "10.1234/x"

    def test_returns_none_for_non_doi(self):
        assert ca._extract_doi("https://example.com/article") is None

    def test_returns_none_for_empty(self):
        assert ca._extract_doi("") is None


class TestCheckUrlAccessible:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_true_for_2xx(self):
        respx.head("https://example.com/x").respond(200)
        assert await ca.check_url_accessible("https://example.com/x") is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_for_404(self):
        respx.head("https://example.com/missing").respond(404)
        assert await ca.check_url_accessible("https://example.com/missing") is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_on_timeout(self):
        respx.head("https://example.com/slow").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        # check_url_accessible swallows transient errors and returns False
        assert await ca.check_url_accessible("https://example.com/slow") is False


class TestCrossrefRetraction:
    @pytest.mark.asyncio
    @respx.mock
    async def test_detects_update_to_retraction(self):
        respx.get("https://api.crossref.org/works/10.1/x").respond(
            200,
            json={
                "message": {
                    "update-to": [{"type": "retraction"}],
                    "title": ["A study of stuff"],
                }
            },
        )
        assert await ca.check_retraction_crossref("10.1/x") is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_detects_retracted_in_title(self):
        respx.get("https://api.crossref.org/works/10.1/y").respond(
            200,
            json={"message": {"title": ["RETRACTED: A study"], "update-to": []}},
        )
        assert await ca.check_retraction_crossref("10.1/y") is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_is_not_retraction(self):
        respx.get("https://api.crossref.org/works/10.1/unknown").respond(404)
        assert await ca.check_retraction_crossref("10.1/unknown") is False

    @pytest.mark.asyncio
    async def test_empty_doi_short_circuits(self):
        assert await ca.check_retraction_crossref("") is False
        assert await ca.check_retraction_crossref(None) is False  # type: ignore[arg-type]

    @pytest.mark.asyncio
    @respx.mock
    async def test_normalizes_doi_url(self):
        """Should strip ``https://doi.org/`` prefix before requesting."""
        route = respx.get("https://api.crossref.org/works/10.1/foo").respond(
            200, json={"message": {"title": ["x"], "update-to": []}}
        )
        await ca.check_retraction_crossref("https://doi.org/10.1/foo")
        assert route.called


class TestAnalyzeAllCitationsParallel:
    @pytest.mark.asyncio
    @respx.mock
    async def test_processes_in_parallel_collects_results(self):
        # Two different citations; both should resolve
        respx.head("https://nature.com/a").respond(200)
        respx.head("https://nature.com/b").respond(200)
        results = await ca.analyze_all_citations(
            [
                {"text": "ref1", "url": "https://nature.com/a"},
                {"text": "ref2", "url": "https://nature.com/b"},
            ]
        )
        assert len(results) == 2
        assert all(r["is_accessible"] for r in results)

    @pytest.mark.asyncio
    async def test_caps_at_20_with_warning(self):
        warnings: list[dict] = []
        # Use 25 dud citations — no URL means no network calls happen
        cits = [{"text": f"r{i}", "url": ""} for i in range(25)]
        results = await ca.analyze_all_citations(cits, warnings=warnings)
        assert len(results) == 20
        assert any(w["type"] == "citations_capped" for w in warnings)
