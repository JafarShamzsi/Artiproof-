"""OpenAI provider (openai-python).

Wraps the official ``openai`` AsyncOpenAI client. Uses the Chat
Completions API because every model the engines need (gpt-4o-mini,
gpt-4o, gpt-3.5-turbo) supports it; the newer Responses API offers
nothing extra for our one-shot completion shape.

Why not Assistants API: stateful threads, retrieval, code execution —
none of which the analysis pipeline needs. Chat Completions stays the
right primitive.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.services.llm.base import LLMProvider, LLMResponse
from app.services.llm.factory import register_provider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return settings.OPENAI_MODEL or "gpt-4o-mini"

    def is_configured(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def generate(
        self,
        prompt: str,
        *,
        operation: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        client = _openai_client()
        if client is None:
            return LLMResponse(
                text="",
                model=model or self.default_model,
                provider=self.name,
            )

        effective_model = model or self.default_model
        response = await client.chat.completions.create(
            model=effective_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_completion_tokens=max_output_tokens,
        )
        # OpenAI's response shape: choices[0].message.content + usage.*
        text = ""
        if response.choices:
            text = (response.choices[0].message.content or "").strip()
        usage = response.usage
        return LLMResponse(
            text=text,
            model=effective_model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )


# ─── Module-level client singleton ────────────────────────────────────
_client = None


def _openai_client():
    global _client
    if _client is None and settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI

            _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError:
            # openai package not installed — log once at info, return
            # None so generate() returns empty text without crashing.
            # Operators install the package only when they actually
            # switch LLM_PROVIDER=openai.
            logger.info("openai package not installed — provider unavailable")
    return _client


register_provider(OpenAIProvider())
