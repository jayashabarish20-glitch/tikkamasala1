"""
Firebase Cloud Messaging (FCM) notification service for admin phone push notifications.
Handles sending notifications to registered admin devices.
Failures are logged but never break order creation.
"""
import asyncio
import logging
import json
import os
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_notification_device import AdminNotificationDevice

logger = logging.getLogger(__name__)

# Firebase Admin SDK will be initialized lazily on first use
_firebase_app = None


def _initialize_firebase():
    """Initialize Firebase Admin SDK once. Uses environment-based configuration."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        # Get service account JSON path from environment
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if not service_account_json:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON not set. FCM notifications disabled.")
            return None

        # Load credentials from JSON file path
        try:
            cred = credentials.Certificate(service_account_json)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("[FCM] Firebase Admin SDK initialized successfully")
            return _firebase_app
        except Exception as e:
            logger.error(f"[FCM] Failed to initialize Firebase: {e}")
            return None
    except ImportError:
        logger.warning("[FCM] firebase-admin package not installed. FCM disabled.")
        return None


def _send_to_tokens(messaging, data: dict, tokens: List[str]) -> int:
    """Blocking FCM calls. Runs in a worker thread so the event loop is never stalled."""
    success_count = 0
    for token in tokens:
        try:
            # Data-only message: the service worker builds the visible notification,
            # so the browser never shows a second copy.
            message = messaging.Message(
                data=data,
                token=token,
                webpush=messaging.WebpushConfig(
                    headers={"Urgency": "high"},
                    fcm_options=messaging.WebpushFcmOptions(
                        link="/admin/orders.html"
                    ),
                ),
            )
            response = messaging.send(message)
            logger.info(f"[FCM] Notification sent to token (response: {response})")
            success_count += 1
        except Exception as e:
            logger.warning(f"[FCM] Failed to send to token: {type(e).__name__}")
    return success_count


async def send_admin_new_order_notification(
    order_id: int,
    order_number: str,
    total: Decimal,
    order_type: str,
    admin_device_tokens: List[str]
) -> bool:
    """
    Send FCM notification to admin devices about a new order.

    Args:
        order_id: Order ID
        order_number: Order number (e.g., "TM20261008001")
        total: Order total amount
        order_type: "DELIVERY" or "PICKUP"
        admin_device_tokens: List of FCM device tokens to notify

    Returns:
        True if at least one notification succeeded, False otherwise.
        Failure never breaks order creation.
    """
    if not admin_device_tokens:
        logger.debug("[FCM] No admin device tokens registered. Skipping notification.")
        return False

    firebase_app = _initialize_firebase()
    if firebase_app is None:
        logger.warning("[FCM] Firebase not initialized. Notification skipped.")
        return False

    try:
        from firebase_admin import messaging

        data = {
            "title": "New Order Received",
            "body": f"Order {order_number} — ₹{float(total)}",
            "order_id": str(order_id),
            "order_number": order_number,
            "total": str(total),
            "order_type": order_type,
            "action": "open_orders",
        }

        success_count = await asyncio.to_thread(_send_to_tokens, messaging, data, admin_device_tokens)

        if success_count > 0:
            logger.info(f"[FCM] New order notification sent to {success_count}/{len(admin_device_tokens)} devices")

        return success_count > 0

    except Exception as e:
        logger.exception(f"[FCM] Unexpected error sending notification: {e}")
        return False


async def notify_admins_new_order(db: AsyncSession, order) -> bool:
    """
    Push "New Order Received" to every active admin device.
    Never raises: the order is already saved, so a notification problem must not affect it.
    """
    try:
        result = await db.execute(
            select(AdminNotificationDevice.device_token).where(
                AdminNotificationDevice.is_active == True
            )
        )
        tokens = list(result.scalars().all())
        return await send_admin_new_order_notification(
            order_id=order.id,
            order_number=order.order_number,
            total=order.total,
            order_type=order.order_type,
            admin_device_tokens=tokens,
        )
    except Exception as e:
        logger.exception(f"[FCM] Could not send new order notification: {e}")
        return False
