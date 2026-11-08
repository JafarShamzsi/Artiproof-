"""Retrieval-augmented verification: verdicts grounded in fetched evidence.

Offline — Google Fact Check, Wikipedia retrieval, and Gemini are all
monkeypatched, so these assert the *wiring* (evidence reaches the prompt and
the result) without any network or keys.
"""

import pytest

from app.services.source_verification import fact_checker as fc
from app.services.source_verification.evidence_retrieval import Evidence

pytestmark = pytest.mark.asyncio


async def test_verify_claim_grounds_verdict_in_evidence(monkeypatch):
    captured = {}

    async def no_factcheck(claim_text, language_code="en"):
        return []

    async def fake_evidence(claim_text, language_code="en"):
        return [
            Evidence(
                title="Eiffel Tower",
                url="https://en.wikipedia.org/wiki/Eiffel_Tower",
                snippet="The tower was completed in 1889.",
                source="wikipedia",
            )
        ]

    async def fake_gemini(prompt, operation=None, **kw):
        captured["prompt"] = prompt
        return (
            '{"verdict": "true", "confidence": 0.9, '
            '"explanation": "Matches the retrieved source.", '
            '"true_version": null, "sources": ["Wikipedia"]}'
        )

    monkeypatch.setattr(fc, "check_with_google_factcheck", no_factcheck)
    monkeypatch.setattr(fc, "retrieve_evidence", fake_evidence)
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fc, "call_gemini", fake_gemini)

    result = await fc.verify_claim("The Eiffel Tower was completed in 1889.", "article ctx")

    # Evidence reached the prompt, with the grounding instruction.
    assert "Eiffel Tower" in captured["prompt"]
    assert "ground your verdict" in captured["prompt"]
    assert "The tower was completed in 1889." in captured["prompt"]
    # Evidence folded into sources and returned in `evidence`.
    assert any(
        s.get("url") == "https://en.wikipedia.org/wiki/Eiffel_Tower"
        for s in result["sources"]
    )
    assert result["evidence"][0]["title"] == "Eiffel Tower"
    assert result["verdict"] == "true"


async def test_verify_claim_surfaces_evidence_without_gemini_key(monkeypatch):
    async def no_factcheck(claim_text, language_code="en"):
        return []

    async def fake_evidence(claim_text, language_code="en"):
        return [
            Evidence(
                title="Topic",
                url="https://en.wikipedia.org/wiki/Topic",
                snippet="Reference text.",
                source="wikipedia",
            )
        ]

    monkeypatch.setattr(fc, "check_with_google_factcheck", no_factcheck)
    monkeypatch.setattr(fc, "retrieve_evidence", fake_evidence)
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "")

    result = await fc.verify_claim("some claim", "")
    # No LLM to reason, but the retrieved evidence is still surfaced.
    assert result["verdict"] == "unverified"
    assert result["evidence"][0]["url"] == "https://en.wikipedia.org/wiki/Topic"
    assert any(
        s.get("url") == "https://en.wikipedia.org/wiki/Topic" for s in result["sources"]
    )


async def test_verify_claim_handles_no_evidence(monkeypatch):
    async def no_factcheck(claim_text, language_code="en"):
        return []

    async def no_evidence(claim_text, language_code="en"):
        return []

    monkeypatch.setattr(fc, "check_with_google_factcheck", no_factcheck)
    monkeypatch.setattr(fc, "retrieve_evidence", no_evidence)
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "")

    result = await fc.verify_claim("some claim", "")
    assert result["verdict"] == "unverified"
    assert result["evidence"] == []
    assert result["sources"] == []
