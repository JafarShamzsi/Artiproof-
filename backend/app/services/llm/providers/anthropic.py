"""Anthropic provider (anthropic-python).

Wraps the official ``anthropic`` AsyncAnthropic client. Uses the
Messages API (the only stable inference primitive in v1+).
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.services.llm.base import LLMProvider, LLMResponse
from app.services.llm.factory import register_provider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return settings.ANTHROPIC_MODEL or "claude-3-5-haiku-20241022"

    def is_configured(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY)

    async def generate(
        self,
        prompt: str,
        *,
        operation: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        client = _anthropic_client()
        if client is None:
            return LLMResponse(
                text="",
                model=model or self.default_model,
                provider=self.name,
            )

        effective_model = model or self.default_model
        response = await client.messages.create(
            model=effective_model,
            max_tokens=max_output_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic's response: content is a list of blocks; text blocks
        # have .text. Concatenate them since rare multi-block responses
        # would otherwise drop content.
        parts: list[str] = []
        for block in response.content or []:
            # ContentBlock for text uses block.type == "text" + block.text.
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
        text = "".join(parts).strip()
        usage = response.usage
        return LLMResponse(
            text=text,
            model=effective_model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=(
                (getattr(usage, "input_tokens", 0) or 0)
                + (getattr(usage, "output_tokens", 0) or 0)
            )
            if usage
            else None,
        )


# ─── Module-level client singleton ─────────────────────────────────
_client = None


def _anthropic_client():
    global _client
    if _client is None and settings.ANTHROPIC_API_KEY:
        try:
            from anthropic import AsyncAnthropic

            _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        except ImportError:
            logger.info("anthropic package not installed — provider unavailable")
    return _client


register_provider(AnthropicProvider())
