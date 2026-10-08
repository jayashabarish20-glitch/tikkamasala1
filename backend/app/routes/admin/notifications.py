"""
Admin notification device registration routes.
Allows admin phones to register their FCM device tokens for push notifications.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.config.database import get_db
from app.models.admin_notification_device import AdminNotificationDevice
from app.routes.admin.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin Notifications"])


class RegisterDeviceRequest(BaseModel):
    token: str
    platform: str = "web"


class DeviceResponse(BaseModel):
    id: int
    device_token: str
    platform: str
    is_active: bool


@router.post("/notifications/register-device")
async def register_device(
    req: RegisterDeviceRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register admin device token for push notifications."""
    payload = await require_admin(request)
    admin_id = int(payload["sub"])

    if not req.token or len(req.token) < 10:
        raise HTTPException(status_code=400, detail="Invalid device token.")

    # Check if token already exists
    existing_result = await db.execute(
        select(AdminNotificationDevice).where(
            AdminNotificationDevice.device_token == req.token
        )
    )
    existing = existing_result.scalars().first()

    if existing:
        # If it exists but belongs to a different admin, reject
        if existing.admin_id != admin_id:
            raise HTTPException(status_code=400, detail="Device token already registered.")
        # If it exists for this admin, reactivate it
        existing.is_active = True
        db.add(existing)
    else:
        # Create new device token record
        device = AdminNotificationDevice(
            admin_id=admin_id,
            device_token=req.token,
            platform=req.platform,
            is_active=True,
        )
        db.add(device)

    await db.commit()

    return {
        "message": "Device token registered successfully.",
        "platform": req.platform,
    }


@router.get("/notifications/devices")
async def list_devices(request: Request, db: AsyncSession = Depends(get_db)):
    """List all registered devices for the current admin."""
    payload = await require_admin(request)
    admin_id = int(payload["sub"])

    result = await db.execute(
        select(AdminNotificationDevice).where(
            AdminNotificationDevice.admin_id == admin_id
        )
    )
    devices = result.scalars().all()

    return [
        {
            "id": d.id,
            "platform": d.platform,
            "is_active": d.is_active,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in devices
    ]


@router.delete("/notifications/devices/{device_id}")
async def unregister_device(
    device_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Unregister (deactivate) a device from receiving notifications."""
    payload = await require_admin(request)
    admin_id = int(payload["sub"])

    result = await db.execute(
        select(AdminNotificationDevice).where(
            AdminNotificationDevice.id == device_id,
            AdminNotificationDevice.admin_id == admin_id,
        )
    )
    device = result.scalars().first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")

    device.is_active = False
    db.add(device)
    await db.commit()

    return {"message": "Device unregistered successfully."}
