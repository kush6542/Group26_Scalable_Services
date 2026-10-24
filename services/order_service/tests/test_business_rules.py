import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.order_service.src.database import Base, get_db
from services.order_service.src.main import app
from services.order_service.src.models import Order, OrderStateLog

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
    assert response.json()["service"] == "order_service"

@patch("services.order_service.src.saga_orchestrator.httpx.Client")
def test_order_checkout_happy_path_saga(mock_httpx):
    """
    BR6: Multi-service orchestrated Saga happy path.
    Transitions: PENDING -> STOCK_RESERVED -> PAID -> DELIVERY_ASSIGNED -> CONFIRMED.
    """
    mock_client = MagicMock()
    mock_httpx.return_value.__enter__.return_value = mock_client

    # Mock responses for downstream services
    # Step 1: Restaurant Reservation
    resp_res = MagicMock()
    resp_res.status_code = 201
    resp_res.json.return_value = {"id": "res-999", "status": "RESERVED"}

    # Step 2: Payment Charge
    resp_pay = MagicMock()
    resp_pay.status_code = 201
    resp_pay.json.return_value = {"id": "pay-999", "status": "SUCCESS"}

    # Step 3: Delivery Task
    resp_deliv = MagicMock()
    resp_deliv.status_code = 201
    resp_deliv.json.return_value = {"id": "task-999", "status": "ASSIGNED"}

    # Step 4: Confirm & Notify
    resp_confirm = MagicMock()
    resp_confirm.status_code = 200
    resp_notif = MagicMock()
    resp_notif.status_code = 201

    mock_client.post.side_effect = [resp_res, resp_pay, resp_deliv, resp_confirm, resp_notif]

    payload = {
        "customer_id": "cust-1",
        "restaurant_id": "rest-1",
        "item_id": "item-1",
        "quantity": 2,
        "unit_price": 15.0,
        "delivery_address": "456 Oak Lane"
    }

    response = client.post("/api/v1/orders/checkout", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "CONFIRMED"
    assert data["total_amount"] == 30.0
    assert data["reservation_id"] == "res-999"
    assert data["payment_id"] == "pay-999"
    assert data["delivery_task_id"] == "task-999"

    # Verify state machine logged every transition
    states = [log["to_state"] for log in data["state_logs"]]
    assert "PENDING" in states
    assert "STOCK_RESERVED" in states
    assert "PAID" in states
    assert "DELIVERY_ASSIGNED" in states
    assert "CONFIRMED" in states

@patch("services.order_service.src.saga_orchestrator.httpx.Client")
def test_order_checkout_payment_failure_compensation(mock_httpx):
    """
    Challenge 3C: Saga Compensation when payment fails at Step 2.
    Transitions: PENDING -> STOCK_RESERVED -> COMPENSATING_ROLLBACK -> FAILED_PAYMENT_REJECTED.
    Must issue compensating release call to Restaurant Service.
    """
    mock_client = MagicMock()
    mock_httpx.return_value.__enter__.return_value = mock_client

    # Step 1: Restaurant Reservation succeeds
    resp_res = MagicMock()
    resp_res.status_code = 201
    resp_res.json.return_value = {"id": "res-888", "status": "RESERVED"}

    # Step 2: Payment Charge Fails (e.g. Card Declined)
    resp_pay = MagicMock()
    resp_pay.status_code = 402
    resp_pay.json.return_value = {"error": {"message": "Card declined"}}

    # Compensation release succeeds
    resp_release = MagicMock()
    resp_release.status_code = 200

    mock_client.post.side_effect = [resp_res, resp_pay, resp_release]

    payload = {
        "customer_id": "cust-2",
        "restaurant_id": "rest-2",
        "item_id": "item-2",
        "quantity": 1,
        "unit_price": 25.0,
        "delivery_address": "789 Pine Road"
    }

    response = client.post("/api/v1/orders/checkout", json=payload)
    assert response.status_code == 402
    data = response.json()
    assert data["status"] == "FAILED_PAYMENT_REJECTED"
    assert data["failure_reason"] == "Card declined"

    states = [log["to_state"] for log in data["state_logs"]]
    assert "STOCK_RESERVED" in states
    assert "COMPENSATING_ROLLBACK" in states
    assert "FAILED_PAYMENT_REJECTED" in states

def test_order_idempotency_conflict():
    """
    BR3: Reusing checkout Idempotency-Key with different payload triggers 409 Conflict.
    """
    idem_key = "idemp-order-001"
    headers = {"Idempotency-Key": idem_key}
    payload1 = {
        "customer_id": "cust-3",
        "restaurant_id": "rest-3",
        "item_id": "item-3",
        "quantity": 1,
        "unit_price": 10.0,
        "delivery_address": "123 Main St"
    }

    with patch("services.order_service.src.saga_orchestrator.httpx.Client") as mock_httpx:
        mock_client = MagicMock()
        mock_httpx.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value.status_code = 201
        mock_client.post.return_value.json.return_value = {"id": "test-id"}

        # First checkout
        resp1 = client.post("/api/v1/orders/checkout", json=payload1, headers=headers)
        assert resp1.status_code == 201

        # Second checkout with DIFFERENT payload and SAME key
        payload2 = dict(payload1)
        payload2["quantity"] = 5  # tampered
        resp2 = client.post("/api/v1/orders/checkout", json=payload2, headers=headers)
        assert resp2.status_code == 409
        assert "already used with a different checkout payload" in resp2.json()["error"]["message"]
