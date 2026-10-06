"""
Razorpay payment routes with server-side signature verification.
In DEMO_MODE=true, skips real Razorpay calls for local testing.
For ONLINE payments, order is created AFTER payment verification.
"""
import hmac
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from datetime import datetime, timedelta, date
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional, List

from app.config.database import get_db
from app.config.settings import settings
from app.models.order import Order
from app.models.payment import Payment
from app.models.order_status_history import OrderStatusHistory
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.order_item import OrderItem
from app.models.user import User
from app.schemas.payment import CreatePaymentRequest, VerifyPaymentRequest, VerifyOnlinePaymentRequest
from app.utils.jwt import decode_token
from app.utils.location import haversine_distance
from app.services.websocket_manager import ws_manager
from app.services.sms_service import send_delivery_otp_sms
from app.utils.otp import generate_otp

router = APIRouter(prefix="/api/payments", tags=["Payments"])


class CreateOnlineOrderRequest(BaseModel):
    order_type: str = "DELIVERY"
    delivery_address: Optional[str] = None
    delivery_house_flat_door: Optional[str] = None
    delivery_street_area: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_state: Optional[str] = None
    delivery_pincode: Optional[str] = None
    delivery_landmark: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None
    notes: Optional[str] = None


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

    today_prefix = f"TM{year}{month}{day}"

    result = await db.execute(
        select(Order.order_number).where(
            Order.order_number.like(f"{today_prefix}%")
        )
    )
    order_numbers = result.scalars().all()

    max_sequence = -1
    for order_num in order_numbers:
        if order_num.startswith(today_prefix):
            try:
                sequence_str = order_num[len(today_prefix):]
                sequence = int(sequence_str)
                max_sequence = max(max_sequence, sequence)
            except (ValueError, IndexError):
                pass

    next_sequence = max_sequence + 1
    sequence = str(next_sequence).zfill(4)
    return f"{today_prefix}{sequence}"


