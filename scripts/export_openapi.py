import json
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.order_service.src.main import app as order_app
from services.restaurant_service.src.main import app as restaurant_app
from services.payment_service.src.main import app as payment_app
from services.delivery_service.src.main import app as delivery_app
from services.notification_service.src.main import app as notification_app

def export():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "openapi"))
    os.makedirs(output_dir, exist_ok=True)

    apps = {
        "order_service_openapi.json": order_app,
        "restaurant_service_openapi.json": restaurant_app,
        "payment_service_openapi.json": payment_app,
        "delivery_service_openapi.json": delivery_app,
        "notification_service_openapi.json": notification_app,
    }

    for filename, app_instance in apps.items():
        spec = app_instance.openapi()
        target_path = os.path.join(output_dir, filename)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
        print(f"Exported {filename} -> {target_path}")

if __name__ == "__main__":
    export()
