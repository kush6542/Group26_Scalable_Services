import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.notification_service.src.database import Base, get_db
from services.notification_service.src.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"
    assert response.json()["service"] == "notification_service"

def test_notification_send_success():
    payload = {
        "order_id": "ord-notif-001",
        "recipient": "+15550001111",
        "channel": "SMS",
        "message": "Your FoodFlow order has been placed successfully!"
    }
    resp = client.post("/api/v1/notifications/send", json=payload)
    assert resp.status_code == 201
    assert resp.json()["status"] == "SENT"
    assert resp.json()["order_id"] == "ord-notif-001"

def test_notification_simulated_failure():
    payload = {
        "order_id": "ord-notif-002",
        "recipient": "+15550002222",
        "channel": "SMS",
        "message": "Delivery update"
    }
    headers = {"X-Mock-Fail": "true"}
    resp = client.post("/api/v1/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 503
    assert "temporarily unreachable" in resp.json()["error"]["message"]
