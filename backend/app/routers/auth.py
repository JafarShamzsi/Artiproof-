from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import UserRegister, UserLogin, UserResponse, UserUpdate, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    # TODO: Phase 2 — implement registration with password hashing
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT token."""
    # TODO: Phase 2 — implement JWT authentication
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/me", response_model=UserResponse)
async def get_current_user(db: AsyncSession = Depends(get_db)):
    """Get current user profile."""
    # TODO: Phase 2 — implement with JWT dependency
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/me", response_model=UserResponse)
async def update_profile(data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """Update current user profile."""
    # TODO: Phase 2 — implement profile update
    raise HTTPException(status_code=501, detail="Not implemented yet")
