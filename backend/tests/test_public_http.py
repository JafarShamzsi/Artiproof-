import asyncio
import socket
import ssl
from unittest.mock import AsyncMock

import httpcore
import httpx
import pytest

from app.utils import public_http as ph


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/x", "https://user:pass@example.com",
    "http://127.0.0.1", "http://[::1]", "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.1", "https://localhost./", "https://x.local/", "https://metadata.google.internal",
    "https://example.com:8443/", "https://example.com/\r\nx", "https://[fe80::1%25eth0]/",
    "http://[::ffff:127.0.0.1]", "http://[64:ff9b::a00:1]",
])
def test_unsafe_url_rejected(url):
    with pytest.raises(ph.UnsafeURL):
        ph.public_url(url)


@pytest.mark.parametrize("address", ["0.0.0.0", "100.64.0.1", "192.0.2.1", "224.0.0.1", "ff02::1", "2002:0808:0808::1", "64:ff9b:1::1", "::ffff:8.8.8.8"])
def test_non_public_or_transition_address_rejected(address):
    assert not ph.is_public_address(address)


@pytest.mark.asyncio
async def test_mixed_dns_answers_rejected(monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "getaddrinfo", AsyncMock(return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
    ]))
    with pytest.raises(ph.UnsafeURL):
        await ph.resolve_public("mixed.example", 443)


class WireStream(httpcore.AsyncNetworkStream):
    def __init__(self, response):
        self.response = response
        self.written = b""
        self.tls = []
        self.closed = False

    async def read(self, max_bytes, timeout=None):
        chunk, self.response = self.response[:max_bytes], self.response[max_bytes:]
        return chunk

    async def write(self, buffer, timeout=None):
        self.written += buffer

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.tls.append((ssl_context.verify_mode, server_hostname))
        return self

    async def aclose(self):
        self.closed = True


class WireBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.streams = []
        self.connections = []

    async def connect_tcp(self, host, port, **kwargs):
        self.connections.append((host, port))
        stream = WireStream(self.responses.pop(0))
        self.streams.append(stream)
        return stream


def transport(responses, resolver=None):
    wire = WireBackend(responses)
    backend = ph.PublicNetworkBackend(resolver=resolver or AsyncMock(return_value=["8.8.8.8"]), backend=wire)
    return ph.PublicTransport(network_backend=backend), wire


def html_response(body=b"<p>Public article</p>", headers=b""):
    return b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: " + str(len(body)).encode() + b"\r\n" + headers + b"\r\n" + body


@pytest.mark.asyncio
async def test_connection_pinned_to_ip_preserves_host_and_tls_name(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1234")
    resolver = AsyncMock(return_value=["8.8.8.8"])
    client_transport, wire = transport([html_response()], resolver)
    response = await ph.fetch_public("https://public.example/article", transport=client_transport)
    assert response.text == "<p>Public article</p>"
    assert wire.connections == [("8.8.8.8", 443)]
    resolver.assert_awaited_once_with("public.example", 443)
    assert b"Host: public.example\r\n" in wire.streams[0].written
    assert wire.streams[0].tls == [(ssl.CERT_REQUIRED, "public.example")]
    assert wire.streams[0].closed


@pytest.mark.asyncio
async def test_redirect_to_private_literal_never_connects():
    client_transport, wire = transport([b"HTTP/1.1 302 Found\r\nLocation: http://169.254.169.254/latest/\r\nContent-Length: 0\r\n\r\n"])
    with pytest.raises(ph.UnsafeURL):
        await ph.fetch_public("https://public.example/article", transport=client_transport)
    assert len(wire.connections) == 1
    assert wire.streams[0].closed


@pytest.mark.asyncio
async def test_redirect_hostname_resolving_private_never_connects():
    resolver = AsyncMock(side_effect=[["8.8.8.8"], ["10.0.0.1"]])
    client_transport, wire = transport([b"HTTP/1.1 302 Found\r\nLocation: https://other.example/\r\nContent-Length: 0\r\n\r\n"], resolver)
    with pytest.raises(ph.UnsafeURL):
        await ph.fetch_public("https://public.example/article", transport=client_transport)
    assert wire.connections == [("8.8.8.8", 443)]


@pytest.mark.asyncio
async def test_relative_redirect_and_final_url():
    client_transport, wire = transport([
        b"HTTP/1.1 302 Found\r\nLocation: /new/article\r\nContent-Length: 0\r\n\r\n", html_response(),
    ])
    response = await ph.fetch_public("https://public.example/old/article", transport=client_transport)
    assert str(response.url) == "https://public.example/new/article"
    assert b"GET /new/article " in wire.streams[-1].written


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [b"Content-Encoding: gzip\r\n", b"Content-Encoding: br\r\n"])
async def test_compressed_body_rejected_before_decompression(headers):
    client_transport, _ = transport([html_response(headers=headers)])
    with pytest.raises(ph.UnsafeURL, match="Compressed"):
        await ph.fetch_public("https://public.example/", transport=client_transport)


@pytest.mark.asyncio
async def test_streaming_size_bound_closes_response(monkeypatch):
    monkeypatch.setattr(ph, "MAX_BYTES", 10)
    client_transport, wire = transport([html_response(b"x" * 100)])
    with pytest.raises(ph.UnsafeURL, match="size limit"):
        await ph.fetch_public("https://public.example/", transport=client_transport)
    assert wire.streams[0].closed


@pytest.mark.asyncio
async def test_total_deadline_includes_resolution(monkeypatch):
    monkeypatch.setattr(ph, "TOTAL_SECONDS", 0.01)
    async def slow_resolve(host, port):
        await asyncio.sleep(1)
        return ["8.8.8.8"]
    client_transport, wire = transport([], slow_resolve)
    with pytest.raises(httpx.ReadTimeout):
        await ph.fetch_public("https://public.example/", transport=client_transport)
    assert wire.connections == []


@pytest.mark.asyncio
async def test_scraper_uses_final_location_for_relative_references(monkeypatch):
    from app.services.source_verification import scraper
    response = httpx.Response(200, text='<article><p>Article paragraph with readable words.</p><a href="../reference">Reference</a></article>',
                              request=httpx.Request("GET", "https://public.example/new/article"))
    monkeypatch.setattr(scraper, "fetch_public", AsyncMock(return_value=response))
    result = await scraper.scrape_url("https://public.example/old/path")
    assert result["citations"][0]["url"] == "https://public.example/reference"
