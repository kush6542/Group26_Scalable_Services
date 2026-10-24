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

# --- Notification Schemas ---
class NotificationSendRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    recipient: str = Field(..., min_length=1)
    channel: Optional[str] = "SMS"
    message: str = Field(..., min_length=1)

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    recipient: str
    channel: str
    message: str
    status: str
    created_at: datetime.datetime
