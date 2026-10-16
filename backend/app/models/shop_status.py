from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, func
from app.config.database import Base


class ShopStatus(Base):
    """Single-row table (id=1) holding whether the shop is accepting orders.

    No row means the shop is open, so existing databases need no seeding.
    """
    __tablename__ = "shop_status"

    id = Column(Integer, primary_key=True)
    is_open = Column(Boolean, nullable=False, default=True)
    updated_by_admin_id = Column(Integer, ForeignKey("admins.id"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
