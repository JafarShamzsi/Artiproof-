"""Bounded HTTP(S) fetching for untrusted article and citation URLs.

Resolve at connection time and dial only validated numeric addresses. HTTP
Host and TLS SNI remain the original hostname, so TLS verification stays on.
No proxy, alternate transport, credential or redirect can bypass this backend.
"""

import asyncio
import ipaddress
import socket
import ssl
from urllib.parse import urljoin

import httpcore
import httpx

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
TOTAL_SECONDS = 20


class UnsafeURL(ValueError):
    """The destination or response violates the public-fetch policy."""


def public_url(value: str) -> httpx.URL:
    if not isinstance(value, str) or len(value) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise UnsafeURL("Invalid public URL")
    try:
        url = httpx.URL(value.strip())
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
            raise UnsafeURL("Only public HTTP(S) URLs without credentials are supported")
        if url.port not in {None, 80 if url.scheme == "http" else 443}:
            raise UnsafeURL("Only standard HTTP(S) ports are supported")
        host = url.host.lower().rstrip(".")
        if host in {"localhost", "metadata", "metadata.google.internal"} or host.endswith((".localhost", ".local", ".internal")):
            raise UnsafeURL("Private network destinations are not supported")
        if "%" in host:
            raise UnsafeURL("Scoped addresses are not supported")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None and not is_public_address(str(literal)):
            raise UnsafeURL("Private network destinations are not supported")
    except httpx.InvalidURL as exc:
        raise UnsafeURL("Invalid public URL") from exc
    return url.copy_with(fragment=None)


def is_public_address(value: str) -> bool:
    if "%" in value:
        return False
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not address.is_global or address.is_multicast or address.is_reserved or getattr(address, "is_site_local", False):
        return False
    if isinstance(address, ipaddress.IPv6Address):
        # Transition mechanisms can tunnel a nominally global IPv6 address to
        # IPv4/private destinations. Public fetches do not need these ranges.
        if address.ipv4_mapped or address.sixtofour or address.teredo:
            return False
        if any(address in ipaddress.ip_network(network) for network in ("64:ff9b::/96", "64:ff9b:1::/48")):
            return False
    return True


async def resolve_public(host: str, port: int) -> list[str]:
    try:
        async with asyncio.timeout(3):
            answers = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, TimeoutError) as exc:
        raise httpx.ConnectError("Public host resolution failed") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    # Reject the entire answer set, including mixed public/private DNS. Passing
    # a prevalidated numeric IP to connect_tcp prevents a second DNS lookup.
    if not addresses or len(addresses) > 64 or not all(is_public_address(address) for address in addresses):
        raise UnsafeURL("Destination did not resolve exclusively to public addresses")
    return addresses


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, *, resolver=resolve_public, backend=None):
        self.resolver = resolver
        self.backend = backend if backend is not None else httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await self.resolver(host, port)
        if not addresses or not all(is_public_address(address) for address in addresses):
            raise UnsafeURL("Non-public network address rejected")
        # Limit connection attempts as well as time. The outer fetch deadline
        # includes DNS, connection, TLS, redirects and streaming body reads.
        last_error = None
        for address in addresses[:4]:
            try:
                return await self.backend.connect_tcp(address, port, timeout=timeout,
                    local_address=local_address, socket_options=socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        raise last_error


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        try:
            async for part in self.stream:
                yield part
        except (httpcore.NetworkError, httpcore.TimeoutException, httpcore.ProtocolError) as exc:
            raise httpx.RequestError("Public response could not be read") from exc

    async def aclose(self):
        await self.stream.aclose()


class PublicTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, network_backend=None):
        self.pool = httpcore.AsyncConnectionPool(ssl_context=ssl.create_default_context(),
            network_backend=network_backend or PublicNetworkBackend(), max_connections=4,
            max_keepalive_connections=0, retries=0)

    async def handle_async_request(self, request):
        public_url(str(request.url))
        core_request = httpcore.Request(method=request.method,
            url=httpcore.URL(scheme=request.url.raw_scheme, host=request.url.raw_host,
                             port=request.url.port, target=request.url.raw_path),
            headers=request.headers.raw, content=request.stream, extensions=request.extensions)
        try:
            response = await self.pool.handle_async_request(core_request)
        except (httpcore.NetworkError, httpcore.TimeoutException, httpcore.ProtocolError) as exc:
            raise httpx.RequestError("Public URL connection failed", request=request) from exc
        return httpx.Response(response.status, headers=response.headers,
            stream=_ResponseStream(response.stream), extensions=response.extensions, request=request)

    async def aclose(self):
        await self.pool.aclose()


async def fetch_public(url: str, *, method: str = "GET", purpose: str = "article", transport=None) -> httpx.Response:
    """Fetch small uncompressed article HTML or citation headers, within one deadline."""
    if method not in {"GET", "HEAD"}:
        raise ValueError("Unsupported public fetch method")
    if purpose not in {"article", "image"}:
        raise ValueError("Unsupported public fetch purpose")
    target = public_url(url)
    try:
        async with asyncio.timeout(TOTAL_SECONDS):
            async with httpx.AsyncClient(transport=transport or PublicTransport(), trust_env=False,
                follow_redirects=False, timeout=httpx.Timeout(8, connect=4),
                headers={"User-Agent": "ArtiProof/1.0 (+https://artiproof.com)",
                         "Accept": "image/png,image/jpeg" if purpose == "image" else "text/html,application/xhtml+xml,text/plain", "Accept-Encoding": "identity"}) as client:
                for hop in range(MAX_REDIRECTS + 1):
                    async with client.stream(method, target) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location or hop == MAX_REDIRECTS:
                                raise UnsafeURL("Redirect limit exceeded or target missing")
                            target = public_url(urljoin(str(target), location))
                            continue
                        if method == "HEAD":
                            return httpx.Response(response.status_code, headers=response.headers, request=response.request)
                        response.raise_for_status()
                        media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        allowed = {"image/png", "image/jpeg"} if purpose == "image" else {"text/html", "application/xhtml+xml", "text/plain"}
                        if media_type not in allowed:
                            raise UnsafeURL("Response is not supported article text")
                        if response.headers.get("content-encoding", "identity").lower() != "identity":
                            raise UnsafeURL("Compressed article responses are not supported")
                        size, parts = 0, []
                        async for part in response.aiter_raw():
                            size += len(part)
                            if size > MAX_BYTES:
                                raise UnsafeURL("Article response exceeds the size limit")
                            parts.append(part)
                        return httpx.Response(response.status_code, headers=response.headers,
                            content=b"".join(parts), request=response.request)
    except TimeoutError as exc:
        raise httpx.ReadTimeout("Public fetch deadline exceeded") from exc
    raise UnsafeURL("Redirect limit exceeded")
