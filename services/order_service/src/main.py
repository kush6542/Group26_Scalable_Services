import json
import hashlib
import uuid
import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request, Header, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import config
from .database import engine, Base, get_db
from .models import Order, OrderStateLog, IdempotencyRecord
from .schemas import (
    UniformErrorResponse, ErrorDetail,
    OrderCheckoutRequest, OrderResponse
)
from .saga_orchestrator import SagaOrchestrator
from .middleware import CorrelationIdMiddleware, logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FoodFlow - Order Orchestration Service",
    version="1.0.0",
    description="Coordinates the distributed Order Checkout Saga, manages state machine lifecycles, and enforces idempotency."
)

app.add_middleware(CorrelationIdMiddleware)

# --- Standardized Error Handlers ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    error_code = "ORDER_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "ORDER_CONFLICT"
    elif exc.status_code == 402:
        error_code = "PAYMENT_REQUIRED"
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
            "message": "Invalid order checkout parameters",
            "details": {"errors": exc.errors()}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.exception(f"Unhandled error in order service: {exc}", extra={"correlation_id": corr_id})
    content = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Order service encountered an unexpected error.",
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


# --- Order Checkout Saga (Challenge 3C) & Idempotency (Challenge 2) ---
@app.post("/api/v1/orders/checkout", tags=["Orders"])
def checkout_order(
    payload: OrderCheckoutRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_mock_payment_fail: Optional[str] = Header(None, alias="X-Mock-Payment-Fail"),
    db: Session = Depends(get_db)
):
    """
    Main Business Transaction (Condition b):
    Executes the multi-service checkout Saga spanning Restaurant, Payment, Delivery, and Notification services.
    Enforces Challenge 2 (Idempotency) and Challenge 3C (Saga with Compensating Rollbacks).
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")

    # 1. Idempotency Check
    payload_dict = payload.model_dump()
    raw_payload_json = json.dumps(payload_dict, sort_keys=True)
    req_hash = hashlib.sha256(raw_payload_json.encode("utf-8")).hexdigest()

    idem_rec = None
    if idempotency_key:
        idem_rec = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == idempotency_key).first()
        if idem_rec:
            if idem_rec.request_hash != req_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Idempotency key '{idempotency_key}' already used with a different checkout payload."
                )
            if idem_rec.status == "COMPLETED" and idem_rec.response_body:
                logger.info(f"Returning cached order response for key {idempotency_key}", extra={"correlation_id": corr_id})
                cached_data = json.loads(idem_rec.response_body)
                return JSONResponse(
                    status_code=idem_rec.response_code or 200,
                    content=cached_data,
                    headers={"X-Idempotent-Replay": "true"}
                )
        else:
            try:
                idem_rec = IdempotencyRecord(
                    id=str(uuid.uuid4()),
                    key=idempotency_key,
                    request_hash=req_hash,
                    status="IN_PROGRESS"
                )
                db.add(idem_rec)
                db.commit()
            except IntegrityError:
                db.rollback()
                idem_rec = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == idempotency_key).first()
                if idem_rec and idem_rec.response_body:
                    return JSONResponse(
                        status_code=idem_rec.response_code or 200,
                        content=json.loads(idem_rec.response_body),
                        headers={"X-Idempotent-Replay": "true"}
                    )

    # 2. Create Order in PENDING state
    total_amount = round(payload.unit_price * payload.quantity, 2)
    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        customer_id=payload.customer_id,
        restaurant_id=payload.restaurant_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_amount=total_amount,
        status="PENDING",
        delivery_address=payload.delivery_address,
        pickup_address=payload.pickup_address or "123 Restaurant Avenue",
        failure_reason=None
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Initial state log
    initial_log = OrderStateLog(
        id=str(uuid.uuid4()),
        order_id=order.id,
        from_state="NONE",
        to_state="PENDING",
        note="Order checkout initiated by customer"
    )
    db.add(initial_log)
    db.commit()

    # 3. Execute Saga Orchestration
    orchestrator = SagaOrchestrator(db, correlation_id=corr_id)
    mock_pay_fail = (x_mock_payment_fail and x_mock_payment_fail.lower() == "true")
    saga_success = orchestrator.execute_order_saga(
        order=order,
        card_number=payload.card_number or "4111111111111111",
        mock_payment_fail=mock_pay_fail
    )

    db.refresh(order)

    order_response_data = {
        "id": order.id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "item_id": order.item_id,
        "quantity": order.quantity,
        "unit_price": order.unit_price,
        "total_amount": order.total_amount,
        "status": order.status,
        "delivery_address": order.delivery_address,
        "pickup_address": order.pickup_address,
        "reservation_id": order.reservation_id,
        "payment_id": order.payment_id,
        "delivery_task_id": order.delivery_task_id,
        "failure_reason": order.failure_reason,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "state_logs": [
            {
                "id": log.id,
                "from_state": log.from_state,
                "to_state": log.to_state,
                "note": log.note,
                "created_at": log.created_at.isoformat()
            }
            for log in order.state_logs
        ]
    }

    # 4. Handle Saga Result
    if saga_success:
        if idem_rec:
            idem_rec.status = "COMPLETED"
            idem_rec.response_code = status.HTTP_201_CREATED
            idem_rec.response_body = json.dumps(order_response_data)
            db.commit()
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=order_response_data)
    else:
        # Partial failure handled via compensating rollback
        status_code = status.HTTP_409_CONFLICT
        if order.status == "FAILED_PAYMENT_REJECTED":
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        elif order.status == "FAILED_OUT_OF_STOCK":
            status_code = status.HTTP_409_CONFLICT

        if idem_rec:
            idem_rec.status = "COMPLETED"
            idem_rec.response_code = status_code
            idem_rec.response_body = json.dumps(order_response_data)
            db.commit()

        return JSONResponse(status_code=status_code, content=order_response_data)


# --- Order Query APIs ---
@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def get_order(order_id: str, db: Session = Depends(get_db)):
    """Retrieve full order details including all state transition logs."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return order

@app.get("/api/v1/orders", response_model=List[OrderResponse], tags=["Orders"])
def list_orders(customer_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    """List recent orders, optionally filtered by customer."""
    query = db.query(Order)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    return query.order_by(Order.created_at.desc()).limit(limit).all()
