import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text
from .database import Base

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, nullable=False, index=True)
    recipient = Column(String, nullable=False)
    channel = Column(String, default="SMS")  # SMS, EMAIL, PUSH
    message = Column(Text, nullable=False)
    status = Column(String, default="SENT")  # SENT, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
