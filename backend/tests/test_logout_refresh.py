"""Tests for the new /logout and /refresh endpoints.

Reuses the in-memory fake session pattern from test_security_endpoints
(kept inline here to avoid making conftest depend on the helper)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from passlib.hash import bcrypt

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.session import Session
from app.utils.auth import get_current_user


def _user(**overrides):
    base = SimpleNamespace(
        id="user-x",
        email="x@example.com",
        full_name="X",
        institution=None,
        role="researcher",
        tier="free",
        locale="en",
        hashed_password=bcrypt.hash("hunter22hunter"),
        notification_preferences=None,
        deactivated_at=None,
        deleted_at=None,
        email_verified_at=None,
        totp_secret=None,
        totp_enabled=False,
        totp_backup_codes=None,
        linked_providers=None,
        analysis_preferences=None,
        organization_id=None,
        share_activity_with_team=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class _DbWithSession:
    def __init__(self, session: Session | None):
        self._session = session
        self.commit = AsyncMock()
        self.refresh = AsyncMock()

    async def get(self, model, pk):
        if model is Session and self._session and self._session.id == pk:
            return self._session
        return None

    def add(self, _obj):
        return None

    async def execute(self, _q):
        class _R:
            def scalars(self):
                class _S:
                    def all(self):
                        return []
                    def first(self):
                        return None
                return _S()
            def scalar_one_or_none(self):
                return None
        return _R()


@pytest.fixture
def env():
    """Wires get_current_user + get_db. The session has the same id we
    embed in the token's `jti` claim so the logout flow finds it."""
    user = _user()
    monkey_jwt_secret = "test-secret-not-for-production-but-32+"
    settings.JWT_SECRET = monkey_jwt_secret

    session_row = Session(
        id="sess-1",
        user_id=user.id,
        user_agent="pytest",
        ip_address="127.0.0.1",
        last_used_at=datetime.now(timezone.utc),
    )
    db = _DbWithSession(session_row)

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: user
    yield SimpleNamespace(db=db, user=user, session=session_row, jwt_secret=monkey_jwt_secret)
    app.dependency_overrides.clear()


def _bearer(jti: str | None, jwt_secret: str) -> dict[str, str]:
    payload: dict[str, object] = {
        "sub": "user-x",
        "email": "x@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if jti:
        payload["jti"] = jti
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_logout_revokes_matching_session(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/logout", headers=_bearer("sess-1", env.jwt_secret)
        )
    assert r.status_code == 204
    assert env.session.revoked_at is not None


@pytest.mark.asyncio
async def test_logout_idempotent_when_already_revoked(env):
    env.session.revoked_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    original = env.session.revoked_at
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/logout", headers=_bearer("sess-1", env.jwt_secret)
        )
    # Still 204 — the user doesn't see a difference, and we don't bump
    # revoked_at because the session already had a revocation timestamp.
    assert r.status_code == 204
    assert env.session.revoked_at == original


@pytest.mark.asyncio
async def test_logout_without_jti_succeeds_quietly(env):
    """Legacy tokens (pre-sessions) lack jti — logout returns 204 without
    touching any row."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/logout", headers=_bearer(None, env.jwt_secret)
        )
    assert r.status_code == 204
    assert env.session.revoked_at is None


@pytest.mark.asyncio
async def test_refresh_issues_new_token_with_same_jti(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/refresh", headers=_bearer("sess-1", env.jwt_secret)
        )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    decoded = jwt.decode(body["access_token"], env.jwt_secret, algorithms=["HS256"])
    assert decoded["sub"] == "user-x"
    assert decoded["jti"] == "sess-1"
    assert body["user"]["email"] == "x@example.com"
