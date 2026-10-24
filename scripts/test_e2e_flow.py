import sys
import uuid
import httpx

BASE_URLS = {
    "order": "http://localhost:8001",
    "restaurant": "http://localhost:8002",
    "payment": "http://localhost:8003",
    "delivery": "http://localhost:8004",
    "notification": "http://localhost:8005",
}

def run_e2e_test():
    print("=" * 60)
    print("   FoodFlow End-to-End Main Transaction Verification")
    print("=" * 60)

    corr_id = f"e2e-{uuid.uuid4()}"
    headers = {"X-Correlation-ID": corr_id}

    with httpx.Client(timeout=10.0) as client:
        # Step 0: Verify Health of all 5 services
        print("\n1. Verifying Health of all 5 services...")
        for name, base_url in BASE_URLS.items():
            r = client.get(f"{base_url}/health", headers=headers)
            assert r.status_code == 200, f"{name} health check failed"
            print(f"   [✓] {name}_service is UP ({r.json()['status']})")

        # Step 1: Create Restaurant and Add Menu Dish
        print("\n2. Seeding Restaurant & Menu Catalog...")
        res_resp = client.post(
            f"{BASE_URLS['restaurant']}/api/v1/restaurants",
            json={"name": "Taj Biryani Kitchen", "address": "42 Spice Road"},
            headers=headers
        )
        assert res_resp.status_code == 201
        rest_id = res_resp.json()["id"]
        print(f"   [✓] Created Restaurant: '{res_resp.json()['name']}' (ID: {rest_id})")

        dish_resp = client.post(
            f"{BASE_URLS['restaurant']}/api/v1/restaurants/{rest_id}/menu",
            json={
                "name": "Hyderabadi Dum Biryani",
                "price": 14.50,
                "available_quantity": 20
            },
            headers=headers
        )
        assert dish_resp.status_code == 201
        item_id = dish_resp.json()["id"]
        print(f"   [✓] Added Menu Item: '{dish_resp.json()['name']}' (Qty: 20, Price: $14.50)")

        # Step 2: Register Delivery Rider
        print("\n3. Registering Delivery Rider...")
        rider_resp = client.post(
            f"{BASE_URLS['delivery']}/api/v1/deliveries/riders",
            json={"name": "Dave Courier", "phone": "+19998887777", "vehicle_type": "MOTORBIKE"},
            headers=headers
        )
        assert rider_resp.status_code == 201
        rider_id = rider_resp.json()["id"]
        print(f"   [✓] Registered Rider: '{rider_resp.json()['name']}' (Status: {rider_resp.json()['status']})")

        # Step 3: Execute Customer Checkout (Saga Spanning 4 Services)
        print("\n4. Customer Initiates Order Checkout (Multi-Service Saga)...")
        checkout_payload = {
            "customer_id": "cust-e2e-user",
            "restaurant_id": rest_id,
            "item_id": item_id,
            "quantity": 2,
            "unit_price": 14.50,
            "delivery_address": "888 Tech Boulevard, Apt 4B",
            "pickup_address": "42 Spice Road"
        }
        order_resp = client.post(
            f"{BASE_URLS['order']}/api/v1/orders/checkout",
            json=checkout_payload,
            headers={"X-Correlation-ID": corr_id, "Idempotency-Key": f"e2e-order-{uuid.uuid4()}"}
        )
        assert order_resp.status_code == 201, f"Checkout failed: {order_resp.text}"
        order = order_resp.json()
        print(f"   [✓] Order Placed & Confirmed: ID={order['id']}")
        print(f"       - Status: {order['status']}")
        print(f"       - Total: ${order['total_amount']}")
        print(f"       - Stock Reservation ID: {order['reservation_id']}")
        print(f"       - Payment ID: {order['payment_id']}")
        print(f"       - Delivery Task ID: {order['delivery_task_id']}")

        # Step 4: Verify Post-Checkout State in All Services
        print("\n5. Verifying Database Consistency Across Microservices...")
        # Check stock reduced from 20 to 18
        dish_check = client.get(f"{BASE_URLS['restaurant']}/api/v1/restaurants/{rest_id}/menu/{item_id}")
        assert dish_check.json()["available_quantity"] == 18
        print(f"   [✓] Restaurant Stock updated: 20 -> 18 (Decremented by 2)")

        # Check Payment Transaction is SUCCESS
        pay_check = client.get(f"{BASE_URLS['payment']}/api/v1/payments/{order['payment_id']}")
        assert pay_check.json()["status"] == "SUCCESS"
        print(f"   [✓] Payment Service confirmed transaction status: SUCCESS")

        # Check Delivery Task is ASSIGNED
        task_check = client.get(f"{BASE_URLS['delivery']}/api/v1/deliveries/tasks/{order['delivery_task_id']}")
        assert task_check.json()["status"] == "ASSIGNED"
        print(f"   [✓] Delivery Task confirmed status: ASSIGNED")

        # Check Notification was dispatched
        notifs = client.get(f"{BASE_URLS['notification']}/api/v1/notifications/order/{order['id']}")
        assert len(notifs.json()) >= 1
        print(f"   [✓] Notification Service recorded dispatch: '{notifs.json()[0]['message']}'")

        # Step 5: Check State Transitions Lifecycle in Order Service
        print("\n6. Order State Machine Transition History:")
        for log in order["state_logs"]:
            print(f"   - {log['from_state']} -> {log['to_state']} ({log['note']})")

    print("\n" + "=" * 60)
    print("  [SUCCESS] END-TO-END FLOW COMPLETED ALL CHECKS PERFECTLY")
    print("=" * 60)

if __name__ == "__main__":
    run_e2e_test()
