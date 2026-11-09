"""Tests for validation regexes and the retry decorator."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.routers.researcher import ORCID_PATTERN
from app.utils.retry import HTTP_RETRY_EXCEPTIONS, with_retry


class TestOrcidRegex:
    @pytest.mark.parametrize(
        "valid",
        [
            "0000-0001-2345-6789",
            "0000-0002-1825-0097",   # the canonical Public ORCID example
            "1234-5678-9012-345X",   # X check digit
            "0000-0000-0000-0000",
        ],
    )
    def test_accepts_valid_format(self, valid):
        assert ORCID_PATTERN.match(valid) is not None

    @pytest.mark.parametrize(
        "invalid",
        [
            "",
            "not-an-orcid",
            "0000-0001-2345-678",        # too short
            "0000-0001-2345-67890",      # too long
            "0000_0001_2345_6789",       # wrong separator
            "0000-0001-2345-678Y",       # Y is not allowed (only X)
            "ABCD-0001-2345-6789",       # letters in wrong slot
            "0000-0001-2345-6789 ",      # trailing whitespace
        ],
    )
    def test_rejects_invalid_format(self, invalid):
        assert ORCID_PATTERN.match(invalid) is None


class TestRetryDecorator:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        calls = 0

        @with_retry(max_retries=3, exceptions=HTTP_RETRY_EXCEPTIONS)
        async def f():
            nonlocal calls
            calls += 1
            return "ok"

        assert await f() == "ok"
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_error_then_succeeds(self):
        calls = 0

        @with_retry(max_retries=3, base_delay=0.001, exceptions=HTTP_RETRY_EXCEPTIONS)
        async def f():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise httpx.TimeoutException("timeout")
            return "ok"

        assert await f() == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries_then_reraises(self):
        @with_retry(max_retries=2, base_delay=0.001, exceptions=HTTP_RETRY_EXCEPTIONS)
        async def f():
            raise httpx.TimeoutException("never recovers")

        with pytest.raises(httpx.TimeoutException):
            await f()

    @pytest.mark.asyncio
    async def test_retries_5xx_status(self):
        """500-level HTTPStatusError should retry; 4xx should not."""
        calls = 0

        @with_retry(max_retries=2, base_delay=0.001)
        async def f():
            nonlocal calls
            calls += 1
            resp = httpx.Response(500)
            raise httpx.HTTPStatusError("server error", request=httpx.Request("GET", "http://x"), response=resp)

        with pytest.raises(httpx.HTTPStatusError):
            await f()
        assert calls == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_does_not_retry_4xx(self):
        calls = 0

        @with_retry(max_retries=3, base_delay=0.001)
        async def f():
            nonlocal calls
            calls += 1
            resp = httpx.Response(404)
            raise httpx.HTTPStatusError("not found", request=httpx.Request("GET", "http://x"), response=resp)

        with pytest.raises(httpx.HTTPStatusError):
            await f()
        assert calls == 1  # no retries for 4xx

    @pytest.mark.asyncio
    async def test_retries_429(self):
        """429 Too Many Requests should be retried."""
        calls = 0

        @with_retry(max_retries=2, base_delay=0.001)
        async def f():
            nonlocal calls
            calls += 1
            resp = httpx.Response(429)
            raise httpx.HTTPStatusError("rate limited", request=httpx.Request("GET", "http://x"), response=resp)

        with pytest.raises(httpx.HTTPStatusError):
            await f()
        assert calls == 3
