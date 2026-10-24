import json
import hashlib
import uuid
import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Header, status
from fastapi.responses import JSONResponse, Response as FastAPIResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import config
from .database import engine, Base, get_db
from .models import PaymentTransaction, IdempotencyRecord
from .schemas import (
    UniformErrorResponse, ErrorDetail,
    PaymentChargeRequest, PaymentChargeResponse,
    RefundRequest, RefundResponse
)
from .middleware import CorrelationIdMiddleware, logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FoodFlow - Payment Service",
    version="1.0.0",
    description="Mock Payment Service handling transactions, idempotency guarantees, and simulated latency/failures."
)

app.add_middleware(CorrelationIdMiddleware)

# --- Standardized Error Handlers ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    error_code = "PAYMENT_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "IDEMPOTENCY_CONFLICT"
    elif exc.status_code == 402:
        error_code = "PAYMENT_DECLINED"
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
            "message": "Invalid payment parameters",
            "details": {"errors": exc.errors()}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.exception(f"Unhandled error in payment service: {exc}", extra={"correlation_id": corr_id})
    content = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Payment processing encountered an internal error.",
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


# --- Challenge 2: Idempotent Payment Charge ---
@app.post("/api/v1/payments/charge", tags=["Payments"])
def charge_payment(
    payload: PaymentChargeRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_mock_fail: Optional[str] = Header(None, alias="X-Mock-Fail"),
    db: Session = Depends(get_db)
):
    """
    Charges payment for an order.
    Enforces Challenge 2 (Idempotency):
    - Repeating with the same key & identical body returns cached result (BR2).
    - Repeating with the same key & modified body returns 409 Conflict (BR3).
    - Concurrent duplicate requests are guarded via DB unique constraint.
    - Simulated failures (X-Mock-Fail: true or card ending in 9999) trigger controlled decline.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")

    # 1. Payload Fingerprint
    payload_dict = payload.model_dump()
    raw_payload_json = json.dumps(payload_dict, sort_keys=True)
    req_hash = hashlib.sha256(raw_payload_json.encode("utf-8")).hexdigest()

    idem_rec = None
    if idempotency_key:
        idem_rec = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == idempotency_key).first()
        if idem_rec:
            # BR3: Verify Payload Fingerprint
            if idem_rec.request_hash != req_hash:
                logger.warning(
                    f"BR3 Idempotency Conflict: Key '{idempotency_key}' payload hash mismatch.",
                    extra={"correlation_id": corr_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Idempotency key '{idempotency_key}' already used with a different request payload."
                )

            # BR2: Cache Hit Replay
            if idem_rec.status == "COMPLETED" and idem_rec.response_body:
                logger.info(
                    f"BR2 Idempotency Replay: Serving cached response for key '{idempotency_key}'.",
                    extra={"correlation_id": corr_id}
                )
                cached_data = json.loads(idem_rec.response_body)
                return JSONResponse(
                    status_code=idem_rec.response_code or 200,
                    content=cached_data,
                    headers={"X-Idempotent-Replay": "true"}
                )
            elif idem_rec.status == "IN_PROGRESS":
                logger.warning(
                    f"Idempotent in-flight duplicate detected for key '{idempotency_key}'",
                    extra={"correlation_id": corr_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A transaction with this idempotency key is currently in progress. Please retry shortly."
                )
        else:
            # Reserve idempotency key slot
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
                # Concurrent race condition: another thread inserted the exact same key at this instant
                db.rollback()
                idem_rec = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == idempotency_key).first()
                if idem_rec and idem_rec.response_body:
                    cached_data = json.loads(idem_rec.response_body)
                    return JSONResponse(
                        status_code=idem_rec.response_code or 200,
                        content=cached_data,
                        headers={"X-Idempotent-Replay": "true"}
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Concurrent identical request conflict."
                )

    # 2. Check for Simulated or Card Decline Failures (Condition e & Saga Failure Trigger)
    card_declined = payload.card_number and payload.card_number.endswith("9999")
    mock_forced_fail = (x_mock_fail and x_mock_fail.lower() == "true")

    if card_declined or mock_forced_fail:
        failure_msg = "Card declined: Insufficient funds or card restriction" if card_declined else "Mock payment failure triggered by test harness"
        logger.warning(f"Payment declined: {failure_msg}", extra={"correlation_id": corr_id})

        failed_txn = PaymentTransaction(
            id=str(uuid.uuid4()),
            order_id=payload.order_id,
            customer_id=payload.customer_id,
            amount=payload.amount,
            currency=payload.currency or "USD",
            payment_method=payload.payment_method or "CREDIT_CARD",
            status="FAILED",
            failure_reason=failure_msg
        )
        db.add(failed_txn)

        if idem_rec:
            db.delete(idem_rec)  # Do not lock key on hard validation error or allow clean retry
        db.commit()

        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=failure_msg)

    # 3. Successful Payment
    txn = PaymentTransaction(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        currency=payload.currency or "USD",
        payment_method=payload.payment_method or "CREDIT_CARD",
        status="SUCCESS",
        failure_reason=None
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    response_dict = {
        "id": txn.id,
        "order_id": txn.order_id,
        "customer_id": txn.customer_id,
        "amount": txn.amount,
        "currency": txn.currency,
        "status": txn.status,
        "payment_method": txn.payment_method,
        "failure_reason": txn.failure_reason,
        "created_at": txn.created_at.isoformat()
    }

    # 4. Save response in idempotency record
    if idem_rec:
        idem_rec.status = "COMPLETED"
        idem_rec.response_code = status.HTTP_201_CREATED
        idem_rec.response_body = json.dumps(response_dict)
        db.commit()

    logger.info(f"Payment transaction {txn.id} for order {txn.order_id} processed successfully", extra={"correlation_id": corr_id})
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=response_dict)


# --- Refund / Saga Compensating Action ---
@app.post("/api/v1/payments/{payment_id}/refund", response_model=RefundResponse, tags=["Payments"])
def refund_payment(payment_id: str, payload: RefundRequest, request: Request, db: Session = Depends(get_db)):
    """Refunds a payment (compensating transaction)."""
    corr_id = getattr(request.state, "correlation_id", "N/A")
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail=f"Payment transaction '{payment_id}' not found")

    if txn.status == "REFUNDED":
        return RefundResponse(id=txn.id, order_id=txn.order_id, amount=txn.amount, status="REFUNDED", message="Payment was already refunded")

    if txn.status != "SUCCESS":
        raise HTTPException(status_code=400, detail=f"Cannot refund a payment with status '{txn.status}'")

    txn.status = "REFUNDED"
    db.commit()
    db.refresh(txn)

    logger.info(f"SAGA COMPENSATION: Refunded payment {payment_id} for order {txn.order_id}", extra={"correlation_id": corr_id})
    return RefundResponse(
        id=txn.id,
        order_id=txn.order_id,
        amount=txn.amount,
        status="REFUNDED",
        message="Payment successfully refunded"
    )

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentChargeResponse, tags=["Payments"])
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    """Get payment transaction by ID."""
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail=f"Payment transaction '{payment_id}' not found")
    return txn

@app.get("/api/v1/payments/order/{order_id}", response_model=List[PaymentChargeResponse], tags=["Payments"])
def get_payments_for_order(order_id: str, db: Session = Depends(get_db)):
    """Get payment history for an order."""
    return db.query(PaymentTransaction).filter(PaymentTransaction.order_id == order_id).all()
