import os
import sys
import time
import signal
import subprocess
import httpx

SERVICES = [
    {"name": "Restaurant Service", "app": "services.restaurant_service.src.main:app", "port": 8002},
    {"name": "Payment Service",    "app": "services.payment_service.src.main:app",    "port": 8003},
    {"name": "Delivery Service",   "app": "services.delivery_service.src.main:app",   "port": 8004},
    {"name": "Notification Service","app": "services.notification_service.src.main:app","port": 8005},
    {"name": "Order Service",      "app": "services.order_service.src.main:app",      "port": 8001},
]

processes = []

def cleanup(sig=None, frame=None):
    print("\n[FoodFlow] Stopping all services...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
    time.sleep(1)
    for p in processes:
        if p.poll() is None:
            p.kill()
    print("[FoodFlow] All services stopped.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def start_services():
    # Prefer virtual environment python if present
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(repo_root, ".venv", "bin", "python")
    python_bin = venv_python if os.path.exists(venv_python) else sys.executable
    print("=" * 60)
    print("      Starting FoodFlow Microservices Architecture")
    print("=" * 60)

    for svc in SERVICES:
        cmd = [
            python_bin, "-m", "uvicorn",
            svc["app"],
            "--host", "0.0.0.0",
            "--port", str(svc["port"]),
            "--log-level", "warning"
        ]
        p = subprocess.Popen(cmd)
        processes.append(p)
        print(f"[*] Started {svc['name']} on http://localhost:{svc['port']}")

    print("\nWaiting for all services to pass /health checks...")
    all_ready = False
    for attempt in range(25):
        time.sleep(0.5)
        ready_count = 0
        with httpx.Client(timeout=2.0) as client:
            for svc in SERVICES:
                try:
                    res = client.get(f"http://localhost:{svc['port']}/health")
                    if res.status_code == 200 and res.json().get("status") == "UP":
                        ready_count += 1
                except Exception:
                    pass
        if ready_count == len(SERVICES):
            all_ready = True
            break

    if all_ready:
        print("\n" + "=" * 60)
        print("  ALL 5 FOODFLOW SERVICES ARE HEALTHY & OPERATIONAL")
        print("=" * 60)
        print("• Order Service:        http://localhost:8001/docs")
        print("• Restaurant Service:   http://localhost:8002/docs")
        print("• Payment Service:      http://localhost:8003/docs")
        print("• Delivery Service:     http://localhost:8004/docs")
        print("• Notification Service: http://localhost:8005/docs")
        print("Press Ctrl+C to shut down.")
        
        while True:
            time.sleep(1)
    else:
        print("\n[ERROR] One or more services failed to report healthy in time.")
        cleanup()

if __name__ == "__main__":
    start_services()
