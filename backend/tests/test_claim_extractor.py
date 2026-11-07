"""Tests for claim extraction edge cases.

We mock the ``_call_gemini`` function so the test suite never actually hits
the Gemini API. Tests cover: empty input, missing API key, valid response,
malformed JSON, non-list response, claim cap, truncation warning.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.source_verification import claim_extractor as ce


@pytest.mark.asyncio
async def test_empty_text_short_circuits():
    out = await ce.extract_claims("")
    assert out == []


@pytest.mark.asyncio
async def test_short_text_short_circuits():
    out = await ce.extract_claims("too short")
    assert out == []


@pytest.mark.asyncio
async def test_no_api_key_returns_empty(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "")
    warnings: list[dict] = []
    out = await ce.extract_claims("a" * 200, warnings=warnings)
    assert out == []
    assert any(w["type"] == "missing_gemini_key" for w in warnings)


@pytest.mark.asyncio
async def test_valid_response_parsed(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")

    fake_response = json.dumps([
        {"claim_text": "Water boils at 100C", "category": "scientific",
         "position": {"start": 0, "end": 20}},
        {"claim_text": "The Earth is round", "category": "scientific"},
    ])
    with patch.object(ce, "_call_gemini", return_value=fake_response):
        out = await ce.extract_claims("a" * 200)

    assert len(out) == 2
    assert out[0]["claim_text"] == "Water boils at 100C"
    assert out[0]["category"] == "scientific"
    # Default position when missing
    assert out[1]["position"] == {"start": 0, "end": 0}


@pytest.mark.asyncio
async def test_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    fenced = '```json\n[{"claim_text": "x"}]\n```'
    with patch.object(ce, "_call_gemini", return_value=fenced):
        out = await ce.extract_claims("a" * 200)
    assert len(out) == 1
    assert out[0]["claim_text"] == "x"


@pytest.mark.asyncio
async def test_invalid_json_returns_empty(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    warnings: list[dict] = []
    with patch.object(ce, "_call_gemini", return_value="not valid json {{{"):
        out = await ce.extract_claims("a" * 200, warnings=warnings)
    assert out == []
    assert any(w["type"] == "invalid_json" for w in warnings)


@pytest.mark.asyncio
async def test_non_list_response_returns_empty(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    warnings: list[dict] = []
    with patch.object(ce, "_call_gemini", return_value=json.dumps({"not": "a list"})):
        out = await ce.extract_claims("a" * 200, warnings=warnings)
    assert out == []
    assert any(w["type"] == "invalid_shape" for w in warnings)


@pytest.mark.asyncio
async def test_call_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    warnings: list[dict] = []
    with patch.object(ce, "_call_gemini", side_effect=RuntimeError("503")):
        out = await ce.extract_claims("a" * 200, warnings=warnings)
    assert out == []
    assert any(w["type"] == "claim_extraction_failed" for w in warnings)


@pytest.mark.asyncio
async def test_text_truncation_warning(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    warnings: list[dict] = []
    long_text = "a" * (ce.MAX_TEXT_CHARS + 1000)
    with patch.object(ce, "_call_gemini", return_value="[]"):
        await ce.extract_claims(long_text, warnings=warnings)
    truncation = next((w for w in warnings if w["type"] == "text_truncated"), None)
    assert truncation is not None
    assert truncation["analyzed_length"] == ce.MAX_TEXT_CHARS
    assert truncation["original_length"] == len(long_text)


@pytest.mark.asyncio
async def test_claim_cap_enforced(monkeypatch):
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    fake_response = json.dumps([
        {"claim_text": f"claim {i}"} for i in range(50)
    ])
    warnings: list[dict] = []
    with patch.object(ce, "_call_gemini", return_value=fake_response):
        out = await ce.extract_claims("a" * 200, warnings=warnings)
    assert len(out) == ce.MAX_CLAIMS
    cap_warning = next((w for w in warnings if w["type"] == "claims_capped"), None)
    assert cap_warning is not None
    assert cap_warning["extracted"] == 50
    assert cap_warning["kept"] == ce.MAX_CLAIMS


@pytest.mark.asyncio
async def test_invalid_claim_objects_filtered(monkeypatch):
    """Items missing claim_text or non-dicts should be silently dropped."""
    monkeypatch.setattr(ce.settings, "GEMINI_API_KEY", "fake-key")
    fake_response = json.dumps([
        {"claim_text": "good"},
        "bare string",                    # not a dict — drop
        {"category": "scientific"},       # missing claim_text — drop
        {"claim_text": "also good"},
    ])
    with patch.object(ce, "_call_gemini", return_value=fake_response):
        out = await ce.extract_claims("a" * 200)
    assert len(out) == 2
    assert {c["claim_text"] for c in out} == {"good", "also good"}
