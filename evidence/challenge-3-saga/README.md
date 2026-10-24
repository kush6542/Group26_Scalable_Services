# Challenge 3C Evidence: Orchestrated Saga with Compensation

## 1. Problem Statement & Motivation
Under the strict **Database-per-Service** pattern, each microservice owns its private database. Cross-database distributed ACID transactions (e.g. 2-Phase Commit / 2PC) are notoriously slow, fragile, and create tight locking dependencies across network boundaries.

To maintain eventual business consistency across Restaurant, Payment, Delivery, and Notification services, FoodFlow implements an **Orchestrated Saga Pattern**.

## 2. Architecture & Explicit State Machine
The `Order Service` functions as the centralized **Saga Orchestrator**. The order lifecycle is governed by an explicit state machine:

```
[NONE] ──> [PENDING] ──> [STOCK_RESERVED] ──> [PAID] ──> [DELIVERY_ASSIGNED] ──> [CONFIRMED]
                              │                  │              │
                              ▼ (Step 2 Fails)   ▼              ▼ (Step 3 Fails)
                    [COMPENSATING_ROLLBACK]  ◄───┴──────────────┘
                              │
                    ┌─────────┴─────────────────────┐
                    ▼                               ▼
       [FAILED_PAYMENT_REJECTED]        [FAILED_NO_RIDER_AVAILABLE]
```

### Steps & Compensations
| Step | Action | Service | Compensating Action on Failure |
| :--- | :--- | :--- | :--- |
| **Step 1** | Reserve Item Stock | Restaurant Service | `POST /api/v1/restaurants/reservations/{id}/release` (restores stock) |
| **Step 2** | Charge Payment | Payment Service | `POST /api/v1/payments/{id}/refund` (refunds money) |
| **Step 3** | Assign Delivery Rider | Delivery Service | `POST /api/v1/deliveries/tasks/{id}/cancel` (frees rider back to AVAILABLE) |
| **Step 4** | Confirm & Notify | Restaurant & Notification Services | Finalize reservation permanently & dispatch confirmation SMS |

## 3. Test Script & Repeatable Verification
* **Script**: `scripts/test_challenge3_saga.py`
* **Observed Output**: [saga_run_output.txt](saga_run_output.txt)

### Demonstrated Scenarios:
1. **Scenario 1 (Happy Path)**:
   * State progression: `NONE` $\rightarrow$ `PENDING` $\rightarrow$ `STOCK_RESERVED` $\rightarrow$ `PAID` $\rightarrow$ `DELIVERY_ASSIGNED` $\rightarrow$ `CONFIRMED`.
   * Menu dish stock decrements from 10 to 8. Order status: `CONFIRMED`.
2. **Scenario 2 (Payment Failure at Step 2)**:
   * Forced card decline (card ending in `9999`).
   * State progression: `PENDING` $\rightarrow$ `STOCK_RESERVED` $\rightarrow$ `COMPENSATING_ROLLBACK` $\rightarrow$ `FAILED_PAYMENT_REJECTED`.
   * **Verification**: Orchestrator releases stock reservation. Stock is restored from 5 back to 8 in the Restaurant Service database. No phantom inventory loss!
3. **Scenario 3 (Delivery Failure at Step 3)**:
   * All riders saturated/busy.
   * State progression: `PENDING` $\rightarrow$ `STOCK_RESERVED` $\rightarrow$ `PAID` $\rightarrow$ `COMPENSATING_ROLLBACK` $\rightarrow$ `FAILED_NO_RIDER_AVAILABLE`.
   * **Verification**: Double-compensation executed:
     1. Payment automatically refunded in Payment Service database (`status = "REFUNDED"`).
     2. Stock reservation released in Restaurant Service database (`status = "RELEASED"`).
     3. System ends in complete data consistency across all databases.
