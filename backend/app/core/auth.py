"""
JWT-based auth helpers.

Token structure:
  {
    "sub": "<user_id>",
    "farm_id": "<farm_id>",          ← tenant scoping claim
    "role": "farmer|agronomist|admin",
    "type": "access|refresh",
    "exp": <unix timestamp>
  }

Every protected endpoint extracts the farm_id from the token so that
the DB query layer can enforce per-tenant data isolation without
relying on application-level filtering alone.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.db import User

log = structlog.get_logger(__name__)

import bcrypt

# Patch bcrypt to work with passlib
if not hasattr(bcrypt, "__about__"):
    class About:
        __version__ = bcrypt.__version__
    bcrypt.__about__ = About()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=not settings.DEMO_MODE)


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    farm_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "farm_id": farm_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str, farm_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "farm_id": farm_id,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Token verification ────────────────────────────────────────────────────────

def decode_token(token: str, expected_type: str = "access") -> dict:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            raise credentials_exc
        return payload
    except JWTError as exc:
        log.warning("auth.token_invalid", error=str(exc))
        raise credentials_exc


# ── FastAPI dependencies ───────────────────────────────────────────────────────

class TokenData:
    def __init__(self, user_id: str, farm_id: str, role: str):
        self.user_id = user_id
        self.farm_id = farm_id
        self.role = role


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if settings.DEMO_MODE and not token:
        return User(id="demo-user", farm_id="farm-001", role="farmer", is_active=True, email="demo@example.com")
    payload = decode_token(token)  # type: ignore
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return user


async def get_current_token_data(token: Optional[str] = Depends(oauth2_scheme)) -> TokenData:
    """Lightweight dependency — only decodes the JWT, no DB hit."""
    if settings.DEMO_MODE and not token:
        return TokenData(user_id="demo-user", farm_id="farm-001", role="farmer")
    payload = decode_token(token)  # type: ignore
    return TokenData(
        user_id=payload["sub"],
        farm_id=payload["farm_id"],
        role=payload["role"],
    )


def require_role(*roles: str):
    """Dependency factory for role-based access control."""
    async def _check(td: TokenData = Depends(get_current_token_data)) -> TokenData:
        if td.role not in roles:
            raise HTTPException(status_code=403, detail=f"Role '{td.role}' not authorised for this action")
        return td
    return _check
