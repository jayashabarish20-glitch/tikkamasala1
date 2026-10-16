"""
Shop Available / Unavailable state, persisted in the shop_status table.
"""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shop_status import ShopStatus

SHOP_UNAVAILABLE_MESSAGE = "Shop Unavailable. We are not accepting new orders right now."


async def get_shop_is_open(db: AsyncSession) -> bool:
    result = await db.execute(select(ShopStatus).where(ShopStatus.id == 1))
    row = result.scalars().first()
    return True if row is None else row.is_open


async def set_shop_is_open(db: AsyncSession, is_open: bool, admin_id: int) -> bool:
    result = await db.execute(select(ShopStatus).where(ShopStatus.id == 1))
    row = result.scalars().first()
    if row is None:
        row = ShopStatus(id=1)
        db.add(row)
    row.is_open = is_open
    row.updated_by_admin_id = admin_id
    await db.commit()
    return row.is_open


async def require_shop_open(db: AsyncSession) -> None:
    """Raise 503 when the shop is unavailable. Call before creating any order."""
    if not await get_shop_is_open(db):
        raise HTTPException(status_code=503, detail=SHOP_UNAVAILABLE_MESSAGE)
