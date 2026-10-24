import os

class Config:
    SERVICE_NAME = os.getenv("SERVICE_NAME", "notification_service")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8005"))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notification.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SIMULATE_FAILURE = os.getenv("SIMULATE_FAILURE", "false").lower() == "true"

config = Config()
