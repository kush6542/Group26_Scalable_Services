import datetime
import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Header, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from .config import config
from .database import engine, Base, get_db
from .models import NotificationLog
from .schemas import (
    UniformErrorResponse, ErrorDetail,
    NotificationSendRequest, NotificationResponse
)
from .middleware import CorrelationIdMiddleware, logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FoodFlow - Notification Service",
    version="1.0.0",
    description="Mock notification dispatch service (SMS, Email, Push) with simulated delivery channel failure modes."
)

app.add_middleware(CorrelationIdMiddleware)

# --- Standardized Error Handlers ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    error_code = "NOTIFICATION_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 503:
        error_code = "SERVICE_UNAVAILABLE"
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
            "message": "Invalid notification parameters",
            "details": {"errors": exc.errors()}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.exception(f"Unhandled error in notification service: {exc}", extra={"correlation_id": corr_id})
    content = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Notification dispatch encountered an internal failure.",
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


# --- Notification Dispatch ---
@app.post("/api/v1/notifications/send", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED, tags=["Notifications"])
def send_notification(
    payload: NotificationSendRequest,
    request: Request,
    x_mock_fail: Optional[str] = Header(None, alias="X-Mock-Fail"),
    db: Session = Depends(get_db)
):
    """
    Sends simulated customer/merchant notification.
    Supports simulated failure via header X-Mock-Fail: true or config.SIMULATE_FAILURE.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")

    should_fail = (x_mock_fail and x_mock_fail.lower() == "true") or config.SIMULATE_FAILURE

    if should_fail:
        logger.warning(
            f"Simulated notification provider failure for recipient {payload.recipient}",
            extra={"correlation_id": corr_id}
        )
        notif = NotificationLog(
            id=str(uuid.uuid4()),
            order_id=payload.order_id,
            recipient=payload.recipient,
            channel=payload.channel or "SMS",
            message=payload.message,
            status="FAILED"
        )
        db.add(notif)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Third-party SMS/Email gateway is temporarily unreachable."
        )

    notif = NotificationLog(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        recipient=payload.recipient,
        channel=payload.channel or "SMS",
        message=payload.message,
        status="SENT"
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    logger.info(
        f"Dispatched {notif.channel} notification to {notif.recipient} for order {notif.order_id}",
        extra={"correlation_id": corr_id}
    )
    return notif

@app.get("/api/v1/notifications/order/{order_id}", response_model=List[NotificationResponse], tags=["Notifications"])
def get_notifications_for_order(order_id: str, db: Session = Depends(get_db)):
    """Retrieve notifications sent for a specific order."""
    return db.query(NotificationLog).filter(NotificationLog.order_id == order_id).all()

@app.get("/api/v1/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
def list_notifications(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve recent notifications."""
    return db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit).all()
