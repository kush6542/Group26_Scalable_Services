import sqlite3
import os
from pathlib import Path

# Always locate databases at the project root regardless of where the script is called from
ROOT_DIR = Path(__file__).resolve().parent.parent

def seed():
    print("=" * 60)
    print("  Seeding FoodFlow Demo Data (Memorable Fixed IDs)")
    print("=" * 60)
    
    rest_db = ROOT_DIR / "restaurant.db"
    deliv_db = ROOT_DIR / "delivery.db"
    
    # 1. Seed Restaurant Service
    conn_rest = sqlite3.connect(rest_db)
    cur_rest = conn_rest.cursor()
    
    cur_rest.execute("""
    CREATE TABLE IF NOT EXISTS restaurants (
        id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        address VARCHAR NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME
    )
    """)
    cur_rest.execute("""
    CREATE TABLE IF NOT EXISTS menu_items (
        id VARCHAR PRIMARY KEY,
        restaurant_id VARCHAR NOT NULL REFERENCES restaurants(id),
        name VARCHAR NOT NULL,
        description VARCHAR DEFAULT '',
        price FLOAT NOT NULL,
        available_quantity INTEGER NOT NULL DEFAULT 0,
        version INTEGER DEFAULT 1,
        created_at DATETIME
    )
    """)
    cur_rest.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id VARCHAR PRIMARY KEY,
        order_id VARCHAR NOT NULL,
        restaurant_id VARCHAR NOT NULL,
        item_id VARCHAR NOT NULL REFERENCES menu_items(id),
        quantity INTEGER NOT NULL,
        status VARCHAR DEFAULT 'RESERVED',
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    
    cur_rest.execute("""
    INSERT OR REPLACE INTO restaurants (id, name, address, is_active, created_at)
    VALUES ('rest-taj-biryani', 'Taj Biryani Kitchen', '42 Spice Road, Cyber City', 1, datetime('now'))
    """)
    
    cur_rest.execute("""
    INSERT OR REPLACE INTO menu_items (id, restaurant_id, name, description, price, available_quantity, version, created_at)
    VALUES ('dish-hyderabadi-biryani', 'rest-taj-biryani', 'Hyderabadi Dum Biryani', 'Authentic slow-cooked saffron basmati rice with tender spiced meat', 14.50, 20, 1, datetime('now'))
    """)
    
    conn_rest.commit()
    conn_rest.close()
    print(f"[✓] Restaurant Service: 'rest-taj-biryani' & 'dish-hyderabadi-biryani' (Stock: 20, Price: $14.50)")
    
    # 2. Seed Delivery Service (Pool of 5 Available Riders)
    conn_deliv = sqlite3.connect(deliv_db)
    cur_deliv = conn_deliv.cursor()
    
    cur_deliv.execute("""
    CREATE TABLE IF NOT EXISTS delivery_riders (
        id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        phone VARCHAR NOT NULL,
        vehicle_type VARCHAR DEFAULT 'MOTORCYCLE',
        status VARCHAR DEFAULT 'AVAILABLE',
        created_at DATETIME
    )
    """)
    cur_deliv.execute("""
    CREATE TABLE IF NOT EXISTS delivery_tasks (
        id VARCHAR PRIMARY KEY,
        order_id VARCHAR NOT NULL,
        rider_id VARCHAR NOT NULL REFERENCES delivery_riders(id),
        pickup_address VARCHAR NOT NULL,
        delivery_address VARCHAR NOT NULL,
        status VARCHAR DEFAULT 'ASSIGNED',
        created_at DATETIME,
        updated_at DATETIME
    )
    """)

    riders = [
        ('rider-dave-01', 'Dave Courier', '+19998887771'),
        ('rider-sarah-02', 'Sarah Swift', '+19998887772'),
        ('rider-alex-03', 'Alex Express', '+19998887773'),
        ('rider-raj-04', 'Raj Runner', '+19998887774'),
        ('rider-elena-05', 'Elena Speed', '+19998887775')
    ]

    for r_id, r_name, r_phone in riders:
        cur_deliv.execute("""
        INSERT OR REPLACE INTO delivery_riders (id, name, phone, vehicle_type, status, created_at)
        VALUES (?, ?, ?, 'MOTORBIKE', 'AVAILABLE', datetime('now'))
        """, (r_id, r_name, r_phone))

    # Reset any existing riders back to AVAILABLE
    cur_deliv.execute("UPDATE delivery_riders SET status = 'AVAILABLE'")
    conn_deliv.commit()
    conn_deliv.close()
    print(f"[✓] Delivery Service: 5 Riders seeded & reset to 'AVAILABLE'")

    print("\n[SUCCESS] Demo data ready! You can now place multiple orders smoothly in Swagger UI!")

if __name__ == "__main__":
    seed()
