"""URL validation helpers — primarily SSRF defense for user-supplied
URLs that the *server* will fetch (e.g. a logo URL embedded in a PDF
that WeasyPrint pulls down at render time).

The validator rejects anything that resolves to a private/loopback/
link-local host or uses a non-HTTP scheme. It is intentionally strict
about ``logo_url``: a leak of cloud metadata via 169.254.169.254 is
the canonical attack and we'd rather break a legitimate edge case
than ship the gap.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


# Hostname-string blocklist — these never resolve to anything safe.
# Any input that exactly matches (case-insensitive) is rejected before
# we even consider IP-literal classification.
_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
}


def _is_private_or_reserved(host: str) -> bool:
    """Return True if ``host`` is an IP literal in any private,
    loopback, link-local, multicast, or otherwise non-routable range
    (IPv4 + IPv6). Returns False for non-IP hostnames — caller decides
    what to do with those (we choose: allow, since DNS resolution is
    racy and the renderer's HTTP fetch happens after schema check)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_safe_external_url(value: str) -> str:
    """Validate that ``value`` is an external HTTP(S) URL safe for the
    server to fetch.

    Raises ``ValueError`` (Pydantic surfaces it as 422) on:
    - non-HTTP/HTTPS scheme (``file://``, ``ftp://``, ``javascript:``, …)
    - missing host
    - hostname in the literal blocklist (``localhost``, cloud metadata)
    - host that's an IP literal in a private/reserved range
      (``127.0.0.1``, ``10.0.0.1``, ``169.254.169.254``, ``::1``, …)

    Note: this does not resolve DNS. A hostname that resolves to a
    private IP at fetch time will still slip through. Defense-in-depth
    at the HTTP-client layer is still required for full SSRF coverage,
    but this catches every literal-attack vector.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("URL is required")

    parsed = urlparse(value.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    if scheme == "http":
        # HTTPS-only — non-HTTPS is suspicious for a logo CDN and would
        # also leak the request over the wire when WeasyPrint fetches.
        raise ValueError("URL must use https")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL must include a host")
    if host in _BLOCKED_HOSTNAMES:
        raise ValueError("URL host is not allowed")
    if _is_private_or_reserved(host):
        raise ValueError("URL host is in a private or reserved range")

    return value
