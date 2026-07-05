"""
Auth routes — login, refresh, register.

POST /auth/login      → access + refresh tokens
POST /auth/refresh    → new access token from refresh token
POST /auth/register   → create a user + farm (onboarding)
POST /auth/logout     → (token invalidation handled client-side; server logs the event)
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    get_current_user,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.db import Farm, User
from app.models.schemas import RefreshRequest, TokenResponse, UserCreate, UserRead

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        log.warning("auth.login_failed", email=form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    access_token = create_access_token(user.id, user.farm_id, user.role)
    refresh_token = create_refresh_token(user.id, user.farm_id, user.role)

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    log.info("auth.login_success", user_id=user.id, farm_id=user.farm_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    access_token = create_access_token(payload["sub"], payload["farm_id"], payload["role"])
    new_refresh = create_refresh_token(payload["sub"], payload["farm_id"], payload["role"])
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserRead, status_code=201)
async def register(body: UserCreate, farm_name: str, db: AsyncSession = Depends(get_db)):
    """
    Create a new user + farm in one shot (onboarding flow).
    In production, farm creation would be a separate admin step.
    """
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    import uuid
    farm = Farm(id=str(uuid.uuid4()), name=farm_name, owner_user_id="")
    db.add(farm)
    await db.flush()

    user = User(
        farm_id=farm.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    farm.owner_user_id = user.id
    await db.flush()

    log.info("auth.registered", user_id=user.id, farm_id=farm.id)
    return user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Stateless logout — token invalidation is client-side (delete token).
    Server logs the event for the audit trail.
    """
    log.info("auth.logout", user_id=current_user.id)
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
