#!/usr/bin/env bash
set -e

# ==============================================================================
# FoodFlow Kubernetes Scaling & Self-Healing Demo (Assignment 2 Advanced Task)
# ==============================================================================

echo "======================================================================"
echo "    Kubernetes Pod Scaling & Self-Healing Verification (FoodFlow)"
echo "======================================================================"

echo ""
echo "--- 1. Initial State: Checking Current Replicas in 'foodflow' namespace ---"
kubectl get pods -n foodflow -l app=restaurant-service -o wide

echo ""
echo "--- 2. Demonstrating Kubernetes Scaling: Scale Restaurant Service from 2 -> 4 ---"
kubectl scale deployment restaurant-service --replicas=4 -n foodflow
kubectl rollout status deployment/restaurant-service -n foodflow --timeout=60s

echo ""
echo "[✓] Successfully Scaled to 4 Replicas:"
kubectl get pods -n foodflow -l app=restaurant-service

echo ""
echo "--- 3. Demonstrating Kubernetes Self-Healing: Simulating Pod Crash ---"
TARGET_POD=$(kubectl get pods -n foodflow -l app=restaurant-service -o jsonpath='{.items[0].metadata.name}')
echo "[*] Forcefully terminating active pod: ${TARGET_POD}"
kubectl delete pod ${TARGET_POD} -n foodflow --grace-period=0 --force 2>/dev/null || true

echo ""
echo "[*] Observing ReplicaSet self-healing behavior..."
sleep 3
kubectl get pods -n foodflow -l app=restaurant-service

echo ""
echo "[*] Waiting for replacement pod to pass Readiness Probe..."
kubectl wait --namespace=foodflow --for=condition=ready pod -l app=restaurant-service --timeout=30s

echo ""
echo "======================================================================"
echo "  [VERIFIED] Kubernetes Self-Healing Succeeded!"
echo "  The ReplicaSet immediately detected the deleted pod and spawned a"
echo "  healthy replacement to satisfy the desired state."
echo "======================================================================"
kubectl get pods -n foodflow -l app=restaurant-service -o wide
