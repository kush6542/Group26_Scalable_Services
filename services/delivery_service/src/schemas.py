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

# --- Rider Schemas ---
class RiderCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=5)
    vehicle_type: Optional[str] = "MOTORCYCLE"

class RiderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str
    vehicle_type: str
    status: str
    created_at: datetime.datetime

# --- Delivery Task Schemas ---
class DeliveryTaskCreate(BaseModel):
    order_id: str = Field(..., min_length=1)
    pickup_address: str = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=1)

class DeliveryTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    rider_id: str
    pickup_address: str
    delivery_address: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

class TaskStatusUpdate(BaseModel):
    status: str = Field(..., description="New status: PICKED_UP, DELIVERED, CANCELLED")
