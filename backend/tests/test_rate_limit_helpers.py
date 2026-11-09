"""Tier-aware rate limit helpers.

These are pure functions: ``user_bucket_key`` returns the bucket id
slowapi uses to count requests, and ``tier_aware_limit_for_key`` is
the limit-provider slowapi calls with that key string. The slowapi
integration (decorator + 429 response) is covered end-to-end in the
per-endpoint suites.

What we pin here:

- Authenticated requests bucket per ``user:<sub>:<tier>``.
- Unauthenticated requests bucket per ``ip:<addr>``.
- The same user on different tiers gets different buckets (so a tier
  upgrade resets the budget rather than letting the new tier inherit
  the old tier's cooldown).
- ``tier_aware_limit_for_key`` returns the right per-tier cap from the
  encoded key alone — no Request access needed.
- Missing/invalid tokens get the strictest anonymous cap.
- Memoisation: the second call within a request doesn't decode again.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from jose import jwt

from app.config import settings
from app.constants import ANONYMOUS_RATE_LIMIT, TIER_RATE_LIMITS
from app.utils.rate_limit import (
    _CTX_ATTR,
    tier_aware_limit_for_key,
    user_bucket_key,
)


def _mk_request(*, authorization: str | None, ip: str = "1.2.3.4"):
    headers: dict[str, str] = {}
    if authorization is not None:
        headers["authorization"] = authorization
    return SimpleNamespace(
        headers=headers,
        state=SimpleNamespace(),
        client=SimpleNamespace(host=ip),
    )


def _bearer(*, sub: str, tier: str | None = "free") -> str:
    payload: dict[str, object] = {"sub": sub, "email": f"{sub}@x"}
    if tier is not None:
        payload["tier"] = tier
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return f"Bearer {token}"


# ─── bucket-key shape ──────────────────────────────────────────────────────


def test_authenticated_buckets_encode_user_and_tier():
    req = _mk_request(authorization=_bearer(sub="u-123", tier="pro"))
    assert user_bucket_key(req) == "user:u-123:pro"


def test_authenticated_bucket_ignores_ip():
    a = _mk_request(authorization=_bearer(sub="u-1", tier="free"), ip="1.1.1.1")
    b = _mk_request(authorization=_bearer(sub="u-1", tier="free"), ip="2.2.2.2")
    assert user_bucket_key(a) == user_bucket_key(b)


def test_tier_change_yields_fresh_bucket():
    # Same user, different tier → different bucket. Upgrade/downgrade
    # resets the budget — defensible behaviour: a freshly-upgraded user
    # shouldn't inherit an exhausted free-tier cooldown.
    free = _mk_request(authorization=_bearer(sub="u-1", tier="free"))
    pro = _mk_request(authorization=_bearer(sub="u-1", tier="pro"))
    assert user_bucket_key(free) != user_bucket_key(pro)


def test_unauthenticated_falls_back_to_ip_bucket():
    req = _mk_request(authorization=None, ip="9.9.9.9")
    assert user_bucket_key(req) == "ip:9.9.9.9"


def test_malformed_authorization_header_falls_back_to_ip():
    req = _mk_request(authorization="Token abc", ip="9.9.9.9")  # not Bearer
    assert user_bucket_key(req) == "ip:9.9.9.9"


def test_invalid_jwt_falls_back_to_ip():
    req = _mk_request(authorization="Bearer not-a-real-jwt", ip="9.9.9.9")
    assert user_bucket_key(req) == "ip:9.9.9.9"


def test_token_without_tier_claim_marks_bucket_anonymous():
    # Tokens issued before the tier claim landed in create_access_token
    # have no tier field. We bucket them per-user but suffix
    # "anonymous" so the limit provider gives them the strictest cap.
    req = _mk_request(authorization=_bearer(sub="legacy-user", tier=None))
    assert user_bucket_key(req) == "user:legacy-user:anonymous"


# ─── limit provider ────────────────────────────────────────────────────────


@pytest.mark.parametrize("tier", list(TIER_RATE_LIMITS.keys()))
def test_tier_key_resolves_to_tier_limit(tier: str):
    key = f"user:u-123:{tier}"
    assert tier_aware_limit_for_key(key) == TIER_RATE_LIMITS[tier]


def test_unknown_tier_in_key_gets_anonymous_cap():
    # An attacker who somehow forges a token with tier="enterprise"
    # shouldn't bypass the strictest cap — they get anonymous.
    assert (
        tier_aware_limit_for_key("user:u-1:enterprise") == ANONYMOUS_RATE_LIMIT
    )


def test_ip_keyed_request_gets_anonymous_cap():
    assert tier_aware_limit_for_key("ip:1.2.3.4") == ANONYMOUS_RATE_LIMIT


def test_user_key_missing_tier_suffix_gets_anonymous_cap():
    # Malformed user key with no tier segment → safe default.
    assert tier_aware_limit_for_key("user:u-1") == ANONYMOUS_RATE_LIMIT


def test_legacy_token_bucket_resolves_to_anonymous_cap():
    # Round-trip: an old token with no tier claim gets the
    # "user:<sub>:anonymous" bucket, which then resolves to the
    # strictest cap via the limit provider.
    req = _mk_request(authorization=_bearer(sub="legacy", tier=None))
    key = user_bucket_key(req)
    assert tier_aware_limit_for_key(key) == ANONYMOUS_RATE_LIMIT


# ─── memoisation ───────────────────────────────────────────────────────────


def test_user_context_memoised_on_request_state():
    # The slowapi middleware calls key_func once per request; we still
    # cache the decoded context so callers (tests, future middleware)
    # that touch it twice don't re-parse the JWT.
    req = _mk_request(authorization=_bearer(sub="u-77", tier="pro"))
    assert getattr(req.state, _CTX_ATTR, None) is None
    user_bucket_key(req)
    assert getattr(req.state, _CTX_ATTR) == ("u-77", "pro")
    # Mutating the cached value proves subsequent calls trust the
    # cache instead of re-decoding.
    req.state._rate_limit_ctx = ("manual-override", "team")
    assert user_bucket_key(req) == "user:manual-override:team"
