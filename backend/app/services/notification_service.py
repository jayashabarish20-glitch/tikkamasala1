"""
Firebase Cloud Messaging (FCM) notification service for admin phone push notifications.
Handles sending notifications to registered admin devices.
Failures are logged but never break order creation.
"""
import logging
import json
import os
from typing import Optional, List
from decimal import Decimal

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

        # Build notification
        title = "🔔 New Order"
        body = f"Order {order_number} — ₹{float(total)}"

        notification = messaging.Notification(title=title, body=body)
        data = {
            "order_id": str(order_id),
            "order_number": order_number,
            "total": str(total),
            "order_type": order_type,
            "action": "open_orders",
        }

        success_count = 0
        failed_tokens = []

        for token in admin_device_tokens:
            try:
                message = messaging.Message(
                    notification=notification,
                    data=data,
                    token=token,
                    webpush=messaging.WebpushConfig(
                        fcm_options=messaging.WebpushFcmOptions(
                            link="/admin/orders.html"
                        )
                    ),
                )

                response = messaging.send(message)
                logger.info(f"[FCM] Notification sent to token (response: {response})")
                success_count += 1
            except Exception as e:
                logger.warning(f"[FCM] Failed to send to token: {type(e).__name__}")
                # Mark token as potentially invalid for later cleanup
                failed_tokens.append(token)

        # Log summary
        if success_count > 0:
            logger.info(f"[FCM] New order notification sent to {success_count}/{len(admin_device_tokens)} devices")

        # Return failed tokens for potential cleanup (caller responsibility)
        if failed_tokens:
            logger.debug(f"[FCM] Failed tokens for potential cleanup: {len(failed_tokens)}")

        return success_count > 0

    except Exception as e:
        logger.exception(f"[FCM] Unexpected error sending notification: {e}")
        return False
