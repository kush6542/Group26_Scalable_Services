# FoodFlow: Scalable Microservices Architecture (Group 26)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Unit Tests](https://img.shields.io/badge/tests-20%2F20%20passed-brightgreen.svg)]()

> **Course**: Scalable Services (SEZG583) | MTech  
> **Assignment 1**: Design and Development of a Microservices Application  
> **Group**: Group 26  

---

## 1. System Overview

**FoodFlow** is a distributed microservices platform for on-demand food delivery designed for high concurrency, fault isolation, and eventual consistency.

The system is decomposed into **5 independent services** communicating exclusively over HTTP REST. Each service implements the **Database-per-Service** pattern with its own isolated database, schema, and credentials, eliminating distributed locks or shared tables.

```
                           ┌───────────────────────────┐
                           │   Client / Test Scripts   │
                           └─────────────┬─────────────┘
                                         │ HTTP REST (/api/v1/orders/checkout)
                                         ▼
                            ┌────────────────────────┐
                            │     Order Service      │ (Port 8001 | orders.db)
                            │   (Saga Orchestrator)  │
                            └────┬───────┬───────┬───┘
          POST /reservations     │       │       │ POST /tasks
     ┌───────────────────────────┘       │       └───────────────────────────┐
     ▼                                   ▼ POST /charge                      ▼
┌─────────────────────────┐   ┌───────────────────────┐   ┌──────────────────────────┐
│   Restaurant Service    │   │    Payment Service    │   │     Delivery Service     │
│ (Port 8002 | rest.db)   │   │ (Port 8003 | pay.db)  │   │  (Port 8004 | deliv.db)  │
└─────────────────────────┘   └───────────┬───────────┘   └──────────────────────────┘
                                          │ POST /send
                                          ▼
                              ┌───────────────────────┐
                              │ Notification Service  │
                              │ (Port 8005 | notif.db)│
                              └───────────────────────┘
```

---

## 2. Service Inventory & Port Allocations

| Service Name | Port | Database | Primary Responsibility | Contended / Unsafe Resource |
| :--- | :---: | :---: | :--- | :--- |
| **Order Service** | `8001` | `orders.db` | Order orchestration & state machine | Unsafe order placement |
| **Restaurant Service** | `8002` | `restaurant.db`| Menus, catalog, & stock reservations | **Contended dish inventory** |
| **Payment Service** | `8003` | `payment.db` | Charges, refunds, idempotency store | **Unsafe payment transactions** |
| **Delivery Service** | `8004` | `delivery.db` | Rider registry & task dispatching | Driver availability pool |
| **Notification Service**| `8005`| `notification.db`| SMS/Email/Push alerts (Mock) | Downstream gateway simulator |

Interactive OpenAPI Swagger documentation is available on each service at `http://localhost:<PORT>/docs`.

---

## 3. Mandatory Engineering Challenges

### Challenge 1: Concurrency Control (Mandatory)
* **The Problem**: High-demand food items can be over-allocated if multiple requests arrive simultaneously.
* **Our Solution**: Atomic conditional SQL update (`UPDATE menu_items SET available_quantity = available_quantity - :qty, version = version + 1 WHERE id = :item_id AND available_quantity >= :qty`).
* **Test Script**: `scripts/test_challenge1_concurrency.py` fires 20 parallel threads against a dish with capacity 5. Exactly 5 succeed, 15 are rejected with `HTTP 409 Conflict`, and final database stock is verified at 0.
* **Evidence**: See [evidence/challenge-1-concurrency/README.md](evidence/challenge-1-concurrency/README.md).

### Challenge 2: Idempotency Enforcement (Mandatory)
* **The Problem**: Unsafe operations (payments and checkout orders) must never result in duplicate deductions or phantom orders when clients retry.
* **Our Solution**: Header `Idempotency-Key` + SHA-256 payload fingerprinting + response cache + database unique constraint preventing concurrent duplicate execution. Mismatched payload returns `HTTP 409 Conflict`.
* **Test Script**: `scripts/test_challenge2_idempotency.py` tests initial call, replay, payload alteration, and 10 parallel simultaneous hits.
* **Evidence**: See [evidence/challenge-2-idempotency/README.md](evidence/challenge-2-idempotency/README.md).

### Challenge 3C: Orchestrated Saga with Compensation (Chosen Elective)
* **The Problem**: In a Database-per-Service architecture, distributed ACID transactions (2PC) are unavailable. Partial failures leave orphan data.
* **Our Solution**: Orchestrated Saga in Order Service with explicit states (`PENDING`, `STOCK_RESERVED`, `PAID`, `DELIVERY_ASSIGNED`, `CONFIRMED`, `COMPENSATING_ROLLBACK`, `FAILED_PAYMENT_REJECTED`, `FAILED_NO_RIDER_AVAILABLE`).
  * If payment fails: Order Service calls Restaurant Service to release reserved stock.
  * If delivery fails: Order Service refunds payment AND releases reserved stock.
* **Test Script**: `scripts/test_challenge3_saga.py` tests both happy path and failure compensation paths.
* **Evidence**: See [evidence/challenge-3-saga/README.md](evidence/challenge-3-saga/README.md).

