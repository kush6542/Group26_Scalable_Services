import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

# --- Uniform Error Schema ---
class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")

class UniformErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str

# --- Order Schemas ---
class OrderCheckoutRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    restaurant_id: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    delivery_address: str = Field(..., min_length=1)
    pickup_address: Optional[str] = "123 Restaurant Avenue"
    card_number: Optional[str] = "4111111111111111"

class OrderStateLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_state: str
    to_state: str
    note: str
    created_at: datetime.datetime

class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    restaurant_id: str
    item_id: str
    quantity: int
    unit_price: float
    total_amount: float
    status: str
    delivery_address: str
    pickup_address: str
    reservation_id: Optional[str] = None
    payment_id: Optional[str] = None
    delivery_task_id: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    state_logs: List[OrderStateLogResponse] = []
