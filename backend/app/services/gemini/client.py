"""Back-compat shim — ``call_gemini`` delegates to the new LLM service.

Phase 9 introduced a provider-agnostic abstraction at
``app.services.llm``. Engines (claim_extractor, fact_checker,
ai_detector, topic_analyzer, origin_tracer, narrative_generator) still
import ``call_gemini`` from this module so the rename didn't ripple
across the codebase. Behavior is unchanged from the engine's POV:
prompt in, text out, telemetry written.

Prefer ``from app.services.llm import call_llm`` in new engines.
"""

from __future__ import annotations

from typing import Optional

from app.services.llm import (
    PROVIDER_PRICING,
    call_llm,
    estimate_cost_usd as _estimate_cost_usd,
)
# Re-export the factory's fallback price for tests that imported the
# private constant from the legacy single-provider module.
from app.services.llm.factory import _FALLBACK_PRICE  # noqa: F401


__all__ = [
    "call_gemini",
    "estimate_cost_usd",
    "GEMINI_PRICING",
    "_FALLBACK_PRICE",
]


# Back-compat: ``GEMINI_PRICING`` used to live here. The new
# authoritative pricing table is ``PROVIDER_PRICING['gemini']`` in
# ``app.services.llm.factory``. Re-export so the admin
# ``/api/admin/gemini/cost-summary`` route and any finance scripts keep
# working without code changes.
GEMINI_PRICING = PROVIDER_PRICING.get("gemini", {})


def estimate_cost_usd(
    *, input_tokens: int, output_tokens: int, model: str
) -> float:
    """Legacy single-provider cost helper. Routes through the new
    multi-provider pricing table with ``provider='gemini'`` so the
    answer matches the pre-Phase-9 behavior.
    """
    return _estimate_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        provider="gemini",
    )


async def call_gemini(
    prompt: str,
    *,
    operation: str,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
    model: Optional[str] = None,
) -> str:
    """Legacy entry point for engines that pre-date the LLM abstraction.

    Delegates to ``call_llm`` which:
      - Routes to ``settings.LLM_PROVIDER`` (defaults to gemini).
      - Records the call in ``llm_metrics`` with the actual provider name.
      - Falls back to ``settings.LLM_FALLBACK_PROVIDER`` on consecutive
        failures (3-strike threshold, 5-min cooldown).
    """
    return await call_llm(
        prompt,
        operation=operation,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        model=model,
    )
