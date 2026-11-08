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


class TestOpenAlexRetraction:
    @pytest.mark.asyncio
    @respx.mock
    async def test_detects_is_retracted_true(self):
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/oax"
        ).respond(200, json={"id": "W1", "is_retracted": True})
        assert await ca.check_retraction_openalex("10.1/oax") is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_normal_paper_not_flagged(self):
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/ok"
        ).respond(200, json={"id": "W2", "is_retracted": False})
        assert await ca.check_retraction_openalex("10.1/ok") is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_returns_false_not_retraction(self):
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/missing"
        ).respond(404)
        assert await ca.check_retraction_openalex("10.1/missing") is False

    @pytest.mark.asyncio
    async def test_empty_doi_short_circuits(self):
        assert await ca.check_retraction_openalex("") is False


class TestCheckRetractionCombined:
    """``check_retraction`` queries both sources in parallel and attributes
    the finding to whichever flagged it."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_both_sources_clean_means_not_retracted(self):
        respx.get("https://api.crossref.org/works/10.1/x").respond(
            200, json={"message": {"title": ["ok"], "update-to": []}}
        )
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/x"
        ).respond(200, json={"is_retracted": False})
        retracted, sources = await ca.check_retraction("10.1/x")
        assert retracted is False
        assert sources == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_openalex_alone_can_trigger_retraction(self):
        """OpenAlex catches DOIs CrossRef's ``update-to`` graph hasn't
        propagated yet — that's the whole point of adding it."""
        respx.get("https://api.crossref.org/works/10.1/oax-only").respond(
            200, json={"message": {"title": ["ok"], "update-to": []}}
        )
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/oax-only"
        ).respond(200, json={"is_retracted": True})
        retracted, sources = await ca.check_retraction("10.1/oax-only")
        assert retracted is True
        assert sources == ["OpenAlex"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_both_sources_flag_lists_both(self):
        respx.get("https://api.crossref.org/works/10.1/both").respond(
            200, json={"message": {"title": ["RETRACTED: x"], "update-to": []}}
        )
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/both"
        ).respond(200, json={"is_retracted": True})
        retracted, sources = await ca.check_retraction("10.1/both")
        assert retracted is True
        assert set(sources) == {"CrossRef", "OpenAlex"}

    @pytest.mark.asyncio
    async def test_empty_doi_returns_clean_quickly(self):
        retracted, sources = await ca.check_retraction("")
        assert retracted is False
        assert sources == []


class TestAnalyzeCitationAttributesRetractionSource:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retracted_issue_string_names_the_database(self):
        # URL is accessible and has a DOI we can extract.
        respx.head("https://doi.org/10.1/r").respond(200)
        # CrossRef says clean, OpenAlex says retracted.
        respx.get("https://api.crossref.org/works/10.1/r").respond(
            200, json={"message": {"title": ["ok"], "update-to": []}}
        )
        respx.get(
            "https://api.openalex.org/works/https://doi.org/10.1/r"
        ).respond(200, json={"is_retracted": True})

        result = await ca.analyze_citation(
            {"text": "Smith 2020", "url": "https://doi.org/10.1/r"}
        )
        assert result["is_retracted"] is True
        assert result["retraction_sources"] == ["OpenAlex"]
        assert any("OpenAlex" in issue for issue in (result["issues"] or []))


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
