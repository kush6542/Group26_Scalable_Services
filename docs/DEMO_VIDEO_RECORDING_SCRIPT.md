# FoodFlow: Demo Video Recording Script & Teleprompter (8 to 10 Minutes)

> **Course**: Scalable Services (SEZG583) | MTech  
> **Group**: Group 26  
> **Team Members**:  
> * **Kushagra Parashar** (`2025tm93126@wilp.bits-pilani.ac.in`) — Lead: Order Service & Restaurant Service  
> * **Thamarai Muthu Selvi A** (`2025tm93028@wilp.bits-pilani.ac.in`) — Payment Service  
> * **Vijay Kumar Singh** (`2025tm93550@wilp.bits-pilani.ac.in`) — Delivery Service  
> * **Hemanta** (`2025tm93xxx@wilp.bits-pilani.ac.in`) — Notification Service  
> **Target Video Duration**: 8 to 10 Minutes (Strictly enforced by faculty rubric)

---

## 1. Pre-Recording Setup (2 Minutes Before Hitting Record)

1. **Screen Layout (Split-Screen)**:
   * **Left Half of Screen**: Web Browser (Chrome/Safari) with 2 open tabs:
     * Tab 1: `http://localhost:8001/docs` (Order Service Swagger UI)
     * Tab 2: `http://localhost:8002/docs` (Restaurant Service Swagger UI)
   * **Right Half of Screen**: Two Terminal windows:
     * **Terminal 1 (Background Services)**: Run `source .venv/bin/activate && python3 scripts/run_all_services.py`
     * **Terminal 2 (Execution Terminal)**: Run `source .venv/bin/activate && python3 scripts/seed_demo_data.py` (resets demo stock to 20)

---

## 2. Minute-by-Minute Teleprompter Script

---

### [0:00 - 1:00] Part 1: Team Introduction & Service Ownership
* **On Screen**: Show the Title Slide or README in your browser.
* **Speaker**: **Kushagra Parashar** (or opening member)
* **What to Say**:
  > *"Hello professor and evaluators. We are **Group 26** presenting our submission for **Assignment 1: Scalable Services (SEZG583)**.*  
  >  
  > *Our project is **FoodFlow**, a scalable, fault-tolerant microservices platform for on-demand food delivery.  
  >  
  > *Our team decomposed the application across four distinct members:*  
  > * *I am **Kushagra Parashar** (Student ID: 2025tm93126). I owned the two central services: the **Order Service**, which acts as our distributed Saga Orchestrator, and the **Restaurant Service**, which manages menus and atomic inventory concurrency control.*  
  > * ***Thamarai Muthu Selvi A** (Student ID: 2025tm93028) owned the **Payment Service**, implementing our cryptographic Idempotency Engine and failure injection mocks.*  
  > * ***Vijay Kumar Singh** (Student ID: 2025tm93550) owned the **Delivery Service**, managing driver availability and task dispatching.*  
  > * ***Hemanta** owned the **Notification Service**, managing multi-channel alerts and distributed request correlation tracing.*  
  >  
  > *Let us now examine the architectural design."*

---

