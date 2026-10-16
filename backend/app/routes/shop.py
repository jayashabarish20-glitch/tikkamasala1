"""
Public shop status route. Customer pages use it to show Available / Unavailable.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.services.shop_status_service import get_shop_is_open, SHOP_UNAVAILABLE_MESSAGE

router = APIRouter(prefix="/api/shop", tags=["Shop"])


@router.get("/status")
async def get_shop_status(db: AsyncSession = Depends(get_db)):
    is_open = await get_shop_is_open(db)
    return {"is_open": is_open, "message": None if is_open else SHOP_UNAVAILABLE_MESSAGE}
