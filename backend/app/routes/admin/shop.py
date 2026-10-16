"""
Admin route to switch the shop between Available and Unavailable.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.routes.admin.deps import require_admin
from app.services.shop_status_service import set_shop_is_open

router = APIRouter(prefix="/api/admin", tags=["Admin Shop"])


class ShopStatusRequest(BaseModel):
    is_open: bool


@router.put("/shop/status")
async def admin_set_shop_status(req: ShopStatusRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Set Shop Available (is_open=true) or Shop Unavailable (is_open=false). Admin only."""
    payload = await require_admin(request)
    is_open = await set_shop_is_open(db, req.is_open, int(payload["sub"]))
    return {"is_open": is_open}
