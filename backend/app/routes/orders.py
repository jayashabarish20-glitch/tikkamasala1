"""
Order creation and retrieval routes.
Full 12-step order process with Haversine 3km validation.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

from app.config.database import get_db
from app.config.settings import settings
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.user import User
from app.schemas.order import CreateOrderRequest
from app.utils.jwt import decode_token
from app.utils.location import haversine_distance
from app.utils.otp import generate_otp
from app.services.websocket_manager import ws_manager
from app.services.sms_service import send_delivery_otp_sms
import random
import string

router = APIRouter(prefix="/api/orders", tags=["Orders"])


async def get_current_user_id(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    payload = decode_token(auth.split(" ")[1])
    if payload.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer access required.")
    return int(payload["sub"])


async def generate_order_number(db: AsyncSession) -> str:
    today = date.today()
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day = today.strftime("%d")

    from sqlalchemy import cast, Date
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(func.count(Order.id)).where(
            (Order.created_at >= today_start) & (Order.created_at <= today_end)
        )
    )
    count = result.scalar() or 0
    sequence = str(count).zfill(4)
    return f"TM{year}{month}{day}{sequence}"


@router.post("")
async def create_order(req: CreateOrderRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Full order creation with all validations. For OFFLINE/COD only. ONLINE orders created after payment."""
    user_id = await get_current_user_id(request)

    if req.payment_method == "ONLINE":
        raise HTTPException(status_code=400, detail="For ONLINE payments, use /api/payments/create-order endpoint.")

    # Step 1: Get cart
    cart_result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = cart_result.scalars().first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    # Step 2: Get cart items
    items_result = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    cart_items = items_result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    # Step 3-4: Validate products + fetch real prices
    subtotal = Decimal("0.00")
    order_items_data = []
    locked_products = []
    for item in cart_items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id).with_for_update())
        product = prod_result.scalars().first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found.")
        if not product.is_available or product.stock_quantity <= 0:
            raise HTTPException(status_code=400, detail=f"'{product.name}' is currently out of stock.")
        if item.quantity > product.stock_quantity:
            raise HTTPException(status_code=400, detail=f"Only {product.stock_quantity} '{product.name}' available; requested {item.quantity}.")
        product.stock_quantity -= item.quantity
        product.is_available = product.stock_quantity > 0
        inventory_result = await db.execute(select(Inventory).where(Inventory.product_id == product.id))
        inventory = inventory_result.scalars().first()
        if inventory:
            inventory.current_stock = product.stock_quantity
        locked_products.append(product)
        item_subtotal = product.price * item.quantity
        subtotal += Decimal(str(item_subtotal))
        order_items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": item.quantity,
            "unit_price": Decimal(str(product.price)),
            "subtotal": Decimal(str(item_subtotal)),
        })

    # Step 5: Delivery validation
    delivery_fee = Decimal("0.00")
    if req.order_type == "DELIVERY":
        if not req.delivery_address or req.delivery_lat is None or req.delivery_lng is None:
            raise HTTPException(status_code=400, detail="Delivery address and location are required.")

        distance = haversine_distance(
            settings.SHOP_LATITUDE, settings.SHOP_LONGITUDE,
            req.delivery_lat, req.delivery_lng
        )
        if distance > settings.DELIVERY_RADIUS_KM:
            raise HTTPException(
                status_code=400,
                detail=f"Sorry, delivery is available only within {settings.DELIVERY_RADIUS_KM} km of Tikka Masala Chat Corner. Your location is {distance:.1f} km away."
            )
        delivery_fee = Decimal(str(settings.DELIVERY_CHARGE))

    discount = Decimal("0.00")
    total = subtotal + delivery_fee - discount

    # Step 6: Create order
    order_number = await generate_order_number(db)

    order = Order(
        order_number=order_number,
        user_id=user_id,
        order_type=req.order_type,
        delivery_address=req.delivery_address,
        delivery_house_flat_door=req.delivery_house_flat_door,
        delivery_street_area=req.delivery_street_area,
        delivery_city=req.delivery_city,
        delivery_state=req.delivery_state,
        delivery_pincode=req.delivery_pincode,
        delivery_landmark=req.delivery_landmark,
        delivery_lat=Decimal(str(req.delivery_lat)) if req.delivery_lat else None,
        delivery_lng=Decimal(str(req.delivery_lng)) if req.delivery_lng else None,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=discount,
        total=total,
        status="PENDING",
        payment_method=req.payment_method,
        payment_status="PENDING",
        payment_mode="OFFLINE",
        notes=req.notes,
    )
    db.add(order)
    await db.flush()

    # Step 7: Create order items
    for oi in order_items_data:
        db.add(OrderItem(
            order_id=order.id,
            product_id=oi["product_id"],
            product_name=oi["product_name"],
            quantity=oi["quantity"],
            unit_price=oi["unit_price"],
            subtotal=oi["subtotal"],
        ))

    # Step 8: Status history
    db.add(OrderStatusHistory(order_id=order.id, status="PENDING", changed_by="system"))

    await db.commit()
    for product in locked_products:
        await ws_manager.broadcast_inventory({"type": "stock_update", "product_id": product.id, "stock_quantity": product.stock_quantity, "is_available": product.is_available})
    await db.refresh(order)

    # Step 8.5: Generate and send demo OTP for COD
    otp = generate_otp(6)
    order.delivery_otp = otp
    order.otp_expires_at = datetime.utcnow() + timedelta(hours=12)
    order.otp_attempts = 0
    db.add(order)
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    if user:
        await send_delivery_otp_sms(user.mobile, otp)

    # Step 9: Clear cart
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    # Step 10: Notify admins via WebSocket
    await ws_manager.broadcast_to_admins({
        "event": "NEW_ORDER",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "user_id": user_id,
            "total": float(order.total),
            "status": order.status,
            "order_type": order.order_type,
            "items": order_items_data and [
                {"name": oi["product_name"], "quantity": oi["quantity"]} for oi in order_items_data
            ],
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
    })

    return {
        "message": "Order created successfully.",
        "order_id": order.id,
        "order_number": order.order_number,
        "total": float(order.total),
        "status": order.status,
    }


@router.get("")
async def get_my_orders(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(request)
    result = await db.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()))
    orders = result.scalars().all()
    out = []
    for o in orders:
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
            "order_type": o.order_type,
            "total": float(o.total),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "placed_time": placed_time,
        })
    return out


@router.get("/{order_id}")
async def get_order(order_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(request)
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == user_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()
    items_data = []
    for item in items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        prod = prod_result.scalars().first()
        items_data.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": prod.name if prod else "Unknown",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal),
        })

    # Status history
    hist_result = await db.execute(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.created_at)
    )
    history = [{"status": h.status, "created_at": h.created_at.isoformat()} for h in hist_result.scalars().all()]

    # Payment info
    pay_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    payment = pay_result.scalars().first()

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
        "order_type": order.order_type,
        "delivery_address": order.delivery_address,
        "subtotal": float(order.subtotal),
        "delivery_fee": float(order.delivery_fee),
        "discount": float(order.discount),
        "total": float(order.total),
        "status": order.status,
        "items": items_data,
        "history": history,
        "payment_method": order.payment_method,
        "payment_status": payment.status if payment else "PENDING",
        "razorpay_order_id": payment.razorpay_order_id if payment else None,
        "delivery_otp": order.delivery_otp,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "placed_time": placed_time,
    }
