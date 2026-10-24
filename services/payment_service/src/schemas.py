import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Uniform Error Schema ---
class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")

class UniformErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str

# --- Payment Schemas ---
class PaymentChargeRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = "CREDIT_CARD"
    card_number: Optional[str] = "4111111111111111"

class PaymentChargeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    failure_reason: Optional[str] = None
    created_at: datetime.datetime

class RefundRequest(BaseModel):
    reason: Optional[str] = "Order cancelled / Saga compensation"

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    amount: float
    status: str
    message: str
