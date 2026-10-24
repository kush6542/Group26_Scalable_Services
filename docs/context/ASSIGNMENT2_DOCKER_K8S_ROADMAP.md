# Assignment 2 Compatibility & Docker / Minikube Roadmap

> **Target Assignment**: Assignment 2 (7 Marks)  
> **Topic**: Containerisation and Deployment on Docker and Minikube  
> **Status**: **100% Compatible & Architected Specifically for Assignment 2**

---

## 1. Is This Codebase Compatible with Assignment 2?

**YES, 100%!** The codebase was intentionally designed and structured from day one with Assignment 2 requirements in mind.

Here is the architectural mapping between what we built in Assignment 1 and what Assignment 2 requires:

| Assignment 2 Requirement | How FoodFlow Fulfills It in Assignment 1 | Ready for Containerisation? |
| :--- | :--- | :---: |
| **Independent Service Folders** | Each service (`order_service`, `restaurant_service`, etc.) is self-contained with its own folder, code, and `requirements.txt`. | Yes |
| **12-Factor App Configuration** | All configuration (host, port, database URL, downstream service URLs) is loaded strictly from environment variables via `config.py`. | Yes |
| **Health Probes for Kubernetes** | Every service exposes `GET /health` returning `{"status": "UP"}`. This directly maps to Kubernetes `livenessProbe` and `readinessProbe`. | Yes |
| **Inter-Service Communication via URLs** | Services communicate using configurable URLs (`RESTAURANT_SERVICE_URL`, `PAYMENT_SERVICE_URL`, etc.). In Docker / K8s, these swap to container/service DNS names seamlessly. | Yes |
| **Structured Logging & Tracing** | Every service propagates `X-Correlation-ID` across HTTP headers and structured logs. | Yes |
| **Database Isolation** | Database-per-service pattern allows either volume-mounted SQLite or dedicated PostgreSQL containers in Docker Compose / Kubernetes. | Yes |

---

## 2. Docker Roadmap (How Each Service Will Containerise)

Each microservice will get an identical, lightweight multi-stage or slim `Dockerfile`.

### Sample `Dockerfile` Template (e.g. for `services/order_service/Dockerfile`):
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy dependency specifications
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Expose service port
EXPOSE 8001

# Run via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## 3. Docker Compose Roadmap (`docker-compose.yml`)

Because every service uses environment variables for discovery, running all 5 services with Docker Compose requires only linking their container names:

```yaml
version: "3.8"

services:
  restaurant-service:
    build:
      context: ./services/restaurant_service
    ports:
      - "8002:8002"
    environment:
      - PORT=8002
      - DATABASE_URL=sqlite:///./restaurant.db

  payment-service:
    build:
      context: ./services/payment_service
    ports:
      - "8003:8003"
    environment:
      - PORT=8003
      - DATABASE_URL=sqlite:///./payment.db

  delivery-service:
    build:
      context: ./services/delivery_service
    ports:
      - "8004:8004"
    environment:
      - PORT=8004
      - DATABASE_URL=sqlite:///./delivery.db

  notification-service:
    build:
      context: ./services/notification_service
    ports:
      - "8005:8005"
    environment:
      - PORT=8005
      - DATABASE_URL=sqlite:///./notification.db

  order-service:
    build:
      context: ./services/order_service
    ports:
      - "8001:8001"
    environment:
      - PORT=8001
      - DATABASE_URL=sqlite:///./orders.db
      - RESTAURANT_SERVICE_URL=http://restaurant-service:8002
      - PAYMENT_SERVICE_URL=http://payment-service:8003
      - DELIVERY_SERVICE_URL=http://delivery-service:8004
      - NOTIFICATION_SERVICE_URL=http://notification-service:8005
    depends_on:
      - restaurant-service
      - payment-service
      - delivery-service
      - notification-service
```
Notice how `order-service` connects to `http://restaurant-service:8002` using Docker's internal DNS without changing any application Python code!

---

## 4. Minikube / Kubernetes Roadmap

In Minikube, each microservice will be deployed using:
1. **Deployment**: Manages replicas, container image, environment variables, and health probes:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: order-service
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: order-service
     template:
       metadata:
         labels:
           app: order-service
       spec:
         containers:
         - name: order-service
           image: foodflow/order-service:v1
           ports:
           - containerPort: 8001
           livenessProbe:
             httpGet:
               path: /health
               port: 8001
             initialDelaySeconds: 5
             periodSeconds: 10
           readinessProbe:
             httpGet:
               path: /health
               port: 8001
             initialDelaySeconds: 5
             periodSeconds: 10
   ```
2. **Service (ClusterIP)**: Exposes stable cluster DNS (e.g. `order-service.default.svc.cluster.local:8001`).
3. **Ingress / NodePort**: Routes external traffic into the cluster.

---

## 5. Database Options in Assignment 2

In Assignment 2, you have two flexible paths for databases:
* **Option A (Persistent Volume SQLite)**: Mount a Kubernetes `PersistentVolumeClaim` (PVC) into `/app/data/` for each service's `.db` file.
* **Option B (Dedicated PostgreSQL Pods)**: Deploy 5 lightweight PostgreSQL pods in Minikube (`order-db`, `restaurant-db`, etc.) and simply update the `DATABASE_URL` environment variable:
  ```bash
  DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@order-db:5432/order_db
  ```
  Because we used SQLAlchemy ORM models, switching from SQLite to PostgreSQL requires **zero code changes**.
