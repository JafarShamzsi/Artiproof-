"""Shared rate limiter instance + tier-aware helpers.

The global ``limiter`` is wired into the FastAPI app state in ``main.py``.
Each router decorates against it with either a static string limit
(auth-style endpoints) or the tier-aware ``tier_aware_limit_for_key``
callable (expensive analysis endpoints).

How slowapi 0.1.9 invokes the limit provider
--------------------------------------------
When the limit value is a callable whose parameter is named ``key``,
slowapi calls it with the result of ``key_func(request)`` — i.e. the
bucket-key string. To keep tier information available at that point,
``user_bucket_key`` encodes both the user id and tier into the key:
``user:<sub>:<tier>``. The limit provider parses the tier back out and
returns the appropriate per-minute cap.

Bucket semantics
----------------
- Authenticated request → ``user:<sub>:<tier>``. Different users get
  different buckets; the same user crossing a tier boundary (e.g. on
  token refresh after an upgrade) gets a fresh bucket, which is the
  conservative-but-fair behaviour.
- Unauthenticated / malformed token → ``ip:<addr>``. Anonymous callers
  always get the strictest cap regardless of which endpoint they hit.

Tier-on-token
-------------
The user's tier is embedded in the JWT (see ``create_access_token``)
so we don't need a DB round-trip per request. Tier changes propagate at
the next token refresh (24h max). For rate-limit purposes that's
forgiving for downgrades and trivially corrected for upgrades.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.constants import ANONYMOUS_RATE_LIMIT, TIER_RATE_LIMITS

_CTX_ATTR = "_rate_limit_ctx"


def _decode_token_silently(request: Request) -> Optional[dict]:
    """Decode the Bearer token without raising. Used for rate-limit
    bucketing only — auth failures still 401 at the dependency layer."""
    auth = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None


def _user_context(request: Request) -> tuple[Optional[str], Optional[str]]:
    """(user_id, tier) memoised on request.state across the slowapi callbacks."""
    cached = getattr(request.state, _CTX_ATTR, None)
    if cached is not None:
        return cached
    payload = _decode_token_silently(request)
    if payload is None:
        ctx: tuple[Optional[str], Optional[str]] = (None, None)
    else:
        ctx = (payload.get("sub"), payload.get("tier"))
    setattr(request.state, _CTX_ATTR, ctx)
    return ctx


def user_bucket_key(request: Request) -> str:
    """Bucket per authenticated (user, tier); fall back to IP for anonymous.

    The tier suffix is what makes the slowapi-side limit provider work
    without a Request — it can recover the tier from the key string alone.
    """
    user_id, tier = _user_context(request)
    if user_id:
        return f"user:{user_id}:{tier or 'anonymous'}"
    return f"ip:{get_remote_address(request)}"


def tier_aware_limit_for_key(key: str) -> str:
    """Return the per-minute limit string appropriate to the caller's tier.

    Called by slowapi with the bucket key string (not the Request). The
    key shape is fixed by ``user_bucket_key`` above, so we can split it
    safely. Unknown / anonymous / IP-keyed callers always get
    ``ANONYMOUS_RATE_LIMIT`` — the strictest cap.
    """
    if not key.startswith("user:"):
        return ANONYMOUS_RATE_LIMIT
    parts = key.split(":", 2)  # ["user", "<sub>", "<tier>"]
    if len(parts) != 3:
        return ANONYMOUS_RATE_LIMIT
    tier = parts[2]
    return TIER_RATE_LIMITS.get(tier, ANONYMOUS_RATE_LIMIT)


# The single limiter instance every router shares.
limiter = Limiter(key_func=user_bucket_key)
