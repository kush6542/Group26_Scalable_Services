import os

class Config:
    SERVICE_NAME = os.getenv("SERVICE_NAME", "payment_service")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8003"))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./payment.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SIMULATE_FAILURE_RATE = float(os.getenv("SIMULATE_FAILURE_RATE", "0.0"))
    SIMULATE_DELAY_MS = int(os.getenv("SIMULATE_DELAY_MS", "0"))

config = Config()
