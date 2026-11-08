"""Regression coverage for publisher ratings without a model provider."""

from unittest.mock import AsyncMock
import json

import pytest

from app.services.source_verification import fact_checker as fc


@pytest.mark.parametrize("rating, expected", [
    ("incorrect", "false"), ("not true", "false"),
    ("inaccurate", "false"), (" TRUE ", "true"),
    ("mostly true", "partially_true"), ("Mostly   False", "misleading"),
    ("not entirely incorrect", "unverified"),
    ("not proven true", "unverified"), ("", "unverified"),
])
def test_rating_labels_do_not_match_substrings(rating, expected):
    assert fc.normalize_factcheck_rating(rating) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("ratings, expected", [
    (["incorrect"], "false"), (["not true"], "false"),
    (["true", "false"], "unverified"),
    (["false", "true"], "unverified"),
    (["true", "unsupported scale"], "unverified"),
    (["true", "correct"], "true"),
])
async def test_fallback_considers_all_reviews(monkeypatch, ratings, expected):
    monkeypatch.setattr(fc.settings, "GEMINI_API_KEY", "")
    reviews = [
        {"rating": rating, "publisher": f"Publisher {i}", "url": f"https://example.com/{i}", "title": "Reviewed claim"}
        for i, rating in enumerate(ratings)
    ]
    monkeypatch.setattr(fc, "check_with_google_factcheck", AsyncMock(return_value=reviews))
    model = AsyncMock()
    monkeypatch.setattr(fc, "_call_gemini_verify", model)
    result = await fc.verify_claim("A submitted claim")
    assert result["verdict"] == expected
    assert len(result["sources"]) == len(reviews)
    if expected == "unverified":
        assert result["confidence"] == 0
    model.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    [], None, "true", {"confidence": None}, {"confidence": "high"},
    {"confidence": float("nan")}, {"confidence": float("inf")},
])
async def test_malformed_model_output_abstains(monkeypatch, payload):
    monkeypatch.setattr(fc.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fc, "check_with_google_factcheck", AsyncMock(return_value=[]))
    monkeypatch.setattr(fc, "_call_gemini_verify", AsyncMock(return_value=json.dumps(payload)))
    result = await fc.verify_claim("A submitted claim")
    assert result["verdict"] == "unverified"
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_non_string_model_verdict_abstains(monkeypatch):
    monkeypatch.setattr(fc.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(fc, "check_with_google_factcheck", AsyncMock(return_value=[]))
    monkeypatch.setattr(fc, "_call_gemini_verify", AsyncMock(
        return_value=json.dumps({"verdict": ["true"], "confidence": 1}),
    ))
    result = await fc.verify_claim("A submitted claim")
    assert result["verdict"] == "unverified"
    assert result["confidence"] == 0
