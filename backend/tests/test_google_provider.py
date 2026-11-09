"""SDK boundary tests with synthetic responses; no provider network requests."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.llm import factory
from app.services.llm.base import LLMProviderError
from app.services.llm.providers import gemini
from google import genai


@pytest.mark.asyncio
async def test_explicit_developer_api_model_and_bounded_request(monkeypatch):
    monkeypatch.setattr(gemini.settings, 'GEMINI_API_KEY', 'synthetic-only')
    monkeypatch.setattr(gemini.settings, 'GEMINI_MODEL', 'gemini-2.5-flash-lite')
    monkeypatch.setattr(gemini, '_client', None)
    response = SimpleNamespace(text=' synthetic advisory ', usage_metadata=SimpleNamespace(
        prompt_token_count=10, candidates_token_count=4, total_token_count=14))
    generate = AsyncMock(return_value=response)
    constructor = MagicMock(return_value=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    monkeypatch.setattr(genai, 'Client', constructor)
    result = await gemini.GeminiProvider().generate('Synthetic input only', operation='synthetic-test', max_output_tokens=80)
    assert constructor.call_args.kwargs['api_key'] == 'synthetic-only'
    assert constructor.call_args.kwargs.get('vertexai') is False
    options = constructor.call_args.kwargs['http_options']
    assert options.timeout == 20000
    assert options.retry_options.attempts == 1
    assert generate.call_args.kwargs['model'] == 'gemini-2.5-flash-lite'
    assert generate.call_args.kwargs['config'].max_output_tokens == 80
    assert result.text == 'synthetic advisory'
    assert result.provider == 'gemini' and result.total_tokens == 14


@pytest.mark.asyncio
async def test_provider_failure_never_propagates_key_bearing_sdk_message(monkeypatch):
    monkeypatch.setattr(gemini.settings, 'GEMINI_API_KEY', 'synthetic-only')
    generate = AsyncMock(side_effect=RuntimeError('SYNTHETIC_PRIVATE_REQUEST_URL'))
    monkeypatch.setattr(gemini, '_client', SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with pytest.raises(LLMProviderError) as caught:
        await gemini.GeminiProvider().generate('Synthetic', operation='synthetic-test')
    assert 'SYNTHETIC_PRIVATE_REQUEST_URL' not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def test_reviewed_model_has_text_pricing():
    assert factory.estimate_cost_usd(input_tokens=1_000_000, output_tokens=1_000_000,
                                     model='gemini-2.5-flash-lite') == 0.5


@pytest.mark.asyncio
async def test_report_narrative_is_explicitly_advisory(monkeypatch):
    from app.services.report_engine import narrative_generator as narrative
    monkeypatch.setattr(narrative.settings, 'GEMINI_API_KEY', 'synthetic-only')
    monkeypatch.setattr(narrative, 'call_gemini', AsyncMock(return_value='Synthetic summary'))
    result = await narrative._generate('Synthetic fixture')
    assert 'advisory' in result.lower()
    assert 'not verified evidence' in result.lower()


@pytest.mark.asyncio
async def test_citation_suggestion_failure_does_not_log_sdk_payload(monkeypatch, caplog):
    import logging

    from app.services.source_verification import citation_analyzer as citations
    monkeypatch.setattr(citations.settings, 'GEMINI_API_KEY', 'synthetic-only')
    generate = AsyncMock(side_effect=RuntimeError('SYNTHETIC_PRIVATE_REQUEST_URL'))
    monkeypatch.setattr(citations, '_gemini_client', lambda: SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    with caplog.at_level(logging.DEBUG, logger=citations.__name__):
        assert await citations._suggest_alternative_via_gemini('Synthetic reference', 'unavailable') is None
    assert 'SYNTHETIC_PRIVATE_REQUEST_URL' not in caplog.text
