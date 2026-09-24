"""
Public delivery-radius config + eligibility check.
Frontend uses this for early UX feedback; final enforcement always happens
in orders.py at order-creation time.
"""
from fastapi import APIRouter

from app.config.settings import settings
from app.schemas.delivery import CheckLocationRequest
from app.utils.location import haversine_distance

router = APIRouter(prefix="/api/delivery", tags=["Delivery"])


@router.get("/config")
async def get_delivery_config():
    return {
        "shop_lat": settings.SHOP_LATITUDE,
        "shop_lng": settings.SHOP_LONGITUDE,
        "radius_km": settings.DELIVERY_RADIUS_KM,
        "delivery_charge": settings.DELIVERY_CHARGE,
    }


@router.post("/check")
async def check_delivery_location(req: CheckLocationRequest):
    distance = haversine_distance(
        settings.SHOP_LATITUDE, settings.SHOP_LONGITUDE,
        req.lat, req.lng,
    )
    eligible = distance <= settings.DELIVERY_RADIUS_KM
    if eligible:
        message = f"Great! We deliver to your location. Your location is {distance:.1f} km from our shop."
    else:
        message = (
            f"Sorry, this location is outside our {settings.DELIVERY_RADIUS_KM:g} km delivery area. "
            f"Your location is {distance:.1f} km away."
        )
    return {
        "distance_km": round(distance, 2),
        "eligible": eligible,
        "radius_km": settings.DELIVERY_RADIUS_KM,
        "message": message,
    }