### [1:00 - 2:30] Part 2: Architecture & Service Decomposition
* **On Screen**: Show the Architecture Diagram (from [`FoodFlow_Design_Report.md`](file:///Users/kushagra.parashar/IdeaProjects/Group26_Scalable_Services/docs/FoodFlow_Design_Report.md) or [`README.md`](file:///Users/kushagra.parashar/IdeaProjects/Group26_Scalable_Services/README.md)).
* **Speaker**: **Kushagra Parashar** (or passing to teammate)
* **What to Say**:
  > *"FoodFlow is decomposed into **5 independent services** communicating strictly over HTTP REST:*  
  > 1. *Order Service (Port 8001)*  
  > 2. *Restaurant Service (Port 8002)*  
  > 3. *Payment Service (Port 8003)*  
  > 4. *Delivery Service (Port 8004)*  
  > 5. *Notification Service (Port 8005)*  
  >  
  > *Most importantly, we have strictly adhered to the **Database-per-Service** pattern. Each microservice owns its private SQLite database: `orders.db`, `restaurant.db`, `payment.db`, etc. There are **zero shared tables**, **no cross-database foreign keys**, and **no cross-database joins**.*  
  >  
  > *Every service exposes `GET /health`, reads 100% of its configuration from environment variables, and propagates an `X-Correlation-ID` header across every single request and structured log line for distributed tracing.*  
  >  
  > *Now let us see the live system in action."*

---

### [2:30 - 5:30] Part 3: Live Visual Demo in Swagger UI (Code in Action)
* **On Screen**: Focus on your browser with Swagger UI.

#### A. Happy Path Order Flow (Visual Demo)
1. **Show Restaurant Stock**:
   * Switch to Tab 2: `http://localhost:8002/docs` (Restaurant Service).
   * Expand **`GET /api/v1/restaurants/{restaurant_id}/menu`** $\rightarrow$ Click **Try it out** $\rightarrow$ Type `rest-taj-biryani` $\rightarrow$ Click **Execute**.
   * **Speaker**:
     > *"Here in the Restaurant Service Swagger UI, we query the menu for 'Taj Biryani Kitchen'. Notice that 'Hyderabadi Dum Biryani' currently has **20 portions available** in `restaurant.db`."*
2. **Execute Customer Checkout**:
   * Switch to Tab 1: `http://localhost:8001/docs` (Order Service).
   * Expand **`POST /api/v1/orders/checkout`** $\rightarrow$ Click **Try it out**.
   * Paste this exact JSON:
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
   * Click **Execute**.
   * **Speaker**:
     > *"We execute checkout for 2 portions. We receive **HTTP 201 Created** with status **`CONFIRMED`**.*  
     > *Notice the `state_logs` array in the response: the Order Orchestrator transitioned through `PENDING` -> `STOCK_RESERVED` -> `PAID` -> `DELIVERY_ASSIGNED` -> `CONFIRMED`, linking the stock reservation ID, payment transaction ID, and delivery task ID across all services."*
3. **Verify Database State**:
   * Switch back to Tab 2 (`http://localhost:8002/docs`) $\rightarrow$ Click **Execute** again.
   * **Speaker**:
     > *"Refreshing the restaurant inventory, we see `available_quantity` has dropped from **20 to 18**. The stock was atomically decremented in the restaurant's private database."*

---

#### B. Failure Case: Payment Declined & Saga Compensation
* **On Screen**: Tab 1: `http://localhost:8001/docs` (Order Service).
1. In `POST /api/v1/orders/checkout`, change `"card_number"` to end in `9999`:
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
2. Click **Execute**.
3. **Speaker**:
   > *"Now we simulate a failure scenario: a payment decline (Condition e). When we click Execute, the response returns **HTTP 402 Payment Required** with status **`FAILED_PAYMENT_REJECTED`**.*  
   >  
   > *Look at the state machine progression in the response JSON: the order was `PENDING`, reserved stock (`STOCK_RESERVED`), but when Payment Service declined the charge, our **Saga Orchestrator** automatically entered `COMPENSATING_ROLLBACK` and fired a compensating API call to the Restaurant Service to release the reserved stock."*
4. Switch to Tab 2 (`http://localhost:8002/docs`) $\rightarrow$ Click **Execute**.
5. **Speaker**:
   > *"Checking the restaurant stock again: it is **still 18**! The compensating transaction released the hold and prevented phantom stock loss."*

---

### [5:30 - 8:30] Part 4: Live Engineering Challenges in Terminal
* **On Screen**: Switch to your Terminal window (Terminal 2).

#### 1. Challenge 1: Concurrency Control (Mandatory)
* **Command**:
  ```bash
  python3 scripts/test_challenge1_concurrency.py
  ```
* **Speaker (Kushagra)**:
  > *"Next, we demonstrate **Challenge 1: Concurrency Control**.*  
  > *During flash deals, simultaneous orders can over-allocate stock if naive application code uses 'check-then-update'.*  
  >  
  > *Our script creates a dish with capacity **N = 5** and fires **20 parallel threads** at the exact same millisecond.*  
  >  
  > *As seen on screen: exactly **5 requests succeed with HTTP 201**, and **15 requests are rejected with HTTP 409 Conflict ('Stock insufficient')**.*  
  > *Final database stock is verified at exactly **0**. Because we used an **atomic conditional SQL update**, zero over-allocation occurs."*

---

#### 2. Challenge 2: Idempotency Enforcement (Mandatory)
* **Command**:
  ```bash
  python3 scripts/test_challenge2_idempotency.py
  ```
* **Speaker (Thamarai / Team)**:
  > *"Now we run **Challenge 2: Idempotency Enforcement**.*  
  > *In Phase 1, an initial charge succeeds with HTTP 201.*  
  > *In Phase 2, an identical replay with the same `Idempotency-Key` immediately returns the cached response with header `X-Idempotent-Replay: true` and the matching transaction ID.*  
  > *In Phase 3, an attacker reuses the key with an altered amount: our service rejects it with **HTTP 409 Conflict**.*  
  > *In Phase 4, a burst of 10 simultaneous identical requests is fired. Database auditing in Phase 5 proves **exactly 1 payment record** was stored in the database."*

---

#### 3. Challenge 3C: Saga Multi-Step Compensation (Chosen Elective)
* **Command**:
  ```bash
  python3 scripts/test_challenge3_saga.py
  ```
* **Speaker (Kushagra / Team)**:
  > *"Now we run **Challenge 3C: Orchestrated Saga with Compensation**.*  
  > *This script verifies all 3 scenarios:  
  > 1. Happy path checkout.*  
  > 2. *Payment failure at Step 2 releasing stock.*  
  > 3. *Delivery failure at Step 3 triggering **double compensation**: automatically refunding the payment in `payment.db` and releasing the reserved stock in `restaurant.db`.*  
  > *All scenarios pass with complete cross-database consistency."*

---

### [8:30 - 9:30] Part 5: Unit Tests & Readiness for Assignment 2
* **Command**:
  ```bash
  pytest services/
  ```
* **Speaker**:
  > *"Here we run our unit test suite covering our 7 business rules (BR1 to BR7). All **20 unit tests pass in 0.4 seconds**.*  
  >  
  > *Furthermore, FoodFlow was built specifically for **Assignment 2**:*  
  > * *Every service has its own `Dockerfile` structure and `requirements.txt`.*  
  > * *Ports and service discovery URLs come from environment variables.*  
  > * *Our `/health` endpoints will directly integrate with Kubernetes `livenessProbe` and `readinessProbe` on Minikube."*

---

### [9:30 - 10:00] Part 6: Conclusion
* **Speaker**:
  > *"In summary, FoodFlow demonstrates rigorous microservices engineering: clean service boundaries, database-per-service isolation, atomic concurrency control, cryptographic idempotency, and automated Saga compensation without distributed locks.*  
  >  
  > *Thank you for your time and evaluation."*

---

## 3. Quick Rehearsal Cheat-Sheet

| Timestamp | Screen | Action / Command |
| :--- | :--- | :--- |
| **0:00** | Browser / Slide | Introduce Group 26, names, IDs, service ownership |
| **1:00** | Architecture Diagram | Explain 5 services, DB-per-service, REST communication |
| **2:30** | Restaurant Swagger (`8002`) | Show stock = 20 for `rest-taj-biryani` |
| **3:15** | Order Swagger (`8001`) | Post checkout (2 qty) $\rightarrow$ Show 201 Created & state machine |
| **4:00** | Restaurant Swagger (`8002`) | Re-run query $\rightarrow$ Show stock decremented 20 $\rightarrow$ 18 |
| **4:30** | Order Swagger (`8001`) | Post checkout with card `...9999` $\rightarrow$ Show 402 & compensation |
| **5:15** | Restaurant Swagger (`8002`) | Re-run query $\rightarrow$ Show stock remained at 18 (no leak) |
| **5:30** | Terminal 2 | `python3 scripts/test_challenge1_concurrency.py` |
| **6:30** | Terminal 2 | `python3 scripts/test_challenge2_idempotency.py` |
| **7:30** | Terminal 2 | `python3 scripts/test_challenge3_saga.py` |
| **8:30** | Terminal 2 | `pytest services/` (20 passed) |
| **9:30** | Slide / Terminal | Mention Assignment 2 Docker/K8s readiness & conclude |
