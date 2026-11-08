"""LLM provider interface.

Every concrete provider implements ``LLMProvider`` and returns an
``LLMResponse``. The factory routes calls to whichever provider is
selected via env / per-call override.

The interface is deliberately narrow — generate() takes a prompt and
returns text + usage. No streaming, no tool calls, no embeddings yet.
When those become engine requirements, the interface grows; for now,
the analysis pipeline only needs one-shot completion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Unified response shape across providers.

    Every provider normalises its own SDK's response onto this struct so
    the factory + metric writer can treat them identically.

    Fields:
        text: The model's textual completion, stripped of trailing
            whitespace. Empty when the provider returned no content.
        model: Provider-specific model identifier (e.g.
            "gemini-2.0-flash", "gpt-4o-mini", "claude-3-5-haiku-20241022").
        provider: Short identifier — "gemini" | "openai" | "anthropic".
            Used to attribute the row in llm_metrics.provider and to
            drive the by-provider rollup in the admin cost dashboard.
        input_tokens, output_tokens, total_tokens: Usage figures lifted
            from the provider's response. May be None if the SDK
            omitted them (some streaming + error paths drop usage).
    """

    text: str
    model: str
    provider: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class LLMProviderError(Exception):
    """Raised when an LLM call cannot be served by ANY configured provider.

    The factory catches per-provider exceptions and tries the fallback
    chain; this is the terminal exception that bubbles to the engine
    layer when even the fallback can't serve the call. The engine then
    decides whether to swallow (its with_retry decorator) or surface as
    a warning to the user.
    """


class LLMProvider(ABC):
    """Abstract provider — implement once per vendor."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier ("gemini" | "openai" | "anthropic").

        Used as the dict key in the provider registry and as the
        ``llm_metrics.provider`` value.
        """

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier when generate() is called without
        an explicit ``model=`` override.

        Read from settings (e.g. ``GEMINI_MODEL``, ``OPENAI_MODEL``,
        ``ANTHROPIC_MODEL``) so an operator can swap models without
        editing code.
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has its API key configured and is ready
        to serve calls. Called by the factory when picking a fallback —
        a fallback provider with no API key is silently skipped.
        """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        operation: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Run a single completion call.

        Args:
            prompt: The full prompt text. Providers wrap this into their
                native message shape (Gemini: contents=prompt; OpenAI:
                messages=[{role:"user", content:prompt}]; Anthropic:
                messages=[{role:"user", content:prompt}]).
            operation: Engine name passed through for telemetry only
                (e.g. "claim_extractor"). Providers don't use it; the
                factory stamps it on the metric row.
            temperature: Model temperature, defaults to 0.1 (low-noise,
                consistent classification output).
            max_output_tokens: Hard ceiling on response length.
            model: Optional override; falls back to ``default_model``.

        Returns:
            ``LLMResponse`` with the text + usage tokens normalised.

        Raises:
            On provider-side errors (rate limit, timeout, malformed
            response, etc.). The factory catches these and tries the
            fallback provider. If every provider fails, raises
            ``LLMProviderError``.
        """
