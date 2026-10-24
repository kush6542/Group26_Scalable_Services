# Challenge 2 Evidence: Idempotency Enforcement

## 1. Problem Statement
In distributed networks, HTTP client calls are prone to transient packet drops, gateway timeouts, and accidental double-clicks by users. If a customer clicks "Pay" twice, or if an automated client retries a payment because an ACK packet was delayed, the payment service must not charge the customer a second time.

## 2. Design & Implementation
FoodFlow implements an **Idempotency Guarantee** across all unsafe endpoints (`POST /api/v1/payments/charge` and `POST /api/v1/orders/checkout`) using the `Idempotency-Key` header:

1. **Payload Fingerprinting**:
   The service extracts the JSON request body and computes a deterministic SHA-256 fingerprint:
   ```python
   raw_payload_json = json.dumps(payload_dict, sort_keys=True)
   req_hash = hashlib.sha256(raw_payload_json.encode("utf-8")).hexdigest()
   ```
2. **Database Idempotency Store (`idempotency_records`)**:
   Tracks `key`, `request_hash`, `status` (`IN_PROGRESS` / `COMPLETED`), `response_code`, and `response_body`.
3. **Behavioral Guarantees**:
   * **BR2 (Identical Replay)**: If `key` exists and `request_hash` matches:
     * If `status == "COMPLETED"`, the cached response is immediately returned with header `X-Idempotent-Replay: true`. The underlying database undergoes zero secondary modifications.
   * **BR3 (Payload Mismatch Rejection)**: If `key` exists but `request_hash` differs (e.g. attacker reuses key with altered payment amount), the server rejects the call with `HTTP 409 Conflict` (`"Idempotency key already used with a different request payload"`).
   * **Concurrent Duplicate Bursts**: A unique constraint on `idempotency_records.key` ensures that two simultaneous identical requests arriving within the exact same millisecond cannot both execute. The first thread acquires the record; the second thread hits the unique constraint, backs off, and awaits/replays the cached result.

## 3. Test Script & Repeatable Verification
* **Script**: `scripts/test_challenge2_idempotency.py`
* **Observed Output**: [idempotency_run_output.txt](idempotency_run_output.txt)
  * **Phase 1**: Initial payment succeeds with `HTTP 201 Created` (Txn ID returned).
  * **Phase 2**: Replay call with matching key and payload returns cached response with `HTTP 201`, matching Txn ID, and `X-Idempotent-Replay: true`.
  * **Phase 3**: Tampered payload call with same key returns `HTTP 409 Conflict`.
  * **Phase 4**: Burst of 10 simultaneous identical requests fired in parallel across 10 threads; 1 executed original charge, 9 replayed cached response.
  * **Phase 5**: Database audit verifies **EXACTLY 1 payment record** was created for both single-order and burst scenarios.
