"""Tests for AI content detection.

The Gemini path requires a real API; we test:
- ``_split_paragraphs``: deterministic, no I/O
- ``_heuristic_detection``: deterministic, the fallback used when Gemini fails
- ``detect_ai_content`` against an empty API key (falls into the heuristic
  path — no network, no mocking needed)
"""

from __future__ import annotations

import pytest

from app.services.source_verification import ai_detector


class TestSplitParagraphs:
    def test_double_newline_splits(self):
        # Each paragraph must be >= 30 chars to survive the filter
        text = (
            "First paragraph long enough to survive the length filter here.\n\n"
            "Second paragraph also long enough to be analyzed and kept."
        )
        out = ai_detector._split_paragraphs(text)
        assert len(out) == 2
        assert out[0].startswith("First")
        assert out[1].startswith("Second")

    def test_short_paragraphs_dropped(self):
        text = "OK\n\n" + ("A long enough paragraph for analysis " * 3).strip()
        out = ai_detector._split_paragraphs(text)
        assert len(out) == 1
        assert out[0].startswith("A long enough paragraph")

    def test_empty_text_returns_empty(self):
        assert ai_detector._split_paragraphs("") == []
        assert ai_detector._split_paragraphs("   ") == []


class TestHeuristicDetection:
    def test_returns_one_result_per_paragraph(self):
        paragraphs = [
            "First paragraph with several sentences. " * 10,
            "Second paragraph with different content. " * 10,
        ]
        out = ai_detector._heuristic_detection(paragraphs)
        assert len(out) == 2
        assert {r["paragraph_index"] for r in out} == {0, 1}

    def test_probability_bounded(self):
        paragraphs = ["Short normal text.\nWith multiple lines. " * 20]
        out = ai_detector._heuristic_detection(paragraphs)
        for r in out:
            assert 0.0 <= r["ai_probability"] <= 1.0

    def test_uniform_long_sentences_score_higher(self):
        """Robotic/uniform text should score above 0.5; conversational below."""
        robotic = (
            "However, the system performs admirably under all tested conditions. "
            "Furthermore, the results are consistent across multiple trials. "
            "Moreover, the methodology is sound and well-documented. "
            "Consequently, we can draw definitive conclusions from the data. "
        )
        casual = (
            "I don't know, it's kinda weird. "
            "We're seeing the numbers come back, but they're all over the place. "
            "Honestly? I'm not sure what's going on. "
        )
        robotic_out = ai_detector._heuristic_detection([robotic])[0]
        casual_out = ai_detector._heuristic_detection([casual])[0]
        # Heuristic isn't perfect but the relative order should hold
        assert robotic_out["ai_probability"] > casual_out["ai_probability"]

    def test_method_label_is_heuristic(self):
        out = ai_detector._heuristic_detection(["A long enough paragraph " * 20])
        assert out[0]["detection_method"] == "heuristic-fallback"


class TestDetectAIContent:
    @pytest.mark.asyncio
    @pytest.mark.parametrize('payload', ['[]', '[null]', '[{"index": -1, "ai_probability": 1}]',
                                         '[{"index": 0, "ai_probability": "NaN"}]'])
    async def test_missing_or_invalid_model_rows_are_not_invented_assessments(self, monkeypatch, payload):
        from unittest.mock import AsyncMock
        monkeypatch.setattr(ai_detector.settings, 'GEMINI_API_KEY', 'synthetic-only')
        monkeypatch.setattr(ai_detector, '_call_gemini', AsyncMock(return_value=payload))
        warnings = []
        result = await ai_detector.detect_ai_content('Synthetic paragraph long enough to pass the filter. ' * 5,
                                                     warnings=warnings)
        assert len(result) == 1
        assert result[0]['detection_method'] == 'heuristic-fallback'
        assert any(w['type'] == 'fallback_heuristic' for w in warnings)

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_list(self):
        out = await ai_detector.detect_ai_content("")
        assert out == []

    @pytest.mark.asyncio
    async def test_no_api_key_falls_back_to_heuristic(self, monkeypatch):
        """No GEMINI_API_KEY → heuristic path, no network call."""
        # Override the loaded settings object's key (env var alone isn't enough
        # because pydantic-settings already snapshotted it on import)
        monkeypatch.setattr(ai_detector.settings, "GEMINI_API_KEY", "")

        text = (
            "First paragraph that is long enough to survive the filter. " * 5
            + "\n\n"
            + "Second paragraph also sufficiently long to be analyzed. " * 5
        )
        warnings: list[dict] = []
        out = await ai_detector.detect_ai_content(text, warnings=warnings)

        assert len(out) == 2
        assert all(r["detection_method"] == "heuristic-fallback" for r in out)
        # Warning should record the fallback
        assert any(w.get("type") == "fallback_heuristic" for w in warnings)

    @pytest.mark.asyncio
    async def test_paragraph_cap_warning_gemini_path(self, monkeypatch):
        """When >20 paragraphs are submitted, the 20-paragraph cap kicks in
        and records a warning. Both Gemini and heuristic paths respect it.
        """
        from unittest.mock import patch
        import json as _json

        monkeypatch.setattr(ai_detector.settings, "GEMINI_API_KEY", "fake-key")
        body = "\n\n".join(f"Paragraph {i} long enough to keep " * 5 for i in range(25))
        warnings: list[dict] = []

        # Mock Gemini to return a valid empty result so we can assert on the
        # cap-warning side effect rather than on Gemini's actual scoring.
        fake_response = _json.dumps([])
        with patch.object(ai_detector, "_call_gemini", return_value=fake_response):
            out = await ai_detector.detect_ai_content(body, warnings=warnings)

        # Output is filled in for all 20 paragraphs Gemini was offered
        assert len(out) == 20
        cap_warning = next(
            (w for w in warnings if w.get("type") == "paragraphs_capped"), None
        )
        assert cap_warning is not None
        assert cap_warning["analyzed"] == 20
        assert cap_warning["total"] >= 25

    @pytest.mark.asyncio
    async def test_heuristic_path_also_caps(self, monkeypatch):
        """The 20-paragraph cap applies on both paths: protects against
        pathologically large submissions even when Gemini is unavailable.
        """
        monkeypatch.setattr(ai_detector.settings, "GEMINI_API_KEY", "")
        body = "\n\n".join(f"Paragraph {i} long enough to keep " * 5 for i in range(25))
        warnings: list[dict] = []
        out = await ai_detector.detect_ai_content(body, warnings=warnings)
        assert len(out) == 20
        cap_warning = next(
            (w for w in warnings if w.get("type") == "paragraphs_capped"), None
        )
        assert cap_warning is not None
        assert cap_warning["analyzed"] == 20
        assert cap_warning["total"] >= 25
        # Fallback warning still recorded alongside the cap warning
        assert any(w.get("type") == "fallback_heuristic" for w in warnings)
