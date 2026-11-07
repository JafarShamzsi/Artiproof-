import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
)
from app.utils.auth import create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Create a new user account and return a JWT so the client can authenticate immediately."""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        hashed_password=bcrypt.hash(data.password),
        full_name=data.full_name,
        institution=data.institution,
        role=data.role,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not bcrypt.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_to_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.institution is not None:
        current_user.institution = data.institution
    if data.role is not None:
        current_user.role = data.role

    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)
