# Testing Evidence & Verification

## 1. Testing Strategy
FoodFlow follows a multi-tiered testing strategy:
1. **Unit Testing of Business Rules**:
   - Each core business rule (`BR1` to `BR5`) is isolated and verified using `pytest` and FastAPI's `TestClient` with in-memory SQLite (`StaticPool`).
   - All tests run hermetically without external dependencies.
2. **End-to-End Integration Testing**:
   - `scripts/test_e2e_flow.py` verifies the entire distributed multi-service checkout lifecycle across the 5 independently running microservices.

## 2. Business Rules Traceability Matrix

| Rule ID | Service | Description | Code Location | Unit Test |
| :--- | :--- | :--- | :--- | :--- |
| **BR1** | Restaurant Service | Stock Sufficiency & Atomic Concurrency | `services/restaurant_service/src/main.py:reserve_stock` | `services/restaurant_service/tests/test_business_rules.py::test_br1_stock_sufficiency_*` |
| **BR2** | Payment Service | Idempotent Replay on Identical Request | `services/payment_service/src/main.py:charge_payment` | `services/payment_service/tests/test_business_rules.py::test_br2_payment_idempotency_replay` |
| **BR3** | Payment Service | Idempotency Rejection on Tampered Payload | `services/payment_service/src/main.py:charge_payment` | `services/payment_service/tests/test_business_rules.py::test_br3_payment_idempotency_payload_mismatch` |
| **BR4** | Payment Service | Amount & Card Validity Checks | `services/payment_service/src/main.py:charge_payment` | `services/payment_service/tests/test_business_rules.py::test_payment_decline_simulation` |
| **BR5** | Delivery Service | Rider Availability Constraint | `services/delivery_service/src/main.py:dispatch_delivery` | `services/delivery_service/tests/test_business_rules.py::test_br5_rider_assignment_*` |
| **BR6** | Order Service | Saga Orchestrated Happy Path | `services/order_service/src/saga_orchestrator.py` | `services/order_service/tests/test_business_rules.py::test_order_checkout_happy_path_saga` |
| **BR7** | Order Service | Saga Rollback Compensation on Payment Failure | `services/order_service/src/saga_orchestrator.py` | `services/order_service/tests/test_business_rules.py::test_order_checkout_payment_failure_compensation` |

## 3. Evidence Log Files
* [pytest_results.txt](pytest_results.txt): Full test run proving 20/20 unit tests pass.
* [e2e_flow_run.txt](e2e_flow_run.txt): End-to-end execution log proving live inter-service orchestration.