@router.post("/create")
async def create_payment(req: CreatePaymentRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Create payment order for existing OFFLINE order. For ONLINE orders, use /create-order instead."""
    user_id = await get_current_user_id(request)

    order_result = await db.execute(select(Order).where(Order.id == req.order_id, Order.user_id == user_id))
    order = order_result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    pay_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    existing_payment = pay_result.scalars().first()
    if existing_payment and existing_payment.status == "PAID":
        raise HTTPException(status_code=400, detail="Order already paid.")

    # --- DEMO MODE: skip real Razorpay ---
    if settings.DEMO_MODE:
        demo_rzp_order_id = f"demo_order_{uuid.uuid4().hex[:12]}"
        if existing_payment:
            existing_payment.razorpay_order_id = demo_rzp_order_id
            existing_payment.status = "PENDING"
        else:
            db.add(Payment(
                order_id=order.id,
                razorpay_order_id=demo_rzp_order_id,
                amount=order.total,
                currency="INR",
                status="PENDING",
            ))
        await db.commit()
        return {
            "razorpay_order_id": demo_rzp_order_id,
            "razorpay_key_id": "DEMO_MODE",
            "amount": int(float(order.total) * 100),
            "currency": "INR",
            "order_number": order.order_number,
            "demo_mode": True,
        }

    # --- PRODUCTION: real Razorpay ---
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        amount_paise = int(float(order.total) * 100)
        rzp_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order.order_number,
            "notes": {"order_id": str(order.id)},
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment gateway error: {str(e)}")

    if existing_payment:
        existing_payment.razorpay_order_id = rzp_order["id"]
        existing_payment.status = "PENDING"
    else:
        db.add(Payment(
            order_id=order.id,
            razorpay_order_id=rzp_order["id"],
            amount=order.total,
            currency="INR",
            status="PENDING",
        ))
    await db.commit()

    return {
        "razorpay_order_id": rzp_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount": int(float(order.total) * 100),
        "currency": "INR",
        "order_number": order.order_number,
    }


@router.post("/create-order")
async def create_online_payment_order(req: CreateOnlineOrderRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Create Razorpay order for ONLINE payment. Actual order created only after payment verification."""
    if not settings.ONLINE_PAYMENT_ENABLED:
        raise HTTPException(status_code=503, detail="Online payment is currently unavailable. Please choose Cash on Delivery.")
    user_id = await get_current_user_id(request)

    # Get cart
    cart_result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = cart_result.scalars().first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    items_result = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    cart_items = items_result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    # Calculate cart total
    subtotal = Decimal("0.00")
    cart_items_data = []
    for item in cart_items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = prod_result.scalars().first()
        if not product or not product.is_available:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} is not available.")
        item_subtotal = product.price * item.quantity
        subtotal += Decimal(str(item_subtotal))
        cart_items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": item.quantity,
            "unit_price": Decimal(str(product.price)),
            "subtotal": Decimal(str(item_subtotal)),
        })

    # Delivery validation
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

    total = subtotal + delivery_fee

    # Store cart+delivery data in session for verification step
    # In production, consider storing temporary order data
    session_key = f"online_order_{user_id}_{datetime.utcnow().timestamp()}"

    # Create Razorpay order
    temp_receipt = f"online_{user_id}_{int(datetime.utcnow().timestamp())}"

    if settings.DEMO_MODE:
        demo_rzp_order_id = f"demo_order_{uuid.uuid4().hex[:12]}"
        return {
            "razorpay_order_id": demo_rzp_order_id,
            "razorpay_key_id": "DEMO_MODE",
            "amount": int(float(total) * 100),
            "currency": "INR",
            "demo_mode": True,
            "order_data": {
                "order_type": req.order_type,
                "delivery_address": req.delivery_address,
                "delivery_house_flat_door": req.delivery_house_flat_door,
                "delivery_street_area": req.delivery_street_area,
                "delivery_city": req.delivery_city,
                "delivery_state": req.delivery_state,
                "delivery_pincode": req.delivery_pincode,
                "delivery_landmark": req.delivery_landmark,
                "delivery_lat": req.delivery_lat,
                "delivery_lng": req.delivery_lng,
                "subtotal": float(subtotal),
                "delivery_fee": float(delivery_fee),
                "total": float(total),
                "notes": req.notes,
            }
        }

    try:
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        amount_paise = int(float(total) * 100)
        rzp_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": temp_receipt,
            "notes": {"user_id": str(user_id), "payment_type": "online"},
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment gateway error: {str(e)}")

    return {
        "razorpay_order_id": rzp_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount": int(float(total) * 100),
        "currency": "INR",
        "order_data": {
            "order_type": req.order_type,
            "delivery_address": req.delivery_address,
            "delivery_house_flat_door": req.delivery_house_flat_door,
            "delivery_street_area": req.delivery_street_area,
            "delivery_city": req.delivery_city,
            "delivery_state": req.delivery_state,
            "delivery_pincode": req.delivery_pincode,
            "delivery_landmark": req.delivery_landmark,
            "delivery_lat": req.delivery_lat,
            "delivery_lng": req.delivery_lng,
            "subtotal": float(subtotal),
            "delivery_fee": float(delivery_fee),
            "total": float(total),
            "notes": req.notes,
        }
    }


