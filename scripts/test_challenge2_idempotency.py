import os
import sys
import uuid
import time
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

PAYMENT_URL = "http://localhost:8003"

def run_idempotency_challenge():
    print("=" * 70)
    print("   CHALLENGE 2: IDEMPOTENCY ENFORCEMENT & CONCURRENT REPLAY")
    print("=" * 70)

    order_id = f"ord-idemp-{uuid.uuid4().hex[:8]}"
    idem_key = f"key-{uuid.uuid4()}"
    base_payload = {
        "order_id": order_id,
        "customer_id": "cust-vip-101",
        "amount": 49.99,
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "card_number": "4111111111111111"
    }

    with httpx.Client(timeout=5.0) as client:
        # Phase 1: Initial Payment Request
        print("\nPhase 1: Submitting initial payment request...")
        r1 = client.post(
            f"{PAYMENT_URL}/api/v1/payments/charge",
            json=base_payload,
            headers={"Idempotency-Key": idem_key, "X-Correlation-ID": f"corr-init-{uuid.uuid4().hex[:6]}"}
        )
        assert r1.status_code == 201, f"Initial charge failed: {r1.text}"
        initial_data = r1.json()
        txn_id = initial_data["id"]
        print(f"  [✓] Initial Payment Succeeded: Status 201, Txn ID={txn_id}, Amount=${initial_data['amount']}")

        # Phase 2: Sequential Duplicate Call with Identical Payload
        print("\nPhase 2: Submitting identical duplicate request (Network Retry simulation)...")
        r2 = client.post(
            f"{PAYMENT_URL}/api/v1/payments/charge",
            json=base_payload,
            headers={"Idempotency-Key": idem_key, "X-Correlation-ID": f"corr-replay-{uuid.uuid4().hex[:6]}"}
        )
        assert r2.status_code == 201
        assert r2.headers.get("x-idempotent-replay") == "true", "Expected X-Idempotent-Replay header"
        replay_data = r2.json()
        assert replay_data["id"] == txn_id, "Replay transaction ID mismatch!"
        print(f"  [✓] Cached Response Replayed: Status 201, Header X-Idempotent-Replay=true")
        print(f"  [✓] Returned Txn ID matches original: {replay_data['id']} == {txn_id}")

        # Phase 3: Tampered Payload with SAME Idempotency Key (Conflict Test)
        print("\nPhase 3: Submitting tampered payload with the same Idempotency-Key...")
        tampered_payload = dict(base_payload)
        tampered_payload["amount"] = 999.99  # Attacker modified amount
        r3 = client.post(
            f"{PAYMENT_URL}/api/v1/payments/charge",
            json=tampered_payload,
            headers={"Idempotency-Key": idem_key, "X-Correlation-ID": f"corr-tamper-{uuid.uuid4().hex[:6]}"}
        )
        assert r3.status_code == 409, f"Expected 409 Conflict, got {r3.status_code}"
        print(f"  [✓] Tampered Payload Rejected: Status 409 Conflict")
        print(f"      Message: '{r3.json()['error']['message']}'")

        # Phase 4: Concurrent Duplicate Request Burst (Race Condition Test)
        print("\nPhase 4: Firing burst of 10 SIMULTANEOUS identical requests with a new key...")
        concurrent_key = f"key-burst-{uuid.uuid4()}"
        burst_order_id = f"ord-burst-{uuid.uuid4().hex[:8]}"
        burst_payload = dict(base_payload)
        burst_payload["order_id"] = burst_order_id
        burst_payload["amount"] = 75.00

        burst_results = []
        def fire_concurrent_request(idx):
            corr = f"corr-burst-{idx}-{uuid.uuid4().hex[:4]}"
            with httpx.Client(timeout=5.0) as b_client:
                res = b_client.post(
                    f"{PAYMENT_URL}/api/v1/payments/charge",
                    json=burst_payload,
                    headers={"Idempotency-Key": concurrent_key, "X-Correlation-ID": corr}
                )
                return res.status_code, res.headers.get("x-idempotent-replay")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fire_concurrent_request, i) for i in range(10)]
            for f in as_completed(futures):
                burst_results.append(f.result())

        print(f"  [✓] Burst Completed (10 parallel requests).")
        replays = [b for b in burst_results if b[1] == "true"]
        print(f"      - Original Execution: 1 call")
        print(f"      - Replay Hits: {len(replays)} calls")

        # Phase 5: Verify Database Records in Payment Service
        print("\nPhase 5: Verifying Database Integrity...")
        txns1 = client.get(f"{PAYMENT_URL}/api/v1/payments/order/{order_id}").json()
        assert len(txns1) == 1, f"Expected exactly 1 payment record for {order_id}, found {len(txns1)}"
        print(f"  [✓] Verified order {order_id} has EXACTLY 1 payment record in database (no double charge).")

        txns2 = client.get(f"{PAYMENT_URL}/api/v1/payments/order/{burst_order_id}").json()
        assert len(txns2) == 1, f"Expected exactly 1 payment record for burst order {burst_order_id}, found {len(txns2)}"
        print(f"  [✓] Verified burst order {burst_order_id} has EXACTLY 1 payment record despite 10 simultaneous hits.")

    print("\n" + "=" * 70)
    print("  [VERIFIED] Challenge 2 Idempotency: PASSED ALL CHECKS!")
    print("=" * 70)

if __name__ == "__main__":
    run_idempotency_challenge()
