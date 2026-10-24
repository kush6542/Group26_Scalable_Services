import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, nullable=False, index=True)
    restaurant_id = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    
    # State Machine Lifecycle
    status = Column(String, default="PENDING")  # PENDING, STOCK_RESERVED, PAID, DELIVERY_ASSIGNED, CONFIRMED, FAILED_*, CANCELLED
    
    delivery_address = Column(String, nullable=False)
    pickup_address = Column(String, default="Restaurant Address")

    # Loose references to external microservices (database-per-service compliance)
    reservation_id = Column(String, nullable=True)
    payment_id = Column(String, nullable=True)
    delivery_task_id = Column(String, nullable=True)
    
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    state_logs = relationship("OrderStateLog", back_populates="order", cascade="all, delete-orphan")


class OrderStateLog(Base):
    __tablename__ = "order_state_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    from_state = Column(String, nullable=False)
    to_state = Column(String, nullable=False)
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("Order", back_populates="state_logs")


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