---

## 4. Business Rules Traceability

| Rule ID | Service | Rule Summary | Test Location |
| :--- | :--- | :--- | :--- |
| **BR1** | Restaurant | Stock sufficiency: cannot reserve > available stock; atomic update prevents race conditions. | `services/restaurant_service/tests/test_business_rules.py` |
| **BR2** | Payment | Idempotency replay: identical key + payload returns cached response with no duplicate charge. | `services/payment_service/tests/test_business_rules.py` |
| **BR3** | Payment | Idempotency conflict: identical key with modified payload triggers `HTTP 409 Conflict`. | `services/payment_service/tests/test_business_rules.py` |
| **BR4** | Payment | Card & amount validity: amounts $\le 0$ or card ending in `9999` triggers decline (`HTTP 402`). | `services/payment_service/tests/test_business_rules.py` |
| **BR5** | Delivery | Rider availability: tasks only assignable to `AVAILABLE` riders; busy returns `HTTP 409`. | `services/delivery_service/tests/test_business_rules.py` |
| **BR6** | Order | Saga progression: successful multi-service order completes all steps into `CONFIRMED`. | `services/order_service/tests/test_business_rules.py` |
| **BR7** | Order | Saga compensation: payment decline triggers stock restoration and sets order to `FAILED`. | `services/order_service/tests/test_business_rules.py` |

---

## 5. Quickstart & How to Run

### Prerequisites
* Python 3.10+
* Git

### Step 1: Clone and Set Up Virtual Environment
```bash
git clone https://github.com/kush6542/Group26_Scalable_Services.git
cd Group26_Scalable_Services

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy httpx pydantic pytest
```

### Step 2: Run All 5 Services
We provide an automated orchestrator runner that launches all 5 services concurrently and validates their `/health` checks:
```bash
python3 scripts/run_all_services.py
```
*(Leave this running in terminal window 1).*

### Step 3: Run Unit Tests
In a second terminal window (with `.venv` activated):
```bash
pytest services/
```
Output:
```text
======================== 20 passed, 1 warning in 0.38s =========================
```

### Step 4: Run Challenge & End-to-End Verification Scripts
With all services running:
```bash
# 1. Run Main End-to-End Business Flow:
python3 scripts/test_e2e_flow.py

# 2. Run Challenge 1 (Concurrency Control - 20 parallel requests against 5 items):
python3 scripts/test_challenge1_concurrency.py

# 3. Run Challenge 2 (Idempotency Replay, Tampering, and Parallel Bursts):
python3 scripts/test_challenge2_idempotency.py

# 4. Run Challenge 3C (Saga Happy Path & Multi-Step Compensating Rollbacks):
python3 scripts/test_challenge3_saga.py
```

---

## 6. Repository Layout

```text
Group26_Scalable_Services/
├── README.md                           # This guide
├── pytest.ini                          # Pytest configuration
├── docs/                               # Diagrams, OpenAPI JSON specs, design report
│   ├── openapi/
│   │   ├── order_service_openapi.json
│   │   ├── restaurant_service_openapi.json
│   │   ├── payment_service_openapi.json
│   │   ├── delivery_service_openapi.json
│   │   └── notification_service_openapi.json
│   └── FoodFlow_Design_Report.md
├── services/
│   ├── order_service/                  # Port 8001
│   │   ├── src/ (main.py, saga_orchestrator.py, models.py, schemas.py, config.py)
│   │   ├── tests/ (test_business_rules.py)
│   │   ├── requirements.txt
│   │   └── .env.example
│   ├── restaurant_service/             # Port 8002
│   ├── payment_service/                # Port 8003
│   ├── delivery_service/               # Port 8004
│   └── notification_service/           # Port 8005
├── scripts/
│   ├── run_all_services.py             # Single command service runner with health checks
│   ├── export_openapi.py               # Exports OpenAPI specifications
│   ├── test_e2e_flow.py                # End-to-End lifecycle test
│   ├── test_challenge1_concurrency.py  # Concurrency verification script
│   ├── test_challenge2_idempotency.py  # Idempotency verification script
│   └── test_challenge3_saga.py         # Saga compensation verification script
└── evidence/
    ├── challenge-1-concurrency/        # Output logs and explanatory README
    ├── challenge-2-idempotency/
    ├── challenge-3-saga/
    └── tests/
```

---

## 7. Pre-Submission Checklist

- [x] Fresh clone runs by following the `README.md` only
- [x] 5 independent services, each with its own database, credentials, and configuration
- [x] Zero cross-database queries or foreign keys
- [x] Every service exposes `GET /health` and OpenAPI specification
- [x] 7 traceable business rules mapped directly to code and unit tests (20/20 passing)
- [x] Challenge 1 (Concurrency Control) verified with 20 parallel threads against 5 stock units
- [x] Challenge 2 (Idempotency) verified with cached replays, payload tampering rejection, and concurrent bursts
- [x] Challenge 3C (Saga with Compensation) verified with multi-step rollbacks upon payment and delivery failures
- [x] Structured logs propagate `X-Correlation-ID` across all services
- [x] Deliverable report outline, sequence diagrams, and video demo script included in `docs/`
