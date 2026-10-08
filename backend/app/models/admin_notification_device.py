from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.config.database import Base


class AdminNotificationDevice(Base):
    __tablename__ = "admin_notification_devices"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    device_token = Column(String(500), unique=True, nullable=False, index=True)
    platform = Column(String(20), default="web")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
