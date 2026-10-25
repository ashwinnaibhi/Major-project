"""
Seeds verified Karnataka Government Hospitals into SQLite database bloodbank.db
"""
import os
import json
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "bloodbank.db")
JSON_PATH = os.path.join(os.path.dirname(__file__), "karnataka_government_hospitals.json")

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        hospitals = json.load(f)

    for h in hospitals:
        cur.execute("""
            INSERT OR REPLACE INTO hospitals (
                id, name, category, state, district, taluk, address, phone, has_blood_bank, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            h["hospital_id"], h["name"], h["category"], h["state"], h["district"],
            h["taluk"], h["address"], h["phone"], 1 if h["has_blood_bank"] else 0,
            h["latitude"], h["longitude"]
        ))

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(hospitals)} verified Karnataka Government Hospitals.")

if __name__ == "__main__":
    seed()