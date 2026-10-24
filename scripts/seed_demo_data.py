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
    
    # 2. Seed Delivery Service
    conn_deliv = sqlite3.connect("delivery.db")
    cur_deliv = conn_deliv.cursor()
    cur_deliv.execute("""
    INSERT OR REPLACE INTO delivery_riders (id, name, phone, vehicle_type, status, created_at)
    VALUES ('rider-dave-01', 'Dave Courier', '+19998887777', 'MOTORBIKE', 'AVAILABLE', datetime('now'))
    """)
    conn_deliv.commit()
    conn_deliv.close()
    print("[✓] Delivery Service: 'rider-dave-01' (Status: AVAILABLE)")

    print("\n[SUCCESS] Demo data ready! You can now use clean, fixed IDs in Swagger UI!")

if __name__ == "__main__":
    seed()
