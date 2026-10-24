# FoodFlow: Project State & Session Handover Document

> **Course**: Scalable Services (SEZG583) | MTech  
> **Team**: Group 26  
> **Repository**: [https://github.com/kush6542/Group26_Scalable_Services](https://github.com/kush6542/Group26_Scalable_Services)  
> **Date of Last Update**: October 2026  
> **Current Version**: v1.0.0 (Assignment 1 Complete)

---

## 1. Executive Summary & Architecture Overview

**FoodFlow** is a distributed on-demand food delivery platform built in Python using **FastAPI**, **SQLAlchemy 2.0**, **Pydantic V2**, and **HTTPX**.

The architecture strictly follows the **Database-per-Service** microservices pattern. Zero shared tables or cross-database foreign keys exist. Services communicate exclusively via synchronous HTTP REST over versioned endpoints (`/api/v1/...`).

### 1.1 Microservice Inventory

| Service | Port | Database | Primary Responsibility | Contended / Unsafe Resource |
| :--- | :---: | :---: | :--- | :--- |
| **Order Service** | `8001` | `orders.db` | Coordinates the distributed checkout Saga; maintains order state machine | Unsafe order checkout |
| **Restaurant Service** | `8002` | `restaurant.db` | Manages restaurant catalogs, menus, and atomic dish reservations | **Contended dish stock** |
| **Payment Service** | `8003` | `payment.db` | Processes charges, refunds, enforces idempotency, simulates failure modes | **Unsafe payment charges** |
| **Delivery Service** | `8004` | `delivery.db` | Manages rider fleet status (`AVAILABLE`/`BUSY`) and delivery task dispatching | Rider availability pool |
| **Notification Service** | `8005` | `notification.db` | Dispatches simulated alerts (SMS/Email/Push) to customers and merchants | Downstream gateway simulator |

---

## 2. Completed Implementations & Verification

### 2.1 Mandatory Challenges (100% Completed & Verified)

#### Challenge 1: Concurrency Control (Mandatory)
* **Problem**: Preventing over-allocation when 20 simultaneous threads request a dish with capacity 5.
* **Mechanism**: Atomic conditional SQL update (`UPDATE menu_items SET available_quantity = available_quantity - :qty, version = version + 1 WHERE id = :item_id AND available_quantity >= :qty`).
* **Verification Script**: `scripts/test_challenge1_concurrency.py`
* **Result**: Exactly 5 succeeded (`HTTP 201`), exactly 15 rejected (`HTTP 409 Conflict`), final database stock = 0 with zero over-allocation.
* **Evidence Log**: `evidence/challenge-1-concurrency/concurrency_run_output.txt`

#### Challenge 2: Idempotency Enforcement (Mandatory)
* **Problem**: Preventing duplicate deductions or phantom orders during network retries or duplicate clicks.
* **Mechanism**: Header `Idempotency-Key` + SHA-256 request payload fingerprinting + response cache + database unique constraint preventing race conditions during concurrent duplicate hits.
* **Verification Script**: `scripts/test_challenge2_idempotency.py`
* **Result**: Tested cached replay (`X-Idempotent-Replay: true`), payload tampering rejection (`HTTP 409 Conflict`), and 10 parallel simultaneous hits. Verified exactly 1 payment record exists in the database.
* **Evidence Log**: `evidence/challenge-2-idempotency/idempotency_run_output.txt`

#### Challenge 3C: Orchestrated Saga with Compensation (Elective)
* **Problem**: Maintaining distributed consistency across isolated microservice databases without distributed 2PC locks.
* **Mechanism**: Orchestrated Saga in Order Service with explicit states (`PENDING` -> `STOCK_RESERVED` -> `PAID` -> `DELIVERY_ASSIGNED` -> `CONFIRMED`).
* **Compensating Actions**:
  1. **Payment Failure (Step 2)**: Order Service calls Restaurant Service to release reserved stock. Order transitions to `FAILED_PAYMENT_REJECTED`. Stock restored from 5 back to 8.
  2. **Delivery Failure (Step 3)**: Order Service refunds payment (`REFUNDED`) and releases reserved stock. Order transitions to `FAILED_NO_RIDER_AVAILABLE`.
* **Verification Script**: `scripts/test_challenge3_saga.py`
* **Evidence Log**: `evidence/challenge-3-saga/saga_run_output.txt`

### 2.2 Testing Suite
* **Unit Tests**: 20/20 tests passing in ~0.4s (`pytest services/`).
* **End-to-End Test**: `scripts/test_e2e_flow.py` verifies live customer journey across all 5 running services.
* **OpenAPI Specs**: Exported for all 5 services in `docs/openapi/`.

---

## 3. Git & Remote Configuration

* **GitHub Repository**: `https://github.com/kush6542/Group26_Scalable_Services`
* **Personal SSH Remote**: Configured using host alias `github.com-personal`:
  ```bash
  git remote set-url origin git@github.com-personal:kush6542/Group26_Scalable_Services.git
  ```
* **Branch**: `main` (tracked to `origin/main`).

---

## 4. Pending Deliverables for Final Submission (Assignment 1)

1. **Team Member Details & Reflections**:
   * Open `docs/FoodFlow_Design_Report.md` (Appendix B).
   * Fill in actual student names, BITS IDs, and individual 3-4 sentence reflections.
2. **Commit Distribution**:
   * Have teammates clone the repo and commit small tweaks from their machines so the Git commit history reflects multiple authors.
3. **Record Demo Video (8 to 10 Minutes)**:
   * Follow the teleprompter outline in `docs/FoodFlow_Design_Report.md` (Appendix A).
   * Run `scripts/run_all_services.py` in Terminal 1.
   * Run `scripts/test_e2e_flow.py`, `scripts/test_challenge1_concurrency.py`, `scripts/test_challenge2_idempotency.py`, and `scripts/test_challenge3_saga.py` live in Terminal 2.
   * Upload video to Google Drive (public viewable link).
4. **Convert Report to PDF**:
   * Add Google Drive link to Section 10 of `docs/FoodFlow_Design_Report.md`.
   * Export the Markdown file to `FoodFlow_Design_Report.pdf` (max 15 pages).

---

## 5. Quick Command Reference

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full test suite
pytest services/

# Start all 5 microservices (Terminal 1)
python3 scripts/run_all_services.py

# In Terminal 2, run verification scripts:
python3 scripts/test_e2e_flow.py
python3 scripts/test_challenge1_concurrency.py
python3 scripts/test_challenge2_idempotency.py
python3 scripts/test_challenge3_saga.py
```
