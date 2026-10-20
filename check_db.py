import sqlite3

conn = sqlite3.connect('backend/bloodbank.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in tables:
    cols = c.execute(f"PRAGMA table_info({t})").fetchall()
    print(f"\nTable {t}:")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")

conn.close()
