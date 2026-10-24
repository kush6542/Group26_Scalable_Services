import datetime
import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import update

from .config import config
from .database import engine, Base, get_db
from .models import DeliveryRider, DeliveryTask
from .schemas import (
    UniformErrorResponse, ErrorDetail,
    RiderCreate, RiderResponse,
    DeliveryTaskCreate, DeliveryTaskResponse, TaskStatusUpdate
)
from .middleware import CorrelationIdMiddleware, logger

Base.metadata.create_all(bind=engine)

def seed_default_rider():
    """Auto-seeds default available rider so fresh clones have immediate demo data."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(DeliveryRider).filter(DeliveryRider.id == "rider-dave-01").first() is None:
            rider = DeliveryRider(
                id="rider-dave-01",
                name="Dave Courier",
                phone="+19998887777",
                vehicle_type="MOTORBIKE",
                status="AVAILABLE"
            )
            db.add(rider)
            db.commit()
    except Exception as e:
        logger.warning(f"Default rider seed skipped: {e}")
    finally:
        db.close()

seed_default_rider()

app = FastAPI(
    title="FoodFlow - Delivery Service",
    version="1.0.0",
    description="Manages riders, dispatch, delivery fulfillment, and compensating task cancellations."
)

app.add_middleware(CorrelationIdMiddleware)

# --- Standardized Error Handlers ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    error_code = "DELIVERY_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "NO_RIDER_AVAILABLE"
    elif exc.status_code == 422:
        error_code = "UNPROCESSABLE_ENTITY"

    content = {
        "error": {
            "code": error_code,
            "message": str(exc.detail),
            "details": {}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=exc.status_code, content=content)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    content = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid delivery request parameters",
            "details": {"errors": exc.errors()}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.exception(f"Unhandled error in delivery service: {exc}", extra={"correlation_id": corr_id})
    content = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Delivery service encountered an unexpected error.",
            "details": {}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)


# --- Operability: Health Check ---
@app.get("/health", tags=["Operability"])
def health_check():
    return {
        "status": "UP",
        "service": config.SERVICE_NAME,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


# --- Rider Management ---
@app.get("/api/v1/deliveries/riders", response_model=List[RiderResponse], tags=["Riders"])
def list_riders(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """List riders, optionally filtering by status."""
    query = db.query(DeliveryRider)
    if status_filter:
        query = query.filter(DeliveryRider.status == status_filter.upper())
    return query.all()

@app.post("/api/v1/deliveries/riders", response_model=RiderResponse, status_code=status.HTTP_201_CREATED, tags=["Riders"])
def register_rider(payload: RiderCreate, db: Session = Depends(get_db)):
    """Register a new delivery rider."""
    rider = DeliveryRider(
        id=str(uuid.uuid4()),
        name=payload.name,
        phone=payload.phone,
        vehicle_type=payload.vehicle_type or "MOTORCYCLE",
        status="AVAILABLE"
    )
    db.add(rider)
    db.commit()
    db.refresh(rider)
    return rider


# --- Delivery Dispatch & Assignment ---
@app.post("/api/v1/deliveries/tasks", response_model=DeliveryTaskResponse, status_code=status.HTTP_201_CREATED, tags=["Delivery Tasks"])
def dispatch_delivery(payload: DeliveryTaskCreate, request: Request, db: Session = Depends(get_db)):
    """
    BR5: Rider Allocation Constraint.
    Finds an available rider and atomically assigns the delivery task.
    If no rider is AVAILABLE, rejects with 409 Conflict.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")

    # Lock / select first available rider
    rider = db.query(DeliveryRider).filter(DeliveryRider.status == "AVAILABLE").first()
    if not rider:
        logger.warning(f"BR5: No available delivery rider found for order {payload.order_id}", extra={"correlation_id": corr_id})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No delivery riders are currently available in the service zone."
        )

    # Assign rider
    rider.status = "BUSY"
    task = DeliveryTask(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        rider_id=rider.id,
        pickup_address=payload.pickup_address,
        delivery_address=payload.delivery_address,
        status="ASSIGNED"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(
        f"Assigned rider {rider.name} ({rider.id}) to delivery task {task.id} for order {payload.order_id}",
        extra={"correlation_id": corr_id}
    )
    return task


# --- Challenge 3C (Saga Compensation) ---
@app.post("/api/v1/deliveries/tasks/{task_id}/cancel", response_model=DeliveryTaskResponse, tags=["Delivery Tasks"])
def cancel_delivery_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Saga Compensating Action:
    Cancels an assigned delivery task and frees the rider back to AVAILABLE status.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")
    task = db.query(DeliveryTask).filter(DeliveryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Delivery task '{task_id}' not found")

    if task.status == "CANCELLED":
        return task

    task.status = "CANCELLED"
    # Restore rider status back to AVAILABLE
    rider = db.query(DeliveryRider).filter(DeliveryRider.id == task.rider_id).first()
    if rider and rider.status == "BUSY":
        rider.status = "AVAILABLE"

    db.commit()
    db.refresh(task)

    logger.info(
        f"SAGA COMPENSATION: Cancelled delivery task {task_id}, freed rider {task.rider_id}",
        extra={"correlation_id": corr_id}
    )
    return task


# --- Task Status Transitions ---
@app.patch("/api/v1/deliveries/tasks/{task_id}/status", response_model=DeliveryTaskResponse, tags=["Delivery Tasks"])
def update_task_status(task_id: str, payload: TaskStatusUpdate, request: Request, db: Session = Depends(get_db)):
    """Updates delivery lifecycle (PICKED_UP -> DELIVERED). When DELIVERED, rider returns to AVAILABLE."""
    corr_id = getattr(request.state, "correlation_id", "N/A")
    task = db.query(DeliveryTask).filter(DeliveryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Delivery task '{task_id}' not found")

    new_status = payload.status.upper()
    valid_statuses = ["ASSIGNED", "PICKED_UP", "DELIVERED", "CANCELLED"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {valid_statuses}")

    task.status = new_status
    if new_status in ["DELIVERED", "CANCELLED"]:
        rider = db.query(DeliveryRider).filter(DeliveryRider.id == task.rider_id).first()
        if rider:
            rider.status = "AVAILABLE"

    db.commit()
    db.refresh(task)
    logger.info(f"Updated task {task_id} status to {new_status}", extra={"correlation_id": corr_id})
    return task

@app.get("/api/v1/deliveries/tasks/{task_id}", response_model=DeliveryTaskResponse, tags=["Delivery Tasks"])
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Retrieve delivery task details."""
    task = db.query(DeliveryTask).filter(DeliveryTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Delivery task '{task_id}' not found")
    return task

@app.get("/api/v1/deliveries/tasks/order/{order_id}", response_model=List[DeliveryTaskResponse], tags=["Delivery Tasks"])
def get_tasks_for_order(order_id: str, db: Session = Depends(get_db)):
    """Retrieve delivery tasks for an order."""
    return db.query(DeliveryTask).filter(DeliveryTask.order_id == order_id).all()
