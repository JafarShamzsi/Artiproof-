"""Concrete LLM providers — gemini, openai, anthropic.

Each module exports a single provider instance and self-registers
with the factory at import time. The package's ``__init__`` exposes
them all so other code can do ``from app.services.llm.providers
import gemini``.
"""
