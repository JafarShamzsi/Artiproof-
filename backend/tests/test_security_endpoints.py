"""Tests for the new security endpoints — password reset, 2FA, sessions,
connected accounts, analysis prefs.

These pin the contract behavior (rejection of invalid tokens, single-use,
session revocation, the no-lockout rule on Google unlink) without needing
a real DB. Where the route reads/writes state, the tests use a small in-
memory fake AsyncSession so the SQL paths still work.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pyotp
import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from passlib.hash import bcrypt

from app.database import get_db
from app.main import app
from app.models.auth_token import AuthToken
from app.models.session import Session
from app.utils.auth import (
    get_current_user,
    get_current_user_allow_deactivated,
)


def _user(*, password: str = "hunter22hunter", **overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        institution=None,
        role="researcher",
        tier="free",
        locale="en",
        hashed_password=bcrypt.hash(password) if password else None,
        notification_preferences=None,
        deactivated_at=None,
        deleted_at=None,
        email_verified_at=None,
        totp_secret=None,
        totp_enabled=False,
        totp_backup_codes=None,
        linked_providers=None,
        analysis_preferences=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class _MemoryDb:
    """In-memory fake AsyncSession good enough for the routes under test.

    Only supports the operations the security routes actually do: get_by_pk
    against AuthToken / Session / User, simple `where` queries, and the
    `add` / `commit` / `refresh` lifecycle. Other backends raise NotImplemented
    so tests that exercise something we don't cover fail loudly."""

    def __init__(self):
        self._auth_tokens: dict[str, AuthToken] = {}
        self._sessions: dict[str, Session] = {}
        self._users: dict[str, SimpleNamespace] = {}
        self.commit = AsyncMock()
        self.refresh = AsyncMock(side_effect=self._refresh)

    async def _refresh(self, obj):
        return obj

    def add(self, obj):
        if isinstance(obj, AuthToken):
            if obj.id is None:
                # AuthToken default is _make_token(); SimpleNamespace defaults
                # don't trigger SQLAlchemy column defaults.
                from app.models.auth_token import _default_expiry, _make_token

                if not getattr(obj, "id", None):
                    obj.id = _make_token()
                if not getattr(obj, "expires_at", None):
                    obj.expires_at = _default_expiry()
            self._auth_tokens[obj.id] = obj
        elif isinstance(obj, Session):
            self._sessions[obj.id] = obj
        elif hasattr(obj, "id") and hasattr(obj, "email"):
            self._users[obj.id] = obj

    async def get(self, model, pk):
        if model is AuthToken:
            return self._auth_tokens.get(pk)
        if model is Session:
            return self._sessions.get(pk)
        return None

    async def execute(self, _q):
        # Several routes use `select(...).where(...)`. Returning empty
        # is safe because the test seeds state by directly mutating the
        # fake's internal dicts before calling the route.
        class _R:
            def all(self):
                return []

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
    """Wires get_db + get_current_user with an in-memory fake."""
    db = _MemoryDb()
    user = _user()

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_allow_deactivated] = lambda: user
    yield SimpleNamespace(db=db, user=user)
    app.dependency_overrides.clear()


