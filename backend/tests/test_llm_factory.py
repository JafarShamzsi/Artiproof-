"""Tests for the Phase 9 LLM abstraction.

Covers:
  - estimate_cost_usd with per-provider pricing
  - get_llm provider routing (default, explicit, unknown raises)
  - Provider `is_configured()` against env state
  - Fallback chain wiring (degraded primary -> fallback)
  - call_llm returns "" when the provider has no API key
"""

from __future__ import annotations

import pytest

from app.services.llm import (
    PROVIDER_PRICING,
    call_llm,
    estimate_cost_usd,
    get_llm,
)
from app.services.llm.base import LLMProviderError, LLMResponse
from app.services.llm.factory import (
    _failure_counts,
    _is_degraded,
    _record_failure,
    _record_success,
    get_fallback_provider,
)


# ─── Pricing ─────────────────────────────────────────────────────────────


def test_pricing_covers_all_three_providers():
    """Every provider we ship must have at least one priced model so the
    cost dashboard doesn't fall back for default operator workloads."""
    assert set(PROVIDER_PRICING.keys()) == {"gemini", "openai", "anthropic"}
    for provider, table in PROVIDER_PRICING.items():
        assert table, f"Provider {provider} has no models priced"


def test_cost_zero_when_no_tokens():
    assert (
        estimate_cost_usd(
            input_tokens=0, output_tokens=0, model="gemini-2.0-flash"
        )
        == 0.0
    )


def test_cost_uses_gemini_pricing_for_gemini_model():
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model="gemini-2.0-flash",
        provider="gemini",
    )
    # gemini-2.0-flash: $0.10/1M in, $0.40/1M out → 0.50 for 1M each.
    assert cost == 0.5


def test_cost_uses_openai_pricing_for_openai_model():
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model="gpt-4o-mini",
        provider="openai",
    )
    # gpt-4o-mini: $0.15/1M in, $0.60/1M out → 0.75 for 1M each.
    assert cost == 0.75


def test_cost_uses_anthropic_pricing_for_anthropic_model():
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model="claude-3-5-haiku-20241022",
        provider="anthropic",
    )
    # claude-3-5-haiku: $0.80/1M in, $4.00/1M out → 4.80 for 1M each.
    assert cost == 4.8


def test_cost_falls_back_for_unknown_model():
    """An unpriced (provider, model) pair uses the conservative midpoint
    fallback so finance dashboards show a non-zero number."""
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=0,
        model="future-mystery-model",
        provider="gemini",
    )
    # Fallback is 0.50 / 2.00 — 1M input → 0.50.
    assert cost == 0.5


# ─── Factory ─────────────────────────────────────────────────────────────


def test_get_llm_default_routes_to_gemini():
    provider = get_llm()
    assert provider.name == "gemini"


def test_get_llm_explicit_provider_works():
    assert get_llm("openai").name == "openai"
    assert get_llm("anthropic").name == "anthropic"
    assert get_llm("gemini").name == "gemini"


def test_get_llm_unknown_provider_raises():
    with pytest.raises(LLMProviderError):
        get_llm("vapor")


def test_get_llm_is_case_insensitive():
    assert get_llm("OpenAI").name == "openai"
    assert get_llm("ANTHROPIC").name == "anthropic"


# ─── Provider is_configured() ──────────────────────────────────────────────


def test_gemini_configured_only_with_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "")
    assert get_llm("gemini").is_configured() is False
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "test-key")
    assert get_llm("gemini").is_configured() is True


def test_openai_configured_only_with_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
    assert get_llm("openai").is_configured() is False
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "test-key")
    assert get_llm("openai").is_configured() is True


def test_anthropic_configured_only_with_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.ANTHROPIC_API_KEY", "")
    assert get_llm("anthropic").is_configured() is False
    monkeypatch.setattr("app.config.settings.ANTHROPIC_API_KEY", "test-key")
    assert get_llm("anthropic").is_configured() is True


# ─── Fallback chain ────────────────────────────────────────────────────────


def test_fallback_returns_none_when_unset(monkeypatch):
    monkeypatch.setattr("app.config.settings.LLM_FALLBACK_PROVIDER", "")
    assert get_fallback_provider() is None


def test_fallback_returns_none_when_provider_unconfigured(monkeypatch):
    """Configured fallback but no API key → fallback unavailable. The
    factory shouldn't try to chain a broken fallback onto a broken primary."""
    monkeypatch.setattr("app.config.settings.LLM_FALLBACK_PROVIDER", "openai")
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
    assert get_fallback_provider() is None


def test_fallback_returns_provider_when_configured(monkeypatch):
    monkeypatch.setattr("app.config.settings.LLM_FALLBACK_PROVIDER", "openai")
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "sk-test")
    fb = get_fallback_provider()
    assert fb is not None and fb.name == "openai"


def test_failure_tracker_marks_provider_degraded_after_threshold():
    # Clean state for this test
    _record_success("gemini")
    assert _is_degraded("gemini") is False
    _record_failure("gemini")
    _record_failure("gemini")
    assert _is_degraded("gemini") is False  # 2 failures, threshold is 3
    _record_failure("gemini")
    assert _is_degraded("gemini") is True  # 3rd failure
    _record_success("gemini")  # Reset
    assert _is_degraded("gemini") is False


# ─── call_llm contract ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_llm_returns_empty_string_when_provider_unconfigured(
    monkeypatch,
):
    """When the chosen provider has no API key, call_llm returns ""
    (legacy call_gemini contract). The engine treats this as "no AI
    configured" and surfaces a structured warning."""
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "")
    text = await call_llm(
        "test prompt",
        operation="claim_extractor",
        temperature=0.1,
        max_output_tokens=100,
    )
    assert text == ""


@pytest.mark.asyncio
async def test_call_llm_uses_explicit_provider_override(monkeypatch):
    """Passing provider= overrides settings.LLM_PROVIDER."""
    monkeypatch.setattr("app.config.settings.LLM_PROVIDER", "gemini")
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", "")
    text = await call_llm(
        "test", operation="claim_extractor", provider="openai"
    )
    # openai unconfigured → ""
    assert text == ""


# ─── LLMResponse dataclass ────────────────────────────────────────────────


def test_llm_response_defaults():
    """Token counts default to None — handles SDKs that omit usage on
    error / streaming paths."""
    response = LLMResponse(text="hi", model="x", provider="gemini")
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.total_tokens is None
