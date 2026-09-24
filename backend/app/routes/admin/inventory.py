"""
Admin inventory management route.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel

from app.config.database import get_db
from app.models.inventory import Inventory
from app.models.product import Product
from app.routes.admin.deps import require_admin
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class UpdateInventoryRequest(BaseModel):
    current_stock: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_available: Optional[bool] = None


@router.get("/inventory")
async def get_inventory(request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin(request)
    result = await db.execute(select(Product).order_by(Product.name))
    products = result.scalars().all()
    out = []
    for product in products:
        inventory_result = await db.execute(select(Inventory).where(Inventory.product_id == product.id))
        inv = inventory_result.scalars().first()
        out.append({
            "id": inv.id if inv else None,
            "product_id": product.id,
            "product_name": product.name,
            "current_stock": product.stock_quantity,
            "low_stock_threshold": inv.low_stock_threshold if inv else 10,
            "is_low_stock": product.stock_quantity <= (inv.low_stock_threshold if inv else 10),
            "is_available": bool(product.is_available and product.stock_quantity > 0),
        })
    return out


@router.patch("/inventory/product/{product_id}")
async def update_inventory(product_id: int, req: UpdateInventoryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin(request)
    if req.current_stock is not None and req.current_stock < 0:
        raise HTTPException(status_code=422, detail="Stock quantity cannot be negative.")
    if req.low_stock_threshold is not None and req.low_stock_threshold < 0:
        raise HTTPException(status_code=422, detail="Low stock threshold cannot be negative.")
    product_result = await db.execute(select(Product).where(Product.id == product_id).with_for_update())
    product = product_result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    result = await db.execute(select(Inventory).where(Inventory.product_id == product_id))
    inv = result.scalars().first()
    if not inv:
        inv = Inventory(product_id=product_id, current_stock=product.stock_quantity)
        db.add(inv)
    if req.current_stock is not None:
        inv.current_stock = req.current_stock
        product.stock_quantity = req.current_stock
    if req.low_stock_threshold is not None:
        inv.low_stock_threshold = req.low_stock_threshold
    if req.is_available is not None and product.stock_quantity > 0:
        product.is_available = req.is_available
    if product.stock_quantity <= 0:
        product.is_available = False
    elif req.current_stock is not None:
        product.is_available = True
    await db.commit()
    await ws_manager.broadcast_inventory({"type": "stock_update", "product_id": product.id, "stock_quantity": product.stock_quantity, "is_available": product.is_available})
    return {"message": "Inventory updated.", "product_id": product.id, "stock_quantity": product.stock_quantity, "is_available": product.is_available}


@router.patch("/inventory/{inv_id:int}")
async def update_inventory_legacy(inv_id: int, req: UpdateInventoryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Keep the original inventory-id endpoint working for existing clients."""
    result = await db.execute(select(Inventory).where(Inventory.id == inv_id))
    inventory = result.scalars().first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return await update_inventory(inventory.product_id, req, request, db)
