import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.delivery_service.src.database import Base, get_db
from services.delivery_service.src.main import app
from services.delivery_service.src.models import DeliveryRider

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
    assert response.json()["service"] == "delivery_service"

def test_br5_rider_assignment_success():
    """
    BR5: Rider Allocation Constraint.
    Available rider is assigned to the task and their status changes to BUSY.
    """
    # 1. Register Rider
    r_resp = client.post("/api/v1/deliveries/riders", json={"name": "Alex Rider", "phone": "+15551234567"})
    assert r_resp.status_code == 201
    rider_id = r_resp.json()["id"]
    assert r_resp.json()["status"] == "AVAILABLE"

    # 2. Dispatch Task
    t_resp = client.post("/api/v1/deliveries/tasks", json={
        "order_id": "ord-deliv-001",
        "pickup_address": "123 Restaurant Way",
        "delivery_address": "789 Customer Ave"
    })
    assert t_resp.status_code == 201
    assert t_resp.json()["rider_id"] == rider_id
    assert t_resp.json()["status"] == "ASSIGNED"

    # 3. Verify rider is now BUSY
    db = TestingSessionLocal()
    rider = db.query(DeliveryRider).filter(DeliveryRider.id == rider_id).first()
    assert rider.status == "BUSY"
    db.close()

def test_br5_rider_assignment_no_rider_available():
    """
    BR5: If all riders are BUSY or no riders exist, task dispatch returns 409 Conflict.
    """
    # No riders registered yet
    t_resp = client.post("/api/v1/deliveries/tasks", json={
        "order_id": "ord-deliv-002",
        "pickup_address": "123 Restaurant Way",
        "delivery_address": "789 Customer Ave"
    })
    assert t_resp.status_code == 409
    assert "No delivery riders are currently available" in t_resp.json()["error"]["message"]

def test_delivery_saga_cancellation():
    """
    Challenge 3C: Saga cancellation must cancel task and free the rider back to AVAILABLE.
    """
    client.post("/api/v1/deliveries/riders", json={"name": "Sarah Swift", "phone": "+15559876543"})
    t_resp = client.post("/api/v1/deliveries/tasks", json={
        "order_id": "ord-deliv-003",
        "pickup_address": "123 Restaurant Way",
        "delivery_address": "789 Customer Ave"
    })
    task_id = t_resp.json()["id"]
    rider_id = t_resp.json()["rider_id"]

    # Cancel task (compensating action)
    cancel_resp = client.post(f"/api/v1/deliveries/tasks/{task_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Verify rider is freed back to AVAILABLE
    db = TestingSessionLocal()
    rider = db.query(DeliveryRider).filter(DeliveryRider.id == rider_id).first()
    assert rider.status == "AVAILABLE"
    db.close()
