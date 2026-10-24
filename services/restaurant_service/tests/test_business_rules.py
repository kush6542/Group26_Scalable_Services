import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.restaurant_service.src.database import Base, get_db
from services.restaurant_service.src.main import app

# In-memory SQLite with StaticPool so all threads/sessions share the same in-memory DB
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
    assert response.json()["service"] == "restaurant_service"

def test_br1_stock_sufficiency_success():
    """
    BR1: Stock Sufficiency & Atomic Concurrency Control.
    Ensure that requesting valid stock succeeds and decrements available quantity.
    """
    # 1. Create Restaurant
    res_resp = client.post("/api/v1/restaurants", json={"name": "Biryani House", "address": "123 Food St"})
    assert res_resp.status_code == 201
    rest_id = res_resp.json()["id"]

    # 2. Add Menu Item with stock 10
    item_resp = client.post(
        f"/api/v1/restaurants/{rest_id}/menu",
        json={"name": "Special Mutton Biryani", "price": 18.5, "available_quantity": 10}
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]

    # 3. Reserve 4 units
    reserve_resp = client.post(
        "/api/v1/restaurants/reservations",
        json={"order_id": "ord-001", "restaurant_id": rest_id, "item_id": item_id, "quantity": 4}
    )
    assert reserve_resp.status_code == 201
    assert reserve_resp.json()["quantity"] == 4
    assert reserve_resp.json()["status"] == "RESERVED"

    # 4. Verify updated stock is 6
    item_check = client.get(f"/api/v1/restaurants/{rest_id}/menu/{item_id}")
    assert item_check.json()["available_quantity"] == 6

def test_br1_stock_sufficiency_insufficient():
    """
    BR1: When requested quantity exceeds available stock, rejection with 409 Conflict occurs.
    """
    res_resp = client.post("/api/v1/restaurants", json={"name": "Burger Joint", "address": "456 Burger Way"})
    assert res_resp.status_code == 201
    rest_id = res_resp.json()["id"]

    item_resp = client.post(
        f"/api/v1/restaurants/{rest_id}/menu",
        json={"name": "Gourmet Cheeseburger", "price": 12.0, "available_quantity": 2}
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]

    # Attempt to reserve 5 when only 2 available
    reserve_resp = client.post(
        "/api/v1/restaurants/reservations",
        json={"order_id": "ord-002", "restaurant_id": rest_id, "item_id": item_id, "quantity": 5}
    )
    assert reserve_resp.status_code == 409
    assert "Stock insufficient" in reserve_resp.json()["error"]["message"]

    # Verify stock remained untouched at 2
    item_check = client.get(f"/api/v1/restaurants/{rest_id}/menu/{item_id}")
    assert item_check.json()["available_quantity"] == 2

def test_saga_compensation_release():
    """
    Challenge 3C: Saga compensating action must safely restore stock.
    """
    res_resp = client.post("/api/v1/restaurants", json={"name": "Pizza Corner", "address": "789 Italy Blvd"})
    assert res_resp.status_code == 201
    rest_id = res_resp.json()["id"]

    item_resp = client.post(
        f"/api/v1/restaurants/{rest_id}/menu",
        json={"name": "Truffle Pizza", "price": 20.0, "available_quantity": 5}
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]

    # Reserve 3 units (leaving 2)
    reserve_resp = client.post(
        "/api/v1/restaurants/reservations",
        json={"order_id": "ord-003", "restaurant_id": rest_id, "item_id": item_id, "quantity": 3}
    )
    assert reserve_resp.status_code == 201
    res_id = reserve_resp.json()["id"]

    item_check1 = client.get(f"/api/v1/restaurants/{rest_id}/menu/{item_id}")
    assert item_check1.json()["available_quantity"] == 2

    # Trigger compensation release
    release_resp = client.post(f"/api/v1/restaurants/reservations/{res_id}/release")
    assert release_resp.status_code == 200
    assert release_resp.json()["status"] == "RELEASED"

    # Verify stock is fully restored to 5
    item_check2 = client.get(f"/api/v1/restaurants/{rest_id}/menu/{item_id}")
    assert item_check2.json()["available_quantity"] == 5
