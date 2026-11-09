"""Provider-agnostic LLM service.

Every analysis engine (claim_extractor, fact_checker, ai_detector,
topic_analyzer, origin_tracer, narrative_generator) goes through this
service instead of importing a provider SDK directly. Operators switch
providers via ``settings.LLM_PROVIDER`` without touching engine code.

Why this matters:
  - A single-provider lock-in means a Google API outage hard-stops every
    pipeline. With this abstraction the operator can flip
    ``LLM_PROVIDER=openai`` in the environment and the pipelines keep
    running on a different vendor.
  - Pricing varies by provider. The cost dashboard joins on the
    ``provider`` column added in migration 0016 so finance reports
    can attribute spend correctly.
  - Per-operation prompt engineering can pick provider-specific
    strengths in the future (e.g. Anthropic for narrative work,
    Gemini for high-volume classification).

Public surface:
  - ``call_llm(prompt, *, operation, ...)`` — the engine-facing entry
    point. Picks the default provider, runs the call, writes a metric
    row, falls back to the secondary provider if the primary errs 3×
    consecutively.
  - ``get_llm(name=None)`` — factory; explicit provider selection.
  - ``LLMResponse`` — the unified response dataclass.
  - ``LLMProviderError`` — raised when a provider can't be reached
    after both primary and fallback fail.

Module-load behavior: every concrete provider is registered at import
time so ``get_llm("openai")`` works without the caller importing the
provider module.
"""

from app.services.llm.base import LLMProvider, LLMResponse, LLMProviderError
from app.services.llm.factory import (
    call_llm,
    estimate_cost_usd,
    get_llm,
    register_provider,
    PROVIDER_PRICING,
)

# Side-effect imports: each provider self-registers via
# register_provider() on import. The factory's get_llm() then routes
# by name without needing per-call imports.
from app.services.llm.providers import gemini as _gemini  # noqa: F401
from app.services.llm.providers import openai as _openai  # noqa: F401
from app.services.llm.providers import anthropic as _anthropic  # noqa: F401


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMProviderError",
    "call_llm",
    "estimate_cost_usd",
    "get_llm",
    "register_provider",
    "PROVIDER_PRICING",
]
