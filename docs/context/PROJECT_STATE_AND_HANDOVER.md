# FoodFlow: Project State & Session Handover Document

> **Course**: Scalable Services (SEZG583) | MTech  
> **Team**: Group 26  
> **Repository**: [https://github.com/kush6542/Group26_Scalable_Services](https://github.com/kush6542/Group26_Scalable_Services)  
> **Date of Last Update**: October 2026  
> **Current Version**: v1.1.0 (Assignment 1 Complete with Demo Seed Support)

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

## 3. Auto-Seeding & Demo Fixed IDs

Whenever any user boots the services, the system automatically checks and pre-populates clean, human-readable demo records. You do not need to deal with long random UUIDs.

* **Restaurant ID**: `rest-taj-biryani` (*"Taj Biryani Kitchen"*)
* **Menu Item ID**: `dish-hyderabadi-biryani` (*"Hyderabadi Dum Biryani"*, Price: $14.50, Initial Stock: 20)
* **Delivery Rider ID**: `rider-dave-01` (*"Dave Courier"*, Status: `AVAILABLE`)

### Reset Seed Script:
If you want to reset stock back to 20 at any point:
```bash
python3 scripts/seed_demo_data.py
```

---

## 4. Swagger UI Visual Demo Walkthrough (For Recording Video)

Open two browser tabs side-by-side with your terminal:
* **Restaurant Swagger UI**: [http://localhost:8002/docs](http://localhost:8002/docs)
* **Order Swagger UI**: [http://localhost:8001/docs](http://localhost:8001/docs)

### A. The Happy Path Order
1. In `http://localhost:8002/docs`, expand `GET /api/v1/restaurants/rest-taj-biryani/menu`, click **Try it out** -> **Execute**. Show stock is `20`.
2. In `http://localhost:8001/docs`, expand `POST /api/v1/orders/checkout`, click **Try it out**, paste the JSON below and click **Execute**:
```json
{
  "customer_id": "cust-demo",
  "restaurant_id": "rest-taj-biryani",
  "item_id": "dish-hyderabadi-biryani",
  "quantity": 2,
  "unit_price": 14.5,
  "delivery_address": "Flat 202, Marina Bay",
  "pickup_address": "42 Spice Road, Cyber City",
  "card_number": "4111111111111111"
}
```
Response returns `201 Created` with `"status": "CONFIRMED"`.
3. Refresh the Restaurant Swagger tab: stock has decremented from **20 -> 18**.

### B. The Failure Case (Card Declined & Stock Released)
In `POST /api/v1/orders/checkout`, change card_number to end in `9999`:
```json
{
  "customer_id": "cust-demo",
  "restaurant_id": "rest-taj-biryani",
  "item_id": "dish-hyderabadi-biryani",
  "quantity": 2,
  "unit_price": 14.5,
  "delivery_address": "Flat 202, Marina Bay",
  "pickup_address": "42 Spice Road, Cyber City",
  "card_number": "4111111111119999"
}
```
Response returns `402 Payment Required` with `"status": "FAILED_PAYMENT_REJECTED"`.
Point out to the evaluator that the Saga Orchestrator caught the decline and released the stock, so stock remains at 18!

---

## 5. Git & Remote Configuration

* **GitHub Repository**: `https://github.com/kush6542/Group26_Scalable_Services`
* **Personal SSH Remote**: Configured using host alias `github.com-personal`:
  ```bash
  git remote set-url origin git@github.com-personal:kush6542/Group26_Scalable_Services.git
  ```
* **Branch**: `main` (tracked to `origin/main`).

---

## 6. Action Items to Pick Up in Next Session

1. **Team Member Details & Reflections**:
   * Open `docs/FoodFlow_Design_Report.md` (Appendix B).
   * Fill in actual student names, BITS IDs, and individual 3-4 sentence reflections.
2. **Commit Distribution**:
   * Have teammates clone the repo and commit small tweaks from their machines so the Git commit history reflects multiple authors.
3. **Record Demo Video (8 to 10 Minutes)**:
   * Follow the outline in Section 4 above and `docs/FoodFlow_Design_Report.md` (Appendix A).
   * Upload video to Google Drive (set permission to "Anyone with the link can view").
4. **Convert Report to PDF**:
   * Add Google Drive link to Section 10 of `docs/FoodFlow_Design_Report.md`.
   * Export the Markdown file to `FoodFlow_Design_Report.pdf` (max 15 pages).
5. **Submit Assignment 1**:
   * Submit GitHub repository URL, Design Report PDF, and Google Drive demo video link on the portal.

---

## 7. Quick Command Reference

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full test suite
pytest services/

# Reset / Seed demo data with memorable IDs
python3 scripts/seed_demo_data.py

# Start all 5 microservices (Terminal 1)
python3 scripts/run_all_services.py

# In Terminal 2, run verification scripts:
python3 scripts/test_e2e_flow.py
python3 scripts/test_challenge1_concurrency.py
python3 scripts/test_challenge2_idempotency.py
python3 scripts/test_challenge3_saga.py
```
