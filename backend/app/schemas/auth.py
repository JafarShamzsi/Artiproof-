from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field


UserRoleStr = Literal["researcher", "faculty", "admin"]


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    institution: Optional[str] = None
    role: UserRoleStr = "researcher"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


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
