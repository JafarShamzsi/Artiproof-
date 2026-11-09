"""Tests for the new settings endpoints.

These exercise the password / notifications / locale / deactivate / delete
routes via FastAPI's `dependency_overrides` so we don't need a live DB. The
goal is to pin contract behavior — wrong-password rejection, locale
validation, deletion confirmation phrase, and the export zip's structure —
not the SQL.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from passlib.hash import bcrypt

from app.constants import DEFAULT_NOTIFICATION_PREFERENCES
from app.database import get_db
from app.main import app
from app.utils.auth import get_current_user, get_current_user_allow_deactivated


def _user(*, password: str = "hunter22hunter", **overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        institution=None,
        role="researcher",
        tier="free",
        organization_id=None,
        locale="en",
        hashed_password=bcrypt.hash(password) if password else None,
        notification_preferences=None,
        analysis_preferences=None,
        watchlist=None,
        email_verified_at=None,
        deactivated_at=None,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class _StubDb:
    """Minimal AsyncSession stub. Tests that don't touch DB can use a bare
    AsyncMock; tests that must read other rows (export, delete) provide a
    `responses` queue keyed by table name."""

    def __init__(self, responses: dict | None = None):
        self.responses = responses or {}
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self._calls = 0

    async def execute(self, _q):  # noqa: ANN001
        # The auth router queries SourceCheck / ResearcherProfile / Report
        # for the export and delete paths in that fixed order. Returning an
        # empty result set covers the "fresh account" case which is what
        # these tests assert about.
        class _Result:
            def all(self):
                return []

            def scalars(self):
                class _S:
                    def all(self):
                        return []

                return _S()

            def scalar_one_or_none(self):
                return None

        return _Result()


@pytest.fixture
def override_user():
    """Helper that wires get_current_user / get_db, returning the stub user
    so a test can mutate it and see the changes reflected by the router."""
    holder: dict = {}

    def _apply(user):
        async def _db():
            yield _StubDb()

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_user_allow_deactivated] = lambda: user
        holder["user"] = user
        return user

    yield _apply
    app.dependency_overrides.clear()


# ─── Change password ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current(override_user):
    user = override_user(_user(password="oldpassword11"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/change-password",
            json={"current_password": "WRONG-password", "new_password": "newpass11"},
        )
    assert r.status_code == 401
    # Crucially, the hashed_password should NOT have been overwritten.
    assert bcrypt.verify("oldpassword11", user.hashed_password)


@pytest.mark.asyncio
async def test_change_password_rejects_when_same_as_current(override_user):
    override_user(_user(password="samepass1234"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/change-password",
            json={"current_password": "samepass1234", "new_password": "samepass1234"},
        )
    assert r.status_code == 400
    assert "differ" in r.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_requires_password_meeting_bcrypt_limit(override_user):
    override_user(_user(password="oldpassword11"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/change-password",
            json={
                "current_password": "oldpassword11",
                "new_password": "x" * 100,  # 100 bytes, > bcrypt's 72
            },
        )
    # Pydantic validation rejects before the route runs
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_change_password_blocks_google_only_account(override_user):
    override_user(_user(password=None))  # no hashed_password
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/change-password",
            json={"current_password": "anything-here", "new_password": "newpass11"},
        )
    assert r.status_code == 400
    assert "Google" in r.json()["detail"]


# ─── Notification preferences ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifications_default_when_unset(override_user):
    override_user(_user())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/auth/me/notifications")
    assert r.status_code == 200
    assert r.json() == DEFAULT_NOTIFICATION_PREFERENCES


@pytest.mark.asyncio
async def test_notifications_round_trip(override_user):
    user = override_user(_user())
    payload = {
        "email_on_completion": False,
        "email_on_low_credibility": True,
        "email_weekly_digest": True,
        "email_product_updates": False,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.put("/api/auth/me/notifications", json=payload)
    assert r.status_code == 200
    assert r.json() == payload
    assert user.notification_preferences == payload


# ─── Locale ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_locale_accepts_supported(override_user):
    # English is the only supported locale right now — `az` / `ru` were
    # de-scoped until next-intl ships. Test the round-trip with `en`.
    user = override_user(_user())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.put("/api/auth/me/locale", json={"locale": "en"})
    assert r.status_code == 200
    assert user.locale == "en"


@pytest.mark.asyncio
async def test_locale_rejects_unsupported(override_user):
    # `az` and `ru` were aspirational and have been removed from
    # SUPPORTED_LOCALES — they should now 400 alongside any other unknown code.
    override_user(_user())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for bad in ("fr", "az", "ru"):
            r = await c.put("/api/auth/me/locale", json={"locale": bad})
            assert r.status_code == 400, f"expected 400 for {bad!r}, got {r.status_code}"


# ─── Deactivate / delete ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deactivate_sets_timestamp(override_user):
    user = override_user(_user(password="hunter22hunter"))
    assert user.deactivated_at is None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/deactivate",
            json={"current_password": "hunter22hunter"},
        )
    assert r.status_code == 204
    assert user.deactivated_at is not None


@pytest.mark.asyncio
async def test_deactivate_rejects_wrong_password(override_user):
    user = override_user(_user(password="hunter22hunter"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/deactivate", json={"current_password": "WRONG-password"}
        )
    assert r.status_code == 401
    assert user.deactivated_at is None


@pytest.mark.asyncio
async def test_reactivate_clears_timestamp(override_user):
    user = override_user(_user(deactivated_at=datetime.now(timezone.utc)))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/auth/me/reactivate")
    assert r.status_code == 200
    assert user.deactivated_at is None


@pytest.mark.asyncio
async def test_delete_requires_correct_confirm_phrase(override_user):
    user = override_user(_user(password="hunter22hunter"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.request(
            "DELETE",
            "/api/auth/me",
            json={"current_password": "hunter22hunter", "confirm": "delete"},  # wrong case
        )
    assert r.status_code == 400
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_delete_sets_deleted_at(override_user):
    user = override_user(_user(password="hunter22hunter"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.request(
            "DELETE",
            "/api/auth/me",
            json={"current_password": "hunter22hunter", "confirm": "DELETE"},
        )
    assert r.status_code == 204
    assert user.deleted_at is not None


# ─── Data export ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_returns_zip_with_expected_files(override_user):
    user = override_user(_user())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/auth/me/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    buf = io.BytesIO(r.content)
    with zipfile.ZipFile(buf) as zf:
        names = set(zf.namelist())
        assert names == {
            "README.txt",
            "profile.json",
            "source_checks.json",
            "researcher_profiles.json",
            "reports.json",
            "sessions.json",
        }
        # Profile JSON contains the user's email — load it and assert.
        with zf.open("profile.json") as f:
            profile = json.loads(f.read())
        assert profile["email"] == user.email
        # The expanded export must include analysis preferences and the
        # watchlist so the GDPR portability contract is honoured.
        assert "analysis_preferences" in profile
        assert "watchlist" in profile
        assert "organization_id" in profile
        # source_checks.json is an empty array since the stub returns nothing.
        with zf.open("source_checks.json") as f:
            assert json.loads(f.read()) == []
        # sessions.json is likewise empty for a stub user with no logins.
        with zf.open("sessions.json") as f:
            assert json.loads(f.read()) == []
