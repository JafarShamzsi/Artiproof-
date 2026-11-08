"""Centralized Gemini call with usage tracking + OTel span.

Pricing constants live here because they change quarterly — easier to
update one source-of-truth than chase them through orchestrators. The
admin cost dashboard reads ``estimate_cost_usd`` to convert raw token
counts into a billing-grade number; the DB only ever stores tokens (so
re-pricing history is a SQL UPDATE, not a backfill).

Every call is best-effort:
  - If the metric write throws, the Gemini result is still returned.
  - If OTel isn't initialized, the span is a no-op.
  - If usage_metadata is missing on the response, the row records NULL
    tokens (still useful — latency + count + error are still there).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional

from google import genai
from google.genai import types

from app.config import settings
from app.context import (
    current_researcher_profile_id,
    current_source_check_id,
    current_user_id,
)
from app.database import async_session
from app.models.gemini_metric import GeminiMetric

logger = logging.getLogger(__name__)


# ─── Pricing ─────────────────────────────────────────────────────────
# USD per 1M tokens. Update when Google revises pricing — the DB stores
# raw tokens so all historical rows reprice automatically.
# Source: ai.google.dev/pricing (verify before relying on the dashboard
# number for finance reporting).
GEMINI_PRICING: dict[str, dict[str, float]] = {
    # Flash family — cheapest, used for most pipeline work.
    "gemini-2.0-flash": {"input_per_1m": 0.10, "output_per_1m": 0.40},
    "gemini-2.0-flash-lite": {"input_per_1m": 0.075, "output_per_1m": 0.30},
    "gemini-1.5-flash": {"input_per_1m": 0.075, "output_per_1m": 0.30},
    "gemini-1.5-flash-8b": {"input_per_1m": 0.0375, "output_per_1m": 0.15},
    # Pro family — used for narrative generation when premium output matters.
    "gemini-2.0-pro": {"input_per_1m": 1.25, "output_per_1m": 5.00},
    "gemini-1.5-pro": {"input_per_1m": 1.25, "output_per_1m": 5.00},
}
# Used when we see a model we haven't priced. Conservative midpoint so
# the dashboard underestimates rather than overestimates — finance gets
# a "≥" number, not a "≤" one.
_FALLBACK_PRICE = {"input_per_1m": 0.10, "output_per_1m": 0.40}


def estimate_cost_usd(
    *, input_tokens: int, output_tokens: int, model: str
) -> float:
    """Convert raw token counts into a USD estimate.

    Returns 0.0 for zero tokens. Unknown models fall back to a midpoint
    rate so the dashboard doesn't display $0 for everything.
    """
    if not input_tokens and not output_tokens:
        return 0.0
    price = GEMINI_PRICING.get(model, _FALLBACK_PRICE)
    return round(
        (input_tokens / 1_000_000) * price["input_per_1m"]
        + (output_tokens / 1_000_000) * price["output_per_1m"],
        6,
    )


# ─── Client singleton ────────────────────────────────────────────────
_client: "genai.Client | None" = None


def _gemini_client() -> "genai.Client | None":
    """Lazy module-level singleton — one Client per process, not per call."""
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# ─── OTel helper (no-op when uninitialized) ─────────────────────────────
def _tracer():
    """Return an OTel tracer if available, else None. The metrics path
    doesn't depend on this — it's purely for distributed-tracing UIs."""
    try:
        from opentelemetry import trace  # type: ignore

        return trace.get_tracer("artiproof.gemini")
    except Exception:
        return None


# ─── Metric persistence ──────────────────────────────────────────────
async def _persist_metric(
    *,
    operation: str,
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    total_tokens: Optional[int],
    latency_ms: int,
    error_class: Optional[str],
) -> None:
    """Best-effort write. Failures are logged but never raised — the
    Gemini result has already been returned to the engine."""
    try:
        async with async_session() as db:
            row = GeminiMetric(
                id=str(uuid.uuid4()),
                user_id=current_user_id.get(),
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
        # Demote to debug — telemetry write failures shouldn't be alert noise.
        logger.debug("Gemini metric write failed: %s", type(e).__name__)


# ─── Public entry point ─────────────────────────────────────────────
async def call_gemini(
    prompt: str,
    *,
    operation: str,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
    model: Optional[str] = None,
) -> str:
    """Run a Gemini generate_content call with telemetry + tracing.

    Args:
        prompt: the full prompt text.
        operation: short engine name — "claim_extractor", "fact_checker",
            "ai_detector", "topic_analyzer", "origin_tracer",
            "narrative_generator". Used to group rows in the cost dashboard.
        temperature: model temperature.
        max_output_tokens: hard cap on response length.
        model: override the default model. When None, uses settings.GEMINI_MODEL.

    Returns:
        The stripped response text. Empty string if GEMINI_API_KEY is unset
        (consistent with the previous per-engine behavior).

    The caller already wraps this in @with_retry where retries are
    desired; we don't double up.
    """
    client = _gemini_client()
    if client is None:
        return ""
    effective_model = model or settings.GEMINI_MODEL

    tracer = _tracer()
    start = time.monotonic()
    in_tokens: Optional[int] = None
    out_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_class: Optional[str] = None

    span_ctx = (
        tracer.start_as_current_span(
            "gemini.generate_content",
            attributes={
                "gemini.operation": operation,
                "gemini.model": effective_model,
                "gemini.prompt_chars": len(prompt),
                "gemini.temperature": temperature,
            },
        )
        if tracer
        else None
    )

    try:
        if span_ctx:
            span_ctx.__enter__()
        try:
            response = await client.aio.models.generate_content(
                model=effective_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
        except Exception as e:
            error_class = type(e).__name__
            raise
        # usage_metadata may be absent on stream/error paths. Grab what
        # we can; rest stays NULL.
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            in_tokens = getattr(usage, "prompt_token_count", None)
            out_tokens = getattr(usage, "candidates_token_count", None)
            total_tokens = getattr(usage, "total_token_count", None)
            if span_ctx is not None and total_tokens is not None:
                try:
                    span_ctx.__enter__  # already entered above
                    from opentelemetry import trace  # type: ignore

                    trace.get_current_span().set_attribute(
                        "gemini.input_tokens", in_tokens or 0
                    )
                    trace.get_current_span().set_attribute(
                        "gemini.output_tokens", out_tokens or 0
                    )
                except Exception:
                    pass
        return (response.text or "").strip()
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        if span_ctx:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:
                pass
        # Schedule the metric write without blocking the caller. The
        # session/transaction is independent of any outer request scope.
        try:
            asyncio.create_task(
                _persist_metric(
                    operation=operation,
                    model=effective_model,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    error_class=error_class,
                )
            )
        except RuntimeError:
            # No running loop — happens in some test contexts. Fire
            # synchronously instead so the row still lands.
            try:
                asyncio.run(
                    _persist_metric(
                        operation=operation,
                        model=effective_model,
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        total_tokens=total_tokens,
                        latency_ms=latency_ms,
                        error_class=error_class,
                    )
                )
            except Exception:
                pass
