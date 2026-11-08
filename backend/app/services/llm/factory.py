"""LLM factory + ``call_llm`` chokepoint.

The factory owns:
  - The provider registry (name -> instance).
  - Default + fallback provider selection from settings.
  - Per-provider consecutive-failure tracking for fallback.
  - Pricing per (provider, model) for cost dashboards.
  - The single ``call_llm()`` entry point used by every engine.

Engines call ``call_llm(prompt, operation=..., ...)``. The factory:
  1. Picks the primary provider (from settings or per-call override).
  2. Runs ``provider.generate(...)``.
  3. On exception, increments the failure counter; if past the threshold,
     tries the fallback provider (also tracked).
  4. Writes one llm_metrics row regardless of which provider served the call.
  5. Returns the text (engines don't care which provider produced it).

Why a singleton registry: provider clients hold an HTTP connection
pool. Creating them per-call is wasteful. The registry pre-instantiates
each provider once at module load.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Optional

from app.config import settings
from app.context import (
    current_researcher_profile_id,
    current_source_check_id,
    current_user_id,
)
from app.database import async_session
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse

logger = logging.getLogger(__name__)


# ─── Registry ─────────────────────────────────────────────────────────────
_PROVIDERS: dict[str, LLMProvider] = {}


def register_provider(provider: LLMProvider) -> None:
    """Register a provider instance under its name.

    Idempotent: re-registering overwrites the previous entry. Called from
    each ``app/services/llm/providers/*.py`` module at import time.
    """
    _PROVIDERS[provider.name] = provider


def get_llm(name: Optional[str] = None) -> LLMProvider:
    """Look up a provider by name.

    Args:
        name: Explicit provider name. When None, reads
            ``settings.LLM_PROVIDER`` (which defaults to "gemini" for
            back-compat with code that pre-dates the abstraction).

    Returns:
        The registered ``LLMProvider`` instance.

    Raises:
        ``LLMProviderError`` if the requested provider isn't registered
        (i.e. the operator typo'd the env var).
    """
    selected = (name or settings.LLM_PROVIDER or "gemini").lower()
    if selected not in _PROVIDERS:
        registered = ", ".join(sorted(_PROVIDERS.keys())) or "(none)"
        raise LLMProviderError(
            f"Unknown LLM provider {selected!r}. Registered: {registered}. "
            "Set LLM_PROVIDER to one of the registered names."
        )
    return _PROVIDERS[selected]


def get_fallback_provider() -> Optional[LLMProvider]:
    """Return the configured fallback provider, or None.

    Returns None when no fallback is configured OR when the fallback
    provider isn't ``is_configured()`` (missing API key). The factory
    skips fallback in that case instead of raising another error on top
    of the primary failure.
    """
    name = (settings.LLM_FALLBACK_PROVIDER or "").lower()
    if not name:
        return None
    provider = _PROVIDERS.get(name)
    if provider is None or not provider.is_configured():
        return None
    return provider


# ─── Pricing ──────────────────────────────────────────────────────────────
# USD per 1M tokens. Models grouped by provider so finance reports can
# attribute correctly. Update when vendors revise pricing — the DB
# stores raw tokens so historical rows reprice automatically.
PROVIDER_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "gemini": {
        # Source: ai.google.dev/pricing
        "gemini-2.0-flash": {"input_per_1m": 0.10, "output_per_1m": 0.40},
        "gemini-2.0-flash-lite": {"input_per_1m": 0.075, "output_per_1m": 0.30},
        "gemini-1.5-flash": {"input_per_1m": 0.075, "output_per_1m": 0.30},
        "gemini-1.5-flash-8b": {"input_per_1m": 0.0375, "output_per_1m": 0.15},
        "gemini-2.0-pro": {"input_per_1m": 1.25, "output_per_1m": 5.00},
        "gemini-1.5-pro": {"input_per_1m": 1.25, "output_per_1m": 5.00},
    },
    "openai": {
        # Source: openai.com/api/pricing
        "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
        "gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.00},
        "gpt-4-turbo": {"input_per_1m": 10.00, "output_per_1m": 30.00},
        "gpt-3.5-turbo": {"input_per_1m": 0.50, "output_per_1m": 1.50},
    },
    "anthropic": {
        # Source: anthropic.com/api (Claude pricing). Naming convention
        # uses Anthropic's date-stamped model identifiers.
        "claude-3-5-haiku-20241022": {"input_per_1m": 0.80, "output_per_1m": 4.00},
        "claude-3-5-sonnet-20241022": {"input_per_1m": 3.00, "output_per_1m": 15.00},
        "claude-3-opus-20240229": {"input_per_1m": 15.00, "output_per_1m": 75.00},
        "claude-3-haiku-20240307": {"input_per_1m": 0.25, "output_per_1m": 1.25},
    },
}
# Conservative midpoint when we see an unpriced (provider, model) pair.
_FALLBACK_PRICE = {"input_per_1m": 0.50, "output_per_1m": 2.00}


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    model: str,
    provider: str = "gemini",
) -> float:
    """Convert raw token counts into a USD estimate.

    Args:
        input_tokens, output_tokens: From ``llm_metrics`` row.
        model: Model identifier the provider used (e.g. ``gpt-4o-mini``).
        provider: Provider identifier — keys into PROVIDER_PRICING.

    Returns:
        Rounded-to-6dp USD cost. ``0.0`` when both token counts are zero.
        For unknown (provider, model) pairs, uses the conservative
        midpoint fallback so the dashboard underestimates rather than
        overestimates — finance gets a "≥" number, not a "≤" one.
    """
    if not input_tokens and not output_tokens:
        return 0.0
    table = PROVIDER_PRICING.get(provider.lower(), {})
    price = table.get(model, _FALLBACK_PRICE)
    return round(
        (input_tokens / 1_000_000) * price["input_per_1m"]
        + (output_tokens / 1_000_000) * price["output_per_1m"],
        6,
    )


# ─── Fallback tracking ────────────────────────────────────────────────────
# When a provider fails 3 times in a row, the factory marks it "degraded"
# and routes new calls to the fallback until the failure counter resets
# (which happens on the next successful call OR after a 5-minute cooldown).
_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 5 * 60
_failure_counts: dict[str, int] = defaultdict(int)
_last_failure_at: dict[str, float] = {}


def _record_success(provider_name: str) -> None:
    if provider_name in _failure_counts:
        del _failure_counts[provider_name]
    if provider_name in _last_failure_at:
        del _last_failure_at[provider_name]


def _record_failure(provider_name: str) -> int:
    _failure_counts[provider_name] += 1
    _last_failure_at[provider_name] = time.monotonic()
    return _failure_counts[provider_name]


def _is_degraded(provider_name: str) -> bool:
    """A provider is degraded when its consecutive-failure count exceeds
    the threshold AND the last failure was within the cooldown window.
    After the cooldown the counter is reset and the provider is given
    another chance."""
    count = _failure_counts.get(provider_name, 0)
    if count < _FAILURE_THRESHOLD:
        return False
    last = _last_failure_at.get(provider_name, 0.0)
    if time.monotonic() - last > _COOLDOWN_SECONDS:
        # Cooldown elapsed — give the provider another try.
        _record_success(provider_name)
        return False
    return True


# ─── OTel helper (no-op when uninitialized) ──────────────────────────────
def _tracer():
    """Return an OTel tracer if available, else None. Metric persistence
    works without OTel; this is purely for distributed-tracing UIs."""
    try:
        from opentelemetry import trace  # type: ignore

        return trace.get_tracer("artiproof.llm")
    except Exception:
        return None


# ─── Metric persistence ──────────────────────────────────────────────────
async def _persist_metric(
    *,
    provider: str,
    operation: str,
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    total_tokens: Optional[int],
    latency_ms: int,
    error_class: Optional[str],
) -> None:
    """Best-effort write to llm_metrics. Never raises into the caller —
    a failed telemetry write must not abort the analysis pipeline."""
    try:
        from app.models.llm_metric import LLMMetric

        async with async_session() as db:
            row = LLMMetric(
                id=str(uuid.uuid4()),
                user_id=current_user_id.get(),
                provider=provider,
                operation=operation,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                error_class=error_class,
                source_check_id=current_source_check_id.get(),
                researcher_profile_id=current_researcher_profile_id.get(),
            )
            db.add(row)
            await db.commit()
    except Exception as e:
        logger.debug("LLM metric write failed: %s", type(e).__name__)


# ─── Public entry point ──────────────────────────────────────────────────
async def call_llm(
    prompt: str,
    *,
    operation: str,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """Run an LLM completion with provider routing, fallback, and telemetry.

    Args:
        prompt: Full prompt text.
        operation: Engine name for telemetry grouping
            (e.g. "claim_extractor"). Stamped on the metric row.
        temperature: Model temperature; defaults to 0.1.
        max_output_tokens: Hard cap on response length.
        model: Optional model override.
        provider: Optional explicit provider name. When None, reads
            ``settings.LLM_PROVIDER`` (default ``gemini``).

    Returns:
        Stripped response text. Empty string when the chosen provider
        is unconfigured (matches the legacy ``call_gemini`` contract so
        engines don't need to change).

    Behavior:
        - If the primary provider is degraded (3 consecutive failures
          within the cooldown) AND a fallback is configured, the
          fallback runs the call directly.
        - On primary success: counter is reset.
        - On primary failure that succeeds via fallback: primary counter
          increments; fallback success doesn't reset the primary.
        - On both primary AND fallback failure: ``LLMProviderError``
          propagates. The engine's ``@with_retry`` decorator may try
          again or surface the failure as a structured warning.
    """
    primary = get_llm(provider)
    if not primary.is_configured():
        # No key → legacy behavior of "" so engines can gracefully
        # report a missing-config warning without raising.
        return ""

    fallback = get_fallback_provider() if provider is None else None
    use_provider = primary

    if _is_degraded(primary.name) and fallback is not None:
        logger.info(
            "Primary LLM provider %s is degraded — routing to fallback %s",
            primary.name,
            fallback.name,
        )
        use_provider = fallback

    tracer = _tracer()
    start = time.monotonic()
    response: Optional[LLMResponse] = None
    error_class: Optional[str] = None
    served_by = use_provider

    span_ctx = (
        tracer.start_as_current_span(
            "llm.generate",
            attributes={
                "llm.provider": use_provider.name,
                "llm.operation": operation,
                "llm.prompt_chars": len(prompt),
                "llm.temperature": temperature,
            },
        )
        if tracer
        else None
    )

    try:
        if span_ctx:
            span_ctx.__enter__()
        try:
            response = await use_provider.generate(
                prompt,
                operation=operation,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                model=model,
            )
            _record_success(use_provider.name)
        except Exception as e:
            error_class = type(e).__name__
            _record_failure(use_provider.name)
            # First try the fallback if we haven't already.
            if (
                fallback is not None
                and use_provider is primary
                and primary is not fallback
            ):
                logger.warning(
                    "LLM primary %s raised %s — trying fallback %s",
                    primary.name,
                    error_class,
                    fallback.name,
                )
                served_by = fallback
                try:
                    response = await fallback.generate(
                        prompt,
                        operation=operation,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        model=model,
                    )
                    _record_success(fallback.name)
                    error_class = None
                except Exception as fe:
                    _record_failure(fallback.name)
                    raise LLMProviderError(
                        f"Both primary ({primary.name}: {error_class}) and "
                        f"fallback ({fallback.name}: {type(fe).__name__}) failed"
                    ) from fe
            else:
                raise
        return response.text if response else ""
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        if span_ctx:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:
                pass
        # Schedule metric write without blocking. Production hosts always
        # have a running loop; tests may not, hence the RuntimeError
        # fall-through.
        record_model = (
            response.model
            if response
            else (model or served_by.default_model)
        )
        try:
            asyncio.create_task(
                _persist_metric(
                    provider=served_by.name,
                    operation=operation,
                    model=record_model,
                    input_tokens=response.input_tokens if response else None,
                    output_tokens=response.output_tokens if response else None,
                    total_tokens=response.total_tokens if response else None,
                    latency_ms=latency_ms,
                    error_class=error_class,
                )
            )
        except RuntimeError:
            try:
                asyncio.run(
                    _persist_metric(
                        provider=served_by.name,
                        operation=operation,
                        model=record_model,
                        input_tokens=response.input_tokens if response else None,
                        output_tokens=response.output_tokens if response else None,
                        total_tokens=response.total_tokens if response else None,
                        latency_ms=latency_ms,
                        error_class=error_class,
                    )
                )
            except Exception:
                pass
