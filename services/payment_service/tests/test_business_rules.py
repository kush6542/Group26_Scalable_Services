import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.payment_service.src.database import Base, get_db
from services.payment_service.src.main import app
from services.payment_service.src.models import PaymentTransaction

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
    assert response.json()["service"] == "payment_service"

def test_br2_payment_idempotency_replay():
    """
    BR2: Idempotent Payment Charge.
    Repeating the call with the same Idempotency-Key and matching payload must return
    the identical cached response and cause NO double deduction in the database.
    """
    idem_key = "idemp-pay-test-001"
    payload = {
        "order_id": "ord-100",
        "customer_id": "cust-200",
        "amount": 45.50,
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "card_number": "4111111111111111"
    }
    headers = {"Idempotency-Key": idem_key}

    # First Charge
    resp1 = client.post("/api/v1/payments/charge", json=payload, headers=headers)
    assert resp1.status_code == 201
    txn1_id = resp1.json()["id"]

    # Replay Call (Identical key and payload)
    resp2 = client.post("/api/v1/payments/charge", json=payload, headers=headers)
    assert resp2.status_code == 201
    assert resp2.headers.get("x-idempotent-replay") == "true"
    assert resp2.json()["id"] == txn1_id

    # Verify only ONE transaction exists in DB
    db = TestingSessionLocal()
    txns = db.query(PaymentTransaction).filter(PaymentTransaction.order_id == "ord-100").all()
    assert len(txns) == 1
    db.close()

def test_br3_payment_idempotency_payload_mismatch():
    """
    BR3: Reusing an Idempotency-Key with a different payload must return 409 Conflict.
    """
    idem_key = "idemp-pay-test-002"
    payload1 = {
        "order_id": "ord-201",
        "customer_id": "cust-201",
        "amount": 25.00,
        "currency": "USD"
    }
    headers = {"Idempotency-Key": idem_key}

    # First Charge
    resp1 = client.post("/api/v1/payments/charge", json=payload1, headers=headers)
    assert resp1.status_code == 201

    # Tampered Payload with SAME Idempotency-Key (amount changed to 999.00)
    payload2 = {
        "order_id": "ord-201",
        "customer_id": "cust-201",
        "amount": 999.00,
        "currency": "USD"
    }
    resp2 = client.post("/api/v1/payments/charge", json=payload2, headers=headers)
    assert resp2.status_code == 409
    assert "already used with a different request payload" in resp2.json()["error"]["message"]

def test_payment_decline_simulation():
    """
    Condition e & Saga Trigger: Card ending in 9999 triggers simulated card decline (402 Payment Required).
    """
    payload = {
        "order_id": "ord-301",
        "customer_id": "cust-301",
        "amount": 35.00,
        "card_number": "4111111111119999"  # Declining card
    }
    resp = client.post("/api/v1/payments/charge", json=payload)
    assert resp.status_code == 402
    assert "Card declined" in resp.json()["error"]["message"]

def test_refund_compensation():
    """
    Saga compensation refund endpoint restores payment state.
    """
    payload = {
        "order_id": "ord-401",
        "customer_id": "cust-401",
        "amount": 50.00
    }
    charge_resp = client.post("/api/v1/payments/charge", json=payload)
    assert charge_resp.status_code == 201
    payment_id = charge_resp.json()["id"]

    refund_resp = client.post(f"/api/v1/payments/{payment_id}/refund", json={"reason": "Customer cancellation"})
    assert refund_resp.status_code == 200
    assert refund_resp.json()["status"] == "REFUNDED"