@router.post("/verify")
async def verify_payment(req: VerifyPaymentRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Verify payment. For ONLINE orders, creates actual order. For OFFLINE, updates existing order."""
    user_id = await get_current_user_id(request)

    # --- Signature check (skip in demo mode) ---
    if not settings.DEMO_MODE:
        msg = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
        expected_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, req.razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid payment signature.")

    pay_result = await db.execute(select(Payment).where(Payment.razorpay_order_id == req.razorpay_order_id))
    payment = pay_result.scalars().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    if payment.status == "PAID":
        order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
        order = order_result.scalars().first()
        return {"message": "Payment already verified.", "order_id": payment.order_id, "order_number": order.order_number if order else None}

    payment.razorpay_payment_id = req.razorpay_payment_id
    payment.status = "PAID"

    order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
    order = order_result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this payment.")

    # Update order status
    order.status = "PAYMENT_VERIFIED"
    order.payment_status = "PAID"

    otp = generate_otp(6)
    order.delivery_otp = otp
    order.otp_expires_at = datetime.utcnow() + timedelta(hours=12)
    order.otp_attempts = 0

    db.add(OrderStatusHistory(order_id=order.id, status="PAYMENT_VERIFIED", changed_by="system"))
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    if user:
        await send_delivery_otp_sms(user.mobile, otp)

    await ws_manager.broadcast_to_admins({
        "event": "PAYMENT_VERIFIED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": "PAYMENT_VERIFIED",
    })
    await ws_manager.send_to_customer(user_id, {
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": "PAYMENT_VERIFIED",
    })

    return {
        "message": "Payment verified. Order confirmed.",
        "order_id": order.id,
        "order_number": order.order_number,
    }


@router.post("/verify-online")
async def verify_online_payment(req: VerifyOnlinePaymentRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Verify ONLINE payment and CREATE the actual order."""
    if not settings.ONLINE_PAYMENT_ENABLED:
        raise HTTPException(status_code=503, detail="Online payment is currently unavailable. Please choose Cash on Delivery.")
    user_id = await get_current_user_id(request)

    # --- Signature check (skip in demo mode) ---
    if not settings.DEMO_MODE:
        msg = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
        expected_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, req.razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid payment signature.")

    # Get cart
    cart_result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = cart_result.scalars().first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    items_result = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    cart_items = items_result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    # Validate and lock products, calculate total
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

    # Get delivery data from request (frontend should send it)
    delivery_data = getattr(req, 'order_data', {}) or {}

    delivery_fee = Decimal("0.00")
    if delivery_data.get("order_type") == "DELIVERY":
        delivery_fee = Decimal(str(settings.DELIVERY_CHARGE))

    total = subtotal + delivery_fee

    # Create order number
    order_number = await generate_order_number(db)

    # CREATE ACTUAL ORDER
    order = Order(
        order_number=order_number,
        user_id=user_id,
        order_type=delivery_data.get("order_type", "DELIVERY"),
        delivery_address=delivery_data.get("delivery_address"),
        delivery_house_flat_door=delivery_data.get("delivery_house_flat_door"),
        delivery_street_area=delivery_data.get("delivery_street_area"),
        delivery_city=delivery_data.get("delivery_city"),
        delivery_state=delivery_data.get("delivery_state"),
        delivery_pincode=delivery_data.get("delivery_pincode"),
        delivery_landmark=delivery_data.get("delivery_landmark"),
        delivery_lat=Decimal(str(delivery_data.get("delivery_lat"))) if delivery_data.get("delivery_lat") else None,
        delivery_lng=Decimal(str(delivery_data.get("delivery_lng"))) if delivery_data.get("delivery_lng") else None,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=Decimal("0.00"),
        total=total,
        status="PAYMENT_VERIFIED",
        payment_method="ONLINE",
        payment_status="PAID",
        payment_mode="ONLINE",
        notes=delivery_data.get("notes"),
    )
    db.add(order)
    await db.flush()

    # Create order items
    for oi in order_items_data:
        db.add(OrderItem(
            order_id=order.id,
            product_id=oi["product_id"],
            quantity=oi["quantity"],
            unit_price=oi["unit_price"],
            subtotal=oi["subtotal"],
        ))

    # Create status history
    db.add(OrderStatusHistory(order_id=order.id, status="PAYMENT_VERIFIED", changed_by="system"))

    # Create payment record
    db.add(Payment(
        order_id=order.id,
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        amount=order.total,
        currency="INR",
        status="PAID",
    ))

    await db.commit()

    # Broadcast inventory updates
    for product in locked_products:
        await ws_manager.broadcast_inventory({"type": "stock_update", "product_id": product.id, "stock_quantity": product.stock_quantity, "is_available": product.is_available})

    # Clear cart
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    # Generate and send OTP
    otp = generate_otp(6)
    order.delivery_otp = otp
    order.otp_expires_at = datetime.utcnow() + timedelta(hours=12)
    db.add(order)
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    if user:
        await send_delivery_otp_sms(user.mobile, otp)

    # Notify admin
    await ws_manager.broadcast_to_admins({
        "event": "NEW_ORDER",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "user_id": user_id,
            "total": float(order.total),
            "status": order.status,
            "order_type": order.order_type,
            "items": order_items_data and [{"name": oi["product_name"], "quantity": oi["quantity"]} for oi in order_items_data],
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
    })

    return {
        "message": "Payment verified. Order created and confirmed.",
        "order_id": order.id,
        "order_number": order.order_number,
    }


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Idempotent Razorpay webhook handler."""
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    import json
    payload = json.loads(body)
    event = payload.get("event", "")

    if event == "payment.captured":
        payment_entity = payload["payload"]["payment"]["entity"]
        rzp_payment_id = payment_entity["id"]
        rzp_order_id = payment_entity["order_id"]

        pay_result = await db.execute(select(Payment).where(Payment.razorpay_order_id == rzp_order_id))
        payment = pay_result.scalars().first()
        if payment and payment.status != "PAID":
            payment.razorpay_payment_id = rzp_payment_id
            payment.status = "PAID"
            order_result = await db.execute(select(Order).where(Order.id == payment.order_id))
            order = order_result.scalars().first()
            if order and order.status == "NEW":
                order.status = "PAYMENT_VERIFIED"
                db.add(OrderStatusHistory(order_id=order.id, status="PAYMENT_VERIFIED", changed_by="webhook"))
            await db.commit()

    return {"status": "ok"}
