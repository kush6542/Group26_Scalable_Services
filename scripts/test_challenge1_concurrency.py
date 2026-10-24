import os
import sys
import uuid
import time
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

RESTAURANT_URL = "http://localhost:8002"
INITIAL_STOCK = 5
PARALLEL_REQUESTS = 20

def run_concurrency_challenge():
    print("=" * 70)
    print("   CHALLENGE 1: CONCURRENCY CONTROL UNDER SIMULTANEOUS ACCESS")
    print("=" * 70)
    print(f"Goal: Fire {PARALLEL_REQUESTS} parallel threads against a contended resource with capacity {INITIAL_STOCK}.")
    print("Requirement: Exactly 5 succeed (HTTP 201), 15 fail (HTTP 409), final stock is 0.")
    print("-" * 70)

    # 1. Setup Test Restaurant & Limited Contended Item
    with httpx.Client(timeout=5.0) as client:
        res = client.post(
            f"{RESTAURANT_URL}/api/v1/restaurants",
            json={"name": "Flash Deal Biryani House", "address": "100 Concurrency Plaza"}
        )
        assert res.status_code == 201
        rest_id = res.json()["id"]

        dish = client.post(
            f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu",
            json={
                "name": "Flash Deal Royal Biryani",
                "price": 25.00,
                "available_quantity": INITIAL_STOCK
            }
        )
        assert dish.status_code == 201
        item_id = dish.json()["id"]

    print(f"[Setup] Created Dish '{dish.json()['name']}' (Item ID: {item_id})")
    print(f"[Setup] Initial Available Quantity: {INITIAL_STOCK}")
    print(f"\nLaunching {PARALLEL_REQUESTS} concurrent threads simultaneously...")

    results = []

    def make_reservation_request(req_idx):
        corr_id = f"corr-conc-{req_idx:02d}-{uuid.uuid4().hex[:6]}"
        order_id = f"ord-conc-{req_idx:02d}"
        payload = {
            "order_id": order_id,
            "restaurant_id": rest_id,
            "item_id": item_id,
            "quantity": 1
        }
        headers = {"X-Correlation-ID": corr_id}
        start_time = time.time()
        try:
            with httpx.Client(timeout=5.0) as worker_client:
                resp = worker_client.post(
                    f"{RESTAURANT_URL}/api/v1/restaurants/reservations",
                    json=payload,
                    headers=headers
                )
                duration_ms = (time.time() - start_time) * 1000
                return {
                    "idx": req_idx,
                    "status_code": resp.status_code,
                    "response": resp.json(),
                    "duration_ms": duration_ms
                }
        except Exception as e:
            return {"idx": req_idx, "status_code": 500, "error": str(e)}

    # Fire 20 parallel threads
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as executor:
        futures = [executor.submit(make_reservation_request, i + 1) for i in range(PARALLEL_REQUESTS)]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = (time.time() - t0) * 1000

    results.sort(key=lambda x: x["idx"])

    successes = [r for r in results if r["status_code"] == 201]
    conflicts = [r for r in results if r["status_code"] == 409]
    others = [r for r in results if r["status_code"] not in (201, 409)]

    print("\n--- Execution Results ---")
    for r in results:
        status_label = "SUCCESS (201)" if r["status_code"] == 201 else f"REJECTED ({r['status_code']})"
        msg = r["response"].get("status") if r["status_code"] == 201 else r["response"].get("error", {}).get("message")
        print(f"Request #{r['idx']:02d}: {status_label} in {r['duration_ms']:.1f}ms -> {msg}")

    print("\n--- Summary ---")
    print(f"Total Requests Dispatched: {PARALLEL_REQUESTS}")
    print(f"Successful Allocations:   {len(successes)} (Expected: {INITIAL_STOCK})")
    print(f"Rejected Out of Stock:    {len(conflicts)} (Expected: {PARALLEL_REQUESTS - INITIAL_STOCK})")
    print(f"Unexpected Failures:      {len(others)} (Expected: 0)")
    print(f"Total Burst Duration:     {total_time:.1f}ms")

    # Verify Final DB State
    with httpx.Client(timeout=5.0) as client:
        final_check = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{rest_id}/menu/{item_id}")
        final_stock = final_check.json()["available_quantity"]
        version = final_check.json()["version"]

    print(f"\n[Verification] Final Database Available Quantity: {final_stock}")
    print(f"[Verification] Final Database Item Version: {version}")

    assert len(successes) == INITIAL_STOCK, f"Expected {INITIAL_STOCK} successes, got {len(successes)}"
    assert len(conflicts) == (PARALLEL_REQUESTS - INITIAL_STOCK), f"Expected {PARALLEL_REQUESTS - INITIAL_STOCK} conflicts, got {len(conflicts)}"
    assert final_stock == 0, f"Expected final stock 0, got {final_stock}"

    print("\n[VERIFIED] Challenge 1 Concurrency Control: PASSED with ZERO OVER-ALLOCATION!")
    return {
        "total": PARALLEL_REQUESTS,
        "successes": len(successes),
        "conflicts": len(conflicts),
        "final_stock": final_stock,
        "results": results
    }

if __name__ == "__main__":
    run_concurrency_challenge()
