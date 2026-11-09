"""Gemini provider (google-genai).

Wraps the existing google-genai async client. The behaviour matches the
pre-abstraction ``app.services.gemini.client.call_gemini`` so engines
that go through the factory get identical output.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.services.llm.base import LLMProvider, LLMProviderError, LLMResponse
from app.services.llm.factory import register_provider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """google-genai-backed provider. Reads GEMINI_API_KEY + GEMINI_MODEL."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return settings.GEMINI_MODEL or "gemini-2.0-flash"

    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    async def generate(
        self,
        prompt: str,
        *,
        operation: str,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        try:
            client = _gemini_client()
        except Exception as exc:
            raise LLMProviderError(f"Gemini initialization failed ({type(exc).__name__})") from None
        if client is None:
            # Unreachable in practice — the factory guards with
            # is_configured() before calling — but we keep the safety
            # path in case a future caller bypasses the factory.
            return LLMResponse(
                text="",
                model=model or self.default_model,
                provider=self.name,
            )

        from google.genai import types  # local import — keep startup light

        effective_model = model or self.default_model
        try:
            response = await client.aio.models.generate_content(
                model=effective_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
        except Exception as exc:
            # Downstream engines may log exception chains. SDK messages can
            # contain request URLs/keys; preserve only the nonsecret class name.
            raise LLMProviderError(f"Gemini request failed ({type(exc).__name__})") from None
        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text=(response.text or "").strip(),
            model=effective_model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            total_tokens=getattr(usage, "total_token_count", None) if usage else None,
        )


# ─── Module-level client singleton ───────────────────────────────────────
# Reused across every call so the underlying HTTP connection pool is
# shared rather than recreated per request.
_client = None


def _gemini_client():
    global _client
    if _client is None and settings.GEMINI_API_KEY:
        from google import genai
        from google.genai import types

        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY, vertexai=False,
            http_options=types.HttpOptions(timeout=20000,
                                          retry_options=types.HttpRetryOptions(attempts=1)),
        )
    return _client


# Self-register at import.
register_provider(GeminiProvider())
