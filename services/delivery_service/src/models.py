import datetime
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class DeliveryRider(Base):
    __tablename__ = "delivery_riders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    vehicle_type = Column(String, default="MOTORCYCLE")
    status = Column(String, default="AVAILABLE")  # AVAILABLE, BUSY, OFFLINE
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tasks = relationship("DeliveryTask", back_populates="rider")


class DeliveryTask(Base):
    __tablename__ = "delivery_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, nullable=False, index=True)
    rider_id = Column(String, ForeignKey("delivery_riders.id"), nullable=False)
    pickup_address = Column(String, nullable=False)
    delivery_address = Column(String, nullable=False)
    status = Column(String, default="ASSIGNED")  # ASSIGNED, PICKED_UP, DELIVERED, CANCELLED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    rider = relationship("DeliveryRider", back_populates="tasks")
