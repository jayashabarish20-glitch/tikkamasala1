"""
Admin order management routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import timezone, timedelta, datetime

from app.config.database import get_db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.routes.admin.deps import require_admin
from app.services.websocket_manager import ws_manager
from app.config.settings import settings
from app.utils.location import haversine_distance
from app.schemas.order import VerifyDeliveryOtpRequest
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["Admin"])

VALID_TRANSITIONS = {
    "PENDING": ["PAYMENT_VERIFIED", "CANCELLED", "DELIVERED", "PICKED_UP"],
    "PAYMENT_VERIFIED": ["PREPARING", "CANCELLED"],
    "PREPARING": ["READY", "READY_FOR_PICKUP"],
    "READY": ["OUT_FOR_DELIVERY"],
    "READY_FOR_PICKUP": ["PICKED_UP"],
    "OUT_FOR_DELIVERY": ["DELIVERED"],
}


class UpdateStatusRequest(BaseModel):
    status: str
    note: Optional[str] = None


@router.get("/orders")
async def list_orders(request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin(request)
    result = await db.execute(select(Order).order_by(Order.created_at.desc()))
    orders = result.scalars().all()

    out = []
    for o in orders:
        user_result = await db.execute(select(User).where(User.id == o.user_id))
        user = user_result.scalars().first()
        pay_result = await db.execute(select(Payment).where(Payment.order_id == o.id))
        payment = pay_result.scalars().first()
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == o.id))
        items = items_result.scalars().all()
        items_data = []
        for item in items:
            prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
            prod = prod_result.scalars().first()
            items_data.append({
                "product_name": prod.name if prod else "Unknown",
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
            })
        # Generate Google Maps link if coordinates available
        google_maps_link = None
        if o.delivery_lat is not None and o.delivery_lng is not None:
            google_maps_link = f"https://www.google.com/maps?q={float(o.delivery_lat)},{float(o.delivery_lng)}"

        # Map backend status to simple PENDING/COMPLETED for admin display
        display_status = "COMPLETED" if o.status in ("DELIVERED", "PICKED_UP") else "PENDING"

        # Payment method: ensure it's always COD or ONLINE (never payment_status)
        if o.payment_method in ("COD", "ONLINE"):
            payment_display = o.payment_method
        else:
            payment_display = "COD"  # Safe default for any unexpected values

        # Convert created_at to IST and format as HH:MM:SS
        placed_time = "—"
        if o.created_at:
            try:
                # Handle both naive and timezone-aware datetimes
                if o.created_at.tzinfo is None:
                    # Naive datetime - assume it's UTC
                    utc_dt = o.created_at.replace(tzinfo=timezone.utc)
                else:
                    # Already timezone-aware - convert to UTC first if needed
                    utc_dt = o.created_at.astimezone(timezone.utc)

                # Convert UTC to IST
                ist = timezone(timedelta(hours=5, minutes=30))
                ist_time = utc_dt.astimezone(ist)
                placed_time = ist_time.strftime("%H:%M:%S")
            except:
                placed_time = "—"

        out.append({
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": user.name if user else "Unknown",
            "customer_mobile": user.mobile if user else "",
            "order_type": o.order_type,
            "delivery_address": o.delivery_address,
            "delivery_pincode": o.delivery_pincode,
            "delivery_landmark": o.delivery_landmark,
            "google_maps_link": google_maps_link,
            "subtotal": float(o.subtotal),
            "delivery_fee": float(o.delivery_fee),
            "total": float(o.total),
            "status": display_status,
            "backend_status": o.status,
            "payment": payment_display,
            "payment_method": o.payment_method,
            "payment_mode": o.payment_mode or "OFFLINE",
            "payment_status": payment.status if payment else o.payment_status,
            "items": items_data,
            "placed_time": placed_time,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return out


@router.get("/orders/{order_id}")
async def get_order(order_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin(request)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalars().first()

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()
    items_data = []
    for item in items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        prod = prod_result.scalars().first()
        items_data.append({
            "product_name": prod.name if prod else "Unknown",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal),
        })

    hist_result = await db.execute(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.created_at)
    )
    history = [{"status": h.status, "created_at": h.created_at.isoformat()} for h in hist_result.scalars().all()]

    pay_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    payment = pay_result.scalars().first()

    distance_km = None
    if order.delivery_lat is not None and order.delivery_lng is not None:
        distance_km = round(haversine_distance(
            settings.SHOP_LATITUDE, settings.SHOP_LONGITUDE,
            float(order.delivery_lat), float(order.delivery_lng),
        ), 2)

    # Generate Google Maps link if coordinates available
    google_maps_link = None
    if order.delivery_lat is not None and order.delivery_lng is not None:
        google_maps_link = f"https://www.google.com/maps?q={float(order.delivery_lat)},{float(order.delivery_lng)}"

    # Map backend status to simple PENDING/COMPLETED for admin display
    display_status = "COMPLETED" if order.status in ("DELIVERED", "PICKED_UP") else "PENDING"

    # Payment method: ensure it's always COD or ONLINE (never payment_status)
    if order.payment_method in ("COD", "ONLINE"):
        payment_display = order.payment_method
    else:
        payment_display = "COD"  # Safe default for any unexpected values

    # Convert created_at to IST and format as HH:MM:SS
    placed_time = "—"
    if order.created_at:
        try:
            # Handle both naive and timezone-aware datetimes
            if order.created_at.tzinfo is None:
                # Naive datetime - assume it's UTC
                utc_dt = order.created_at.replace(tzinfo=timezone.utc)
            else:
                # Already timezone-aware - convert to UTC first if needed
                utc_dt = order.created_at.astimezone(timezone.utc)

            # Convert UTC to IST
            ist = timezone(timedelta(hours=5, minutes=30))
            ist_time = utc_dt.astimezone(ist)
            placed_time = ist_time.strftime("%H:%M:%S")
        except:
            placed_time = "—"

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": user.name if user else "Unknown",
        "customer_mobile": user.mobile if user else "",
        "order_type": order.order_type,
        "delivery_address": order.delivery_address,
        "delivery_house_flat_door": order.delivery_house_flat_door,
        "delivery_street_area": order.delivery_street_area,
        "delivery_city": order.delivery_city,
        "delivery_state": order.delivery_state,
        "delivery_pincode": order.delivery_pincode,
        "delivery_landmark": order.delivery_landmark,
        "delivery_lat": float(order.delivery_lat) if order.delivery_lat else None,
        "delivery_lng": float(order.delivery_lng) if order.delivery_lng else None,
        "google_maps_link": google_maps_link,
        "distance_km": distance_km,
        "delivery_eligible": (distance_km is not None and distance_km <= settings.DELIVERY_RADIUS_KM) if distance_km is not None else None,
        "subtotal": float(order.subtotal),
        "delivery_fee": float(order.delivery_fee),
        "discount": float(order.discount),
        "total": float(order.total),
        "status": display_status,
        "backend_status": order.status,
        "payment": payment_display,
        "payment_method": order.payment_method,
        "payment_mode": order.payment_mode or "OFFLINE",
        "payment_status": payment.status if payment else order.payment_status,
        "items": items_data,
        "history": history,
        "notes": order.notes,
        "placed_time": placed_time,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "delivery_otp": order.delivery_otp,  # Admin sees OTP for delivery verification
    }


@router.patch("/orders/{order_id}/status")
async def update_order_status(order_id: int, req: UpdateStatusRequest, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await require_admin(request)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    allowed = VALID_TRANSITIONS.get(order.status, [])
    if req.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {order.status} to {req.status}. Allowed: {allowed}"
        )

    order.status = req.status
    db.add(OrderStatusHistory(
        order_id=order.id,
        status=req.status,
        changed_by="admin",
        changed_by_id=int(payload.get("sub", 0)),
        note=req.note,
    ))
    await db.commit()

    # Real-time: notify customer
    status_messages = {
        "PREPARING": "Your order is being prepared. 🍽️",
        "READY": "Your order is ready!",
        "READY_FOR_PICKUP": "Your order is ready for pickup!",
        "OUT_FOR_DELIVERY": "Your order is out for delivery! 🛵",
        "PICKED_UP": "Order picked up. Thank you!",
        "CANCELLED": "Your order has been cancelled.",
    }
    await ws_manager.send_to_customer(order.user_id, {
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": req.status,
        "message": status_messages.get(req.status, f"Order status: {req.status}"),
    })
    await ws_manager.broadcast_to_admins({
        "event": "ORDER_UPDATED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": req.status,
    })

    return {"message": f"Order status updated to {req.status}.", "order_id": order.id, "status": req.status}


@router.post("/orders/{order_id}/verify-otp")
async def verify_delivery_otp(order_id: int, req: VerifyDeliveryOtpRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin(request)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status in ("DELIVERED", "PICKED_UP", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot verify OTP for order with status {order.status}.")

    if not order.delivery_otp:
        raise HTTPException(status_code=400, detail="No OTP associated with this order.")

    if order.otp_expires_at and datetime.utcnow() > order.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired.")

    if order.delivery_otp != req.otp:
        order.otp_attempts = (order.otp_attempts or 0) + 1
        db.add(order)
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    new_status = "DELIVERED" if order.order_type == "DELIVERY" else "PICKED_UP"
    order.status = new_status
    order.otp_attempts = 0
    if order.payment_method == "COD":
        order.payment_status = "PAID"
    db.add(OrderStatusHistory(order_id=order.id, status=new_status, changed_by="admin"))
    await db.commit()

    await ws_manager.send_to_customer(order.user_id, {
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": new_status,
        "message": "Order delivery confirmed! Thank you for your purchase.",
    })
    await ws_manager.broadcast_to_admins({
        "event": "ORDER_UPDATED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": new_status,
    })

    return {
        "message": f"OTP verified. Order status updated to {new_status}.",
        "order_id": order.id,
        "status": new_status,
    }