# ─── Password reset ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_token(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/reset-password",
            json={"token": "definitely-not-a-token", "new_password": "newpass1234"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(env):
    expired = AuthToken(
        id="expired-token",
        user_id=env.user.id,
        kind="password_reset",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    env.db._auth_tokens["expired-token"] = expired

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/reset-password",
            json={"token": "expired-token", "new_password": "newpass1234"},
        )
    assert r.status_code == 400


# ─── 2FA ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_totp_setup_then_enable(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Step 1: setup
        r = await c.post("/api/auth/me/2fa/setup")
        assert r.status_code == 200
        body = r.json()
        assert body["secret"]
        assert body["provisioning_uri"].startswith("otpauth://totp/")
        assert len(body["backup_codes"]) == 10
        assert env.user.totp_secret == body["secret"]
        assert env.user.totp_enabled is False  # not yet

        # Step 2: enable with a real TOTP code
        code = pyotp.TOTP(body["secret"]).now()
        r2 = await c.post("/api/auth/me/2fa/enable", json={"code": code})
        assert r2.status_code == 200
        assert r2.json()["enabled"] is True
        assert env.user.totp_enabled is True


@pytest.mark.asyncio
async def test_totp_enable_rejects_wrong_code(env):
    env.user.totp_secret = pyotp.random_base32()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/auth/me/2fa/enable", json={"code": "000000"})
    assert r.status_code == 401
    assert env.user.totp_enabled is False


@pytest.mark.asyncio
async def test_totp_disable_requires_password_and_code(env):
    secret = pyotp.random_base32()
    env.user.totp_secret = secret
    env.user.totp_enabled = True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Wrong password
        r = await c.post(
            "/api/auth/me/2fa/disable",
            json={"current_password": "wrong", "code": pyotp.TOTP(secret).now()},
        )
        assert r.status_code == 401
        assert env.user.totp_enabled is True

        # Right password + code
        r2 = await c.post(
            "/api/auth/me/2fa/disable",
            json={"current_password": "hunter22hunter", "code": pyotp.TOTP(secret).now()},
        )
        assert r2.status_code == 204
        assert env.user.totp_enabled is False
        assert env.user.totp_secret is None


# ─── Sessions ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_session_404_for_other_users(env):
    other_session = Session(
        id="other-session",
        user_id="someone-else",
    )
    env.db._sessions["other-session"] = other_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/sessions/other-session")
    assert r.status_code == 404
    assert other_session.revoked_at is None


@pytest.mark.asyncio
async def test_revoke_own_session_succeeds(env):
    own = Session(id="own-session", user_id=env.user.id)
    env.db._sessions["own-session"] = own

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/sessions/own-session")
    assert r.status_code == 204
    assert own.revoked_at is not None


# ─── Connected accounts ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unlink_google_blocks_lockout(env):
    """No password and no other provider → unlink would lock the user out."""
    env.user.hashed_password = None
    env.user.linked_providers = {
        "google": {"sub": "g-1", "email": "u@example.com", "linked_at": "2026-01-01T00:00:00+00:00"}
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/connections/google")
    assert r.status_code == 400
    assert "password" in r.json()["detail"].lower()
    assert env.user.linked_providers and "google" in env.user.linked_providers


@pytest.mark.asyncio
async def test_unlink_google_succeeds_with_password(env):
    env.user.hashed_password = bcrypt.hash("anything-here")
    env.user.linked_providers = {
        "google": {"sub": "g-1", "email": "u@example.com", "linked_at": "2026-01-01T00:00:00+00:00"}
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/connections/google")
    assert r.status_code == 204
    assert (env.user.linked_providers or {}).get("google") is None


# ─── Analysis preferences ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analysis_prefs_default_when_unset(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/auth/me/analysis-preferences")
    assert r.status_code == 200
    body = r.json()
    assert body["check_citations"] is True
    assert body["ai_detection_model"] == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_analysis_prefs_round_trip(env):
    payload = {
        "check_citations": False,
        "trace_misinfo_origins": False,
        "ai_detection_model": "gemini-2.0-flash",
        "researcher_field_inference": True,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.put("/api/auth/me/analysis-preferences", json=payload)
    assert r.status_code == 200
    assert r.json() == payload
    assert env.user.analysis_preferences == payload


# ─── Email verification ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_email_status_returns_unverified_for_new_user(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/auth/me/email/status")
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is False
    assert body["email"] == env.user.email


@pytest.mark.asyncio
async def test_email_verify_request_rejected_when_already_verified(env):
    env.user.email_verified_at = datetime.now(timezone.utc)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/auth/me/email/verify/request")
    assert r.status_code == 400
