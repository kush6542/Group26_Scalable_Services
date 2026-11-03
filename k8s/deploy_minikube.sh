#!/usr/bin/env bash
set -e

# ==============================================================================
# FoodFlow Minikube Deployment Script (Assignment 2 Advanced Task)
# ==============================================================================

echo "============================================================"
echo "    Deploying FoodFlow Microservices Platform on Minikube"
echo "============================================================"

# Step 1: Check minikube status
if ! minikube status > /dev/null 2>&1; then
    echo "[!] Minikube is not running. Starting Minikube..."
    minikube start --driver=docker --cpus=4 --memory=4096
else
    echo "[✓] Minikube is active and running."
fi

# Step 2: Point local Docker CLI to Minikube's Docker daemon
echo "[*] Configuring Docker CLI to build inside Minikube daemon..."
eval $(minikube -p minikube docker-env)

# Step 3: Build container images directly into Minikube
echo "[*] Building FoodFlow container images..."
docker build -t foodflow/restaurant-service:v1 -f services/restaurant_service/Dockerfile .
docker build -t foodflow/payment-service:v1 -f services/payment_service/Dockerfile .
docker build -t foodflow/delivery-service:v1 -f services/delivery_service/Dockerfile .
docker build -t foodflow/notification-service:v1 -f services/notification_service/Dockerfile .
docker build -t foodflow/order-service:v1 -f services/order_service/Dockerfile .
echo "[✓] All 5 microservice images successfully built inside Minikube."

# Step 4: Apply Kubernetes Manifests
echo "[*] Applying Kubernetes manifests..."
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/03-postgres.yaml

echo "[*] Waiting for PostgreSQL to be ready..."
kubectl wait --namespace=foodflow --for=condition=ready pod -l app=postgres --timeout=120s

kubectl apply -f k8s/04-restaurant-service.yaml
kubectl apply -f k8s/05-payment-service.yaml
kubectl apply -f k8s/06-delivery-service.yaml
kubectl apply -f k8s/07-notification-service.yaml
kubectl apply -f k8s/08-order-service.yaml

# Step 5: Wait for all service deployments to roll out
echo "[*] Waiting for microservices to roll out..."
kubectl rollout status deployment/restaurant-service -n foodflow --timeout=90s
kubectl rollout status deployment/payment-service -n foodflow --timeout=90s
kubectl rollout status deployment/delivery-service -n foodflow --timeout=90s
kubectl rollout status deployment/notification-service -n foodflow --timeout=90s
kubectl rollout status deployment/order-service -n foodflow --timeout=90s

echo ""
echo "============================================================"
echo "  [SUCCESS] FoodFlow Successfully Deployed on Minikube!"
echo "============================================================"
kubectl get pods -n foodflow -o wide
echo ""
kubectl get svc -n foodflow
echo ""
ORDER_URL=$(minikube service order-service -n foodflow --url 2>/dev/null || minikube ip)
echo "[*] Order Service is accessible at: ${ORDER_URL}"
echo "[*] Swagger Documentation: ${ORDER_URL}/docs"
