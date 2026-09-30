from pydantic import BaseModel
from typing import Optional, Dict, Any


class CreatePaymentRequest(BaseModel):
    order_id: int


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyOnlinePaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    order_data: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    razorpay_order_id: str
    amount: float
    currency: str
    status: str

    class Config:
        from_attributes = True
