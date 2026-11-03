import os
import sys
import time
import signal
import subprocess

processes = []

def cleanup(sig=None, frame=None):
    print("\n[FoodFlow] Stopping Payment Service...")
    for p in processes:
        if p.poll() is None:
            p.terminate()

    time.sleep(1)

    for p in processes:
        if p.poll() is None:
            p.kill()

    print("[FoodFlow] Payment Service stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def start_service():

    # Prefer virtual environment Python
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Windows and Linux compatibility
    if os.name == "nt":
        venv_python = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(repo_root, ".venv", "bin", "python")

    python_bin = venv_python if os.path.exists(venv_python) else sys.executable

    print("=" * 60)
    print("       Starting FoodFlow Payment Service")
    print("=" * 60)

    cmd = [
        python_bin,
        "-m", "uvicorn",
        "services.payment_service.src.main:app",
        "--host", "0.0.0.0",
        "--port", "8003",
        "--log-level", "info"
    ]

    p = subprocess.Popen(cmd)
    processes.append(p)

    print("[*] Payment Service starting on http://localhost:8003")
    print("[*] API Documentation: http://localhost:8003/docs")
    print("[*] Press Ctrl+C to stop the service.")

    try:
        while p.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    start_service()