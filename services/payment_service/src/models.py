import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, UniqueConstraint
from .database import Base

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    payment_method = Column(String, default="CREDIT_CARD")
    status = Column(String, default="SUCCESS")  # SUCCESS, FAILED, REFUNDED
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, unique=True, nullable=False, index=True)
    request_hash = Column(String, nullable=False)
    status = Column(String, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
