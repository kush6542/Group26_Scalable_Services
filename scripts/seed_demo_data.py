import sqlite3
import os

def seed():
    print("=" * 60)
    print("  Seeding FoodFlow Demo Data (Memorable Fixed IDs)")
    print("=" * 60)
    
    # 1. Seed Restaurant Service
    conn_rest = sqlite3.connect("restaurant.db")
    cur_rest = conn_rest.cursor()
    
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
    print("[✓] Restaurant Service: 'rest-taj-biryani' & 'dish-hyderabadi-biryani' (Stock: 20, Price: $14.50)")
    
    # 2. Seed Delivery Service (Pool of 5 Available Riders)
    conn_deliv = sqlite3.connect("delivery.db")
    cur_deliv = conn_deliv.cursor()

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
    print("[✓] Delivery Service: 5 Riders seeded & reset to 'AVAILABLE'")

    print("\n[SUCCESS] Demo data ready! You can now place multiple orders smoothly in Swagger UI!")

if __name__ == "__main__":
    seed()
