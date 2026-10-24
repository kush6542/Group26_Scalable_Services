import os

class Config:
    SERVICE_NAME = os.getenv("SERVICE_NAME", "delivery_service")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8004"))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./delivery.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()
