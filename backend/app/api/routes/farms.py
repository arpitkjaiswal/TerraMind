"""
Farm routes — scoped to the authenticated user's farm_id from the JWT.

GET  /api/v1/farms/me          → current farm details
PUT  /api/v1/farms/me          → update farm name
GET  /api/v1/farms/me/users    → list users in farm
POST /api/v1/farms/me/users    → invite / create user
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_token_data, TokenData, require_role
from app.core.database import get_db
from app.models.db import Farm, User
from app.models.schemas import FarmCreate, FarmRead, UserCreate, UserRead
from app.core.auth import hash_password

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/me", response_model=FarmRead)
async def get_my_farm(
    td: TokenData = Depends(get_current_token_data),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Farm).where(Farm.id == td.farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.put("/me", response_model=FarmRead)
async def update_farm(
    body: FarmCreate,
    td: TokenData = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Farm).where(Farm.id == td.farm_id))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    farm.name = body.name
    await db.flush()
    return farm


@router.get("/me/users", response_model=list[UserRead])
async def list_farm_users(
    td: TokenData = Depends(require_role("admin", "agronomist")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.farm_id == td.farm_id))
    return result.scalars().all()


@router.post("/me/users", response_model=UserRead, status_code=201)
async def add_farm_user(
    body: UserCreate,
    td: TokenData = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        farm_id=td.farm_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    log.info("farm.user_added", farm_id=td.farm_id, new_user_id=user.id, role=user.role)
    return user
