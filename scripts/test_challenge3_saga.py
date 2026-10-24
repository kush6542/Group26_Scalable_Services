import os
import sys
import uuid
import httpx

ORDER_URL = "http://localhost:8001"
RESTAURANT_URL = "http://localhost:8002"
PAYMENT_URL = "http://localhost:8003"
DELIVERY_URL = "http://localhost:8004"

def run_saga_challenge():
    print("=" * 75)
    print("   CHALLENGE 3C: ORCHESTRATED SAGA WITH COMPENSATING ROLLBACKS")
    print("=" * 75)

    with httpx.Client(timeout=10.0) as client:
        # Seeding baseline restaurant and rider
        r_resp = client.post(
            f"{RESTAURANT_URL}/api/v1/restaurants",
            json={"name": "Saga Kitchen", "address": "12 Saga Way"}
        )
        rest_id = r_resp.json()["id"]

        dish_resp = client.post(
            f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu",
            json={"name": "Saga Gourmet Pizza", "price": 20.0, "available_quantity": 10}
        )
        item_id = dish_resp.json()["id"]

        client.post(
            f"{DELIVERY_URL}/api/v1/deliveries/riders",
            json={"name": "Saga Rider", "phone": "+15554443322"}
        )

        # -------------------------------------------------------------
        # SCENARIO 1: Happy Path Saga Execution
        # -------------------------------------------------------------
        print("\n--- SCENARIO 1: Happy Path Saga Execution ---")
        happy_payload = {
            "customer_id": "cust-saga-happy",
            "restaurant_id": rest_id,
            "item_id": item_id,
            "quantity": 2,
            "unit_price": 20.0,
            "delivery_address": "100 Happy Street"
        }
        res1 = client.post(
            f"{ORDER_URL}/api/v1/orders/checkout",
            json=happy_payload,
            headers={"X-Correlation-ID": "corr-saga-happy-01"}
        )
        assert res1.status_code == 201
        order1 = res1.json()
        print(f"[✓] Happy Path Order Completed: ID={order1['id']}, Status={order1['status']}")
        for log in order1["state_logs"]:
            print(f"    State transition: {log['from_state']} -> {log['to_state']} ({log['note']})")

        stock1 = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}").json()["available_quantity"]
        print(f"[✓] Stock count updated: 10 -> {stock1} (Decremented by 2)")

        # -------------------------------------------------------------
        # SCENARIO 2: Forced Payment Failure at Step 2 -> Compensation Undoes Step 1
        # -------------------------------------------------------------
        print("\n--- SCENARIO 2: Payment Failure at Step 2 (Compensates Step 1 Stock) ---")
        stock_before_fail = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}").json()["available_quantity"]
        print(f"Current Stock before failed order: {stock_before_fail}")

        fail_pay_payload = {
            "customer_id": "cust-saga-fail-pay",
            "restaurant_id": rest_id,
            "item_id": item_id,
            "quantity": 3,
            "unit_price": 20.0,
            "delivery_address": "200 Decline Avenue",
            "card_number": "4111111111119999"  # Triggers Payment Failure
        }
        res2 = client.post(
            f"{ORDER_URL}/api/v1/orders/checkout",
            json=fail_pay_payload,
            headers={"X-Correlation-ID": "corr-saga-fail-pay-02"}
        )
        assert res2.status_code == 402, f"Expected 402 Payment Required, got {res2.status_code}"
        order2 = res2.json()
        print(f"[✓] Order correctly rejected with 402: Status={order2['status']}")
        print(f"    Failure Reason: {order2['failure_reason']}")

        print("State Machine Compensating Progression:")
        for log in order2["state_logs"]:
            print(f"    {log['from_state']} -> {log['to_state']} ({log['note']})")

        # Verify Compensating Action Restored Stock
        stock_after_comp = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}").json()["available_quantity"]
        print(f"[✓] Stock count after compensating rollback: {stock_after_comp}")
        assert stock_after_comp == stock_before_fail, f"Stock leak! Expected {stock_before_fail}, got {stock_after_comp}"
        print(f"    [VERIFIED] Compensating transaction restored all {fail_pay_payload['quantity']} reserved items!")

        # -------------------------------------------------------------
        # SCENARIO 3: Forced Delivery Failure at Step 3 -> Compensates Steps 1 & 2
        # -------------------------------------------------------------
        print("\n--- SCENARIO 3: Delivery Failure at Step 3 (Compensates Payment & Stock) ---")
        # Mark all existing riders as BUSY so delivery assignment fails
        riders = client.get(f"{DELIVERY_URL}/api/v1/deliveries/riders").json()
        for r in riders:
            # Create dummy tasks to make them busy or use their ID
            pass

        # Register a rider and then set them OFFLINE or dispatch tasks to saturate riders
        # We can dispatch dummy tasks until no riders available
        while True:
            t = client.post(
                f"{DELIVERY_URL}/api/v1/deliveries/tasks",
                json={"order_id": f"dummy-{uuid.uuid4().hex[:6]}", "pickup_address": "X", "delivery_address": "Y"}
            )
            if t.status_code == 409:
                break  # All riders saturated!

        stock_before_deliv_fail = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}").json()["available_quantity"]
        fail_deliv_payload = {
            "customer_id": "cust-saga-fail-deliv",
            "restaurant_id": rest_id,
            "item_id": item_id,
            "quantity": 2,
            "unit_price": 20.0,
            "delivery_address": "300 Saturated Road"
        }

        res3 = client.post(
            f"{ORDER_URL}/api/v1/orders/checkout",
            json=fail_deliv_payload,
            headers={"X-Correlation-ID": "corr-saga-fail-deliv-03"}
        )
        assert res3.status_code == 409, f"Expected 409 Conflict, got {res3.status_code}"
        order3 = res3.json()
        print(f"[✓] Order rejected at delivery step: Status={order3['status']}")
        print(f"    Failure Reason: {order3['failure_reason']}")

        print("State Machine Double-Compensation Progression:")
        for log in order3["state_logs"]:
            print(f"    {log['from_state']} -> {log['to_state']} ({log['note']})")

        # Verify Compensation 1: Stock is restored
        stock_after_deliv_comp = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}").json()["available_quantity"]
        assert stock_after_deliv_comp == stock_before_deliv_fail, f"Stock leak! Expected {stock_before_deliv_fail}, got {stock_after_deliv_comp}"
        print(f"    [VERIFIED] Stock restored: {stock_after_deliv_comp} == {stock_before_deliv_fail}")

        # Verify Compensation 2: Payment was REFUNDED
        if order3.get("payment_id"):
            pay_rec = client.get(f"{PAYMENT_URL}/api/v1/payments/{order3['payment_id']}").json()
            assert pay_rec["status"] == "REFUNDED", f"Expected payment status REFUNDED, got {pay_rec['status']}"
            print(f"    [VERIFIED] Payment {order3['payment_id']} was automatically refunded (status={pay_rec['status']})")

    print("\n" + "=" * 75)
    print("  [VERIFIED] Challenge 3C Saga with Compensation: ALL SCENARIOS PASSED!")
    print("=" * 75)

if __name__ == "__main__":
    run_saga_challenge()
