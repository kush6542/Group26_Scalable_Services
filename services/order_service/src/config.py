import os

class Config:
    SERVICE_NAME = os.getenv("SERVICE_NAME", "order_service")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8001"))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:8002")
    PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")
    DELIVERY_SERVICE_URL = os.getenv("DELIVERY_SERVICE_URL", "http://localhost:8004")
    NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8005")

config = Config()
