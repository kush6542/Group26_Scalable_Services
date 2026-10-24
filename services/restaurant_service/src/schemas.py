import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Uniform Error Response Schema ---
class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")

class UniformErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str

# --- Restaurant Schemas ---
class RestaurantCreate(BaseModel):
    name: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)

class RestaurantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    is_active: bool
    created_at: datetime.datetime

# --- Menu Item Schemas ---
class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = ""
    price: float = Field(..., gt=0)
    available_quantity: int = Field(..., ge=0)

class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    restaurant_id: str
    name: str
    description: str
    price: float
    available_quantity: int
    version: int

# --- Reservation Schemas ---
class ReservationCreate(BaseModel):
    order_id: str
    restaurant_id: str
    item_id: str
    quantity: int = Field(..., gt=0)

class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    restaurant_id: str
    item_id: str
    quantity: int
    status: str
    created_at: datetime.datetime
