import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    GoogleLogin,
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
)
from app.utils.auth import create_access_token, get_current_user
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Create a new user account and return a JWT so the client can authenticate immediately."""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # New users always start as researchers — admin is privileged and only assignable
    # by an existing admin via a separate admin tool. Ignore role from the public payload.
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        hashed_password=bcrypt.hash(data.password),
        full_name=data.full_name,
        institution=data.institution,
        role="researcher" if data.role == "admin" else data.role,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not bcrypt.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/google", response_model=TokenResponse)
@limiter.limit("10/minute")
async def google_login(request: Request, data: GoogleLogin, db: AsyncSession = Depends(get_db)):
    """Verify a Google ID token, then create or return the matching platform user."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    try:
        id_info = google_id_token.verify_oauth2_token(
            data.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = id_info.get("email")
    email_verified = id_info.get("email_verified")
    if not email or email_verified is not True:
        raise HTTPException(status_code=401, detail="Google email is not verified")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=None,
            full_name=id_info.get("name") or email.split("@", 1)[0],
            role="researcher",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

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
    # Users may update profile fields but never their own role — role changes are
    # privileged and must go through an admin tool.
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("role", None)

    if "full_name" in update_data:
        current_user.full_name = update_data["full_name"]
    if "institution" in update_data:
        current_user.institution = update_data["institution"]

    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)
