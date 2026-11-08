"""AI content detection — deterministic statistical primary, with opt-in
perplexity/LLM blends (both off by default)."""

from __future__ import annotations

import pytest

from app.services.source_verification import ai_detector as ad
from app.services.source_verification.ai_detector import (
    _paragraph_ai_score,
    _statistical_detection,
    detect_ai_content,
)
from app.services.source_verification.perplexity import perplexity_ai_signal

HUMAN = (
    "I grabbed coffee and rushed out — the bus was already pulling away! "
    "My neighbor waved. Honestly? I almost tripped on the curb, twice."
)
AI_LIKE = (
    "The system provides significant benefits to users. The system delivers "
    "significant value to organizations. Furthermore the system enables "
    "significant improvements. Moreover the system supports significant growth. "
    "Additionally the system ensures significant reliability across operations."
)


class TestSplitParagraphs:
    def test_double_newline_splits(self):
        text = (
            "First paragraph long enough to survive the length filter here.\n\n"
            "Second paragraph also long enough to be analyzed and kept."
        )
        out = ad._split_paragraphs(text)
        assert len(out) == 2
        assert out[0].startswith("First") and out[1].startswith("Second")

    def test_short_paragraphs_dropped(self):
        text = "OK\n\n" + ("A long enough paragraph for analysis " * 3).strip()
        out = ad._split_paragraphs(text)
        assert len(out) == 1

    def test_empty_text_returns_empty(self):
        assert ad._split_paragraphs("") == []
        assert ad._split_paragraphs("   ") == []


class TestStatisticalDetection:
    def test_one_result_per_paragraph_labelled_statistical(self):
        out = _statistical_detection([HUMAN, AI_LIKE])
        assert {r["paragraph_index"] for r in out} == {0, 1}
        assert all(r["detection_method"] == "statistical" for r in out)

    def test_probability_bounded(self):
        for r in _statistical_detection([HUMAN, AI_LIKE]):
            assert 0.0 <= r["ai_probability"] <= 1.0

    def test_ai_like_scores_higher_than_human(self):
        assert _paragraph_ai_score(AI_LIKE, True) > _paragraph_ai_score(HUMAN, True)

    def test_english_signals_are_gated(self):
        # The English-only cues only raise the score when english_signals=True.
        assert _paragraph_ai_score(AI_LIKE, True) >= _paragraph_ai_score(AI_LIKE, False)


class TestDetectAIContent:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_list(self):
        assert await detect_ai_content("") == []

    @pytest.mark.asyncio
    async def test_default_is_statistical(self, monkeypatch):
        monkeypatch.setattr(ad.settings, "GEMINI_API_KEY", "")
        warnings: list[dict] = []
        out = await detect_ai_content(HUMAN + "\n\n" + AI_LIKE, warnings=warnings)
        assert len(out) == 2
        assert all(r["detection_method"] == "statistical" for r in out)

    @pytest.mark.asyncio
    async def test_no_llm_call_by_default_even_with_key(self, monkeypatch):
        monkeypatch.setattr(ad.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(ad.settings, "AI_DETECT_LLM_CROSSCHECK", False)

        async def boom(*a, **k):
            raise AssertionError("LLM must not be called by default")

        monkeypatch.setattr(ad, "call_gemini", boom)
        out = await detect_ai_content(HUMAN + "\n\n" + AI_LIKE)
        assert all(r["detection_method"] == "statistical" for r in out)

    @pytest.mark.asyncio
    async def test_full_document_covered_no_cap_for_normal_size(self, monkeypatch):
        monkeypatch.setattr(ad.settings, "GEMINI_API_KEY", "")
        n = 25  # under the pathological cap -> every paragraph analyzed
        body = "\n\n".join(f"Paragraph {i} long enough to keep " * 3 for i in range(n))
        warnings: list[dict] = []
        out = await detect_ai_content(body, warnings=warnings)
        assert len(out) == n
        assert not any(w.get("type") == "paragraphs_capped" for w in warnings)

    @pytest.mark.asyncio
    async def test_paragraph_cap_only_at_pathological_size(self, monkeypatch):
        from app.constants import ANALYSIS_MAX_PARAGRAPHS

        monkeypatch.setattr(ad.settings, "GEMINI_API_KEY", "")
        n = ANALYSIS_MAX_PARAGRAPHS + 5
        body = "\n\n".join(f"Paragraph {i} long enough to keep " * 2 for i in range(n))
        warnings: list[dict] = []
        out = await detect_ai_content(body, warnings=warnings)
        assert len(out) == ANALYSIS_MAX_PARAGRAPHS
        cap = next((w for w in warnings if w.get("type") == "paragraphs_capped"), None)
        assert cap is not None and cap["analyzed"] == ANALYSIS_MAX_PARAGRAPHS and cap["total"] == n

    def test_perplexity_off_by_default(self, monkeypatch):
        monkeypatch.setattr(ad.settings, "AI_DETECT_PERPLEXITY", False)
        assert perplexity_ai_signal("a long enough paragraph of text") is None

    @pytest.mark.asyncio
    async def test_llm_crosscheck_blends_when_enabled(self, monkeypatch):
        monkeypatch.setattr(ad.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(ad.settings, "AI_DETECT_LLM_CROSSCHECK", True)
        monkeypatch.setattr(ad.settings, "AI_DETECT_PERPLEXITY", False)

        async def fake_gemini(prompt, operation=None, **k):
            return '[{"index":0,"ai_probability":1.0},{"index":1,"ai_probability":1.0}]'

        monkeypatch.setattr(ad, "call_gemini", fake_gemini)
        out = await detect_ai_content(HUMAN + "\n\n" + AI_LIKE)
        assert all("+llm" in r["detection_method"] for r in out)
        # Blended = mean(statistical, LLM=1.0) >= statistical alone.
        for blended, base in zip(out, _statistical_detection([HUMAN, AI_LIKE])):
            assert blended["ai_probability"] >= base["ai_probability"]
