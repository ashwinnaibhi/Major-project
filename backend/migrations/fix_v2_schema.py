"""
Schema migration: Ensures blood_requests and blood_inventory tables meet
all Issue 1, 2, 5 requirements without dropping any existing records.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bloodbank.db")

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Ensure assigned_admin_id can be NULL in blood_requests
    cur.execute("PRAGMA table_info(blood_requests)")
    cols = [col[1] for col in cur.fetchall()]
    if "assigned_admin_id" not in cols:
        cur.execute("ALTER TABLE blood_requests ADD COLUMN assigned_admin_id INTEGER NULL")

    # 2. Add category to hospitals if missing
    cur.execute("PRAGMA table_info(hospitals)")
    h_cols = [col[1] for col in cur.fetchall()]
    if "category" not in h_cols:
        cur.execute("ALTER TABLE hospitals ADD COLUMN category TEXT DEFAULT 'Government Hospital'")

    # 3. Ensure unique index on blood_inventory (hospital_id, blood_group)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_hosp_group 
        ON blood_inventory(hospital_id, blood_group)
    """)

    conn.commit()
    conn.close()
    print("Database migration completed successfully.")

if __name__ == "__main__":
    run_migration()