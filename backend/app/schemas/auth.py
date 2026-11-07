from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


UserRoleStr = Literal["researcher", "faculty", "admin"]


# bcrypt only hashes the first 72 bytes of UTF-8. Reject longer passwords
# explicitly instead of letting them silently collide with their first 72 bytes.
BCRYPT_MAX_BYTES = 72


def _validate_bcrypt_length(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes (UTF-8). "
            "Note: emoji and accented characters take multiple bytes."
        )
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    institution: Optional[str] = None
    role: UserRoleStr = "researcher"

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


class GoogleLogin(BaseModel):
    id_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    institution: Optional[str] = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[UserRoleStr] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
