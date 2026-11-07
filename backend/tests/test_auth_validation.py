"""Auth schema validation — bcrypt 72-byte limit + role downgrade contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import UserLogin, UserRegister, BCRYPT_MAX_BYTES


class TestBcryptLengthGuard:
    def test_short_password_accepted(self):
        u = UserRegister(
            email="a@example.com",
            password="hunter22hunter",
            full_name="Test",
        )
        assert u.password == "hunter22hunter"

    def test_password_exactly_at_limit_accepted(self):
        pw = "a" * BCRYPT_MAX_BYTES
        u = UserRegister(email="a@example.com", password=pw, full_name="T")
        assert len(u.password.encode("utf-8")) == BCRYPT_MAX_BYTES

    def test_password_one_byte_over_limit_rejected(self):
        pw = "a" * (BCRYPT_MAX_BYTES + 1)
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password=pw, full_name="T")

    def test_multibyte_chars_count_in_bytes_not_chars(self):
        # Each emoji is 4 bytes in UTF-8; 19 of them = 76 bytes > 72.
        pw = "🦄" * 19
        assert len(pw) == 19  # chars
        assert len(pw.encode("utf-8")) > BCRYPT_MAX_BYTES
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password=pw, full_name="T")

    def test_login_also_enforces_limit(self):
        with pytest.raises(ValidationError):
            UserLogin(email="a@example.com", password="x" * (BCRYPT_MAX_BYTES + 1))


class TestRolePublicSurface:
    """The frontend shouldn't be able to talk an admin role into existence —
    the public register form drops the option, but the backend Pydantic
    contract still accepts admin (because UserResponse needs it). The actual
    downgrade lives in the route handler; this test pins that the schema
    parses 'admin' so we know the route's `if data.role == "admin"` branch
    is reachable.
    """

    def test_admin_role_parses_at_schema_layer(self):
        u = UserRegister(
            email="a@example.com",
            password="hunter22hunter",
            full_name="T",
            role="admin",
        )
        assert u.role == "admin"

    def test_unknown_role_rejected(self):
        with pytest.raises(ValidationError):
            UserRegister(
                email="a@example.com",
                password="hunter22hunter",
                full_name="T",
                role="superuser",  # type: ignore[arg-type]
            )
