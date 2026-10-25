"""
Migration script: add_donation_history.py
Adds donation_history table and indexes to Neon PostgreSQL and/or local SQLite,
and safely backfills existing verified records from donations.

Usage:
    python backend/migrations/add_donation_history.py [--dry-run] [--verify-only] [--target postgres|sqlite|both]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import database

POSTGRES_DONATION_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS donation_history (
    id SERIAL PRIMARY KEY,
    donor_id INTEGER REFERENCES donors(id) ON DELETE SET NULL,
    donor_code TEXT,
    donor_name TEXT NOT NULL,
    donor_email TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 1 CHECK(units > 0),
    donation_date TEXT NOT NULL,
    donation_type TEXT NOT NULL DEFAULT 'Whole Blood'
        CHECK(donation_type IN ('Whole Blood', 'Platelets', 'Plasma', 'Red Blood Cells')),
    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    hospital_name TEXT NOT NULL,
    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'CONFIRMED'
        CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONFIRMED')),
    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approval_date TEXT,
    notes TEXT,
    certificate_code TEXT UNIQUE NOT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK(is_synthetic IN (0, 1)),
    synthetic_batch_tag TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SQLITE_DONATION_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS donation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER REFERENCES donors(id) ON DELETE SET NULL,
    donor_code TEXT,
    donor_name TEXT NOT NULL,
    donor_email TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 1 CHECK(units > 0),
    donation_date TEXT NOT NULL,
    donation_type TEXT NOT NULL DEFAULT 'Whole Blood'
        CHECK(donation_type IN ('Whole Blood', 'Platelets', 'Plasma', 'Red Blood Cells')),
    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    hospital_name TEXT NOT NULL,
    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'CONFIRMED'
        CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONFIRMED')),
    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approval_date TEXT,
    notes TEXT,
    certificate_code TEXT UNIQUE NOT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK(is_synthetic IN (0, 1)),
    synthetic_batch_tag TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

POSTGRES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_donation_history_donor_id ON donation_history(donor_id);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_donor_email ON donation_history(LOWER(donor_email));",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_hospital ON donation_history(hospital_user_id);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_status ON donation_history(status);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_date ON donation_history(donation_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_synthetic ON donation_history(is_synthetic);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_cert ON donation_history(UPPER(certificate_code));",
]

SQLITE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_donation_history_donor_id ON donation_history(donor_id);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_donor_email ON donation_history(donor_email);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_hospital ON donation_history(hospital_user_id);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_status ON donation_history(status);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_date ON donation_history(donation_date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_synthetic ON donation_history(is_synthetic);",
    "CREATE INDEX IF NOT EXISTS idx_donation_history_cert ON donation_history(certificate_code);",
]


def get_neon_connection():
    """Connects securely to Neon PostgreSQL using environment URL or neon CLI."""
    import psycopg2
    import psycopg2.extras
    db_url = database.DATABASE_URL
    if not db_url:
        cmd = ["neon.cmd", "connection-string", "production"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        db_url = res.stdout.strip()
    return psycopg2.connect(db_url)


def migrate_postgres(dry_run: bool = False, verify_only: bool = False) -> dict[str, Any]:
    print("\n--- [Neon PostgreSQL] Donation History Migration ---")
    conn = get_neon_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Check if table already exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'donation_history'
            );
        """)
        table_exists = cur.fetchone()[0]

        if verify_only:
            if not table_exists:
                print("FAILED: table 'donation_history' does not exist in Neon PostgreSQL.")
                return {"status": "FAILED", "table_exists": False}
            cur.execute("SELECT COUNT(*) FROM donation_history;")
            count = cur.fetchone()[0]
            cur.execute("SELECT certificate_code, donor_name, units, status FROM donation_history ORDER BY id;")
            records = cur.fetchall()
            print(f"VERIFIED: table exists with {count} records:")
            for r in records:
                print(f"  {r[0]}: {r[1]} ({r[2]} units, status={r[3]})")
            return {"status": "VERIFIED", "count": count, "records": records}

        # Apply DDL
        print("Applying DDL for 'donation_history'...")
        cur.execute(POSTGRES_DONATION_HISTORY_DDL)
        for idx_sql in POSTGRES_INDEXES:
            cur.execute(idx_sql)

        # Backfill from legacy donations
        cur.execute("""
            SELECT id, donation_code, donor_name, donor_email, blood_group, units, donation_date, center_name, status
            FROM donations
            ORDER BY id;
        """)
        legacy_donations = cur.fetchall()
        print(f"Found {len(legacy_donations)} legacy donations in 'donations' table.")

        inserted_count = 0
        skipped_count = 0

        for row in legacy_donations:
            (d_id, cert_code, donor_name, donor_email, blood_group, units, d_date, center_name, status) = row
            # Check if certificate already exists
            cur.execute("SELECT id FROM donation_history WHERE UPPER(certificate_code) = UPPER(%s);", (cert_code,))
            if cur.fetchone():
                print(f"  Skipping {cert_code}: already present in donation_history.")
                skipped_count += 1
                continue

            # Check donor mapping
            cur.execute("SELECT id, donor_id FROM donors WHERE LOWER(email) = LOWER(%s) LIMIT 1;", (donor_email,))
            donor_match = cur.fetchone()
            if donor_match:
                donor_id_val = donor_match[0]
                donor_code_val = donor_match[1]
            else:
                donor_id_val = None
                # Check appointment for legacy donor_id code
                cur.execute("SELECT donor_id FROM appointments WHERE LOWER(donor_email) = LOWER(%s) LIMIT 1;", (donor_email,))
                appt_match = cur.fetchone()
                donor_code_val = appt_match[0] if appt_match else None

            # Check hospital mapping
            cur.execute("SELECT hospital_user_id FROM hospital_profiles WHERE LOWER(hospital_name) = LOWER(%s) LIMIT 1;", (center_name,))
            hosp_match = cur.fetchone()
            hospital_user_id_val = hosp_match[0] if hosp_match else None

            # Canonical status
            canonical_status = "CONFIRMED" if (status or "").upper() in ("VERIFIED", "CONFIRMED") else "CONFIRMED"
            now_iso = datetime.now(timezone.utc).isoformat()
            approval_date_val = f"{d_date}T00:00:00Z" if d_date else now_iso
            notes_val = "Legacy verified donation backfilled from donations table"

            cur.execute("""
                INSERT INTO donation_history (
                    donor_id, donor_code, donor_name, donor_email, blood_group, units,
                    donation_date, donation_type, hospital_user_id, hospital_name,
                    appointment_id, status, approved_by_user_id, approval_date, notes,
                    certificate_code, is_synthetic, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                );
            """, (
                donor_id_val, donor_code_val, donor_name, donor_email, blood_group, units or 1,
                d_date, "Whole Blood", hospital_user_id_val, center_name,
                None, canonical_status, None, approval_date_val, notes_val,
                cert_code, 0, approval_date_val, approval_date_val
            ))
            inserted_count += 1
            print(f"  Inserted {cert_code}: {donor_name} ({units} units, {blood_group}, center={center_name})")

        if dry_run:
            print("\n[DRY RUN] Rolling back all Postgres changes...")
            conn.rollback()
            print("[DRY RUN] Neon production database remains unchanged.")
            return {"status": "DRY_RUN_SUCCESS", "inserted": inserted_count, "skipped": skipped_count}
        else:
            # Advance sequence
            cur.execute("SELECT setval('donation_history_id_seq', COALESCE((SELECT MAX(id) FROM donation_history), 1), (SELECT MAX(id) IS NOT NULL FROM donation_history));")
            conn.commit()
            print(f"\n[LIVE] Postgres migration committed successfully. {inserted_count} inserted, {skipped_count} skipped.")
            return {"status": "SUCCESS", "inserted": inserted_count, "skipped": skipped_count}

    except Exception as e:
        conn.rollback()
        print(f"ERROR during Postgres migration: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def migrate_sqlite(db_path: str | Path, dry_run: bool = False, verify_only: bool = False) -> dict[str, Any]:
    print(f"\n--- [Local SQLite] Donation History Migration ({db_path}) ---")
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='donation_history';")
        table_exists = bool(cur.fetchone())

        if verify_only:
            if not table_exists:
                print("FAILED: table 'donation_history' does not exist in SQLite.")
                return {"status": "FAILED", "table_exists": False}
            cur.execute("SELECT COUNT(*) FROM donation_history;")
            count = cur.fetchone()[0]
            cur.execute("SELECT certificate_code, donor_name, units, status FROM donation_history ORDER BY id;")
            records = cur.fetchall()
            print(f"VERIFIED: table exists with {count} records:")
            for r in records:
                print(f"  {r[0]}: {r[1]} ({r[2]} units, status={r[3]})")
            return {"status": "VERIFIED", "count": count, "records": records}

        # Apply DDL
        print("Applying DDL for 'donation_history'...")
        cur.executescript(SQLITE_DONATION_HISTORY_DDL)
        for idx_sql in SQLITE_INDEXES:
            cur.execute(idx_sql)

        # Backfill
        cur.execute("""
            SELECT id, donation_code, donor_name, donor_email, blood_group, units, donation_date, center_name, status
            FROM donations
            ORDER BY id;
        """)
        legacy_donations = cur.fetchall()
        print(f"Found {len(legacy_donations)} legacy donations in 'donations' table.")

        inserted_count = 0
        skipped_count = 0

        for row in legacy_donations:
            d_id = row["id"]
            cert_code = row["donation_code"]
            donor_name = row["donor_name"]
            donor_email = row["donor_email"]
            blood_group = row["blood_group"]
            units = row["units"]
            d_date = row["donation_date"]
            center_name = row["center_name"]
            status = row["status"]

            # Check if certificate already exists
            cur.execute("SELECT id FROM donation_history WHERE UPPER(certificate_code) = UPPER(?);", (cert_code,))
            if cur.fetchone():
                print(f"  Skipping {cert_code}: already present in donation_history.")
                skipped_count += 1
                continue

            # Check donor mapping
            cur.execute("SELECT id, donor_id FROM donors WHERE LOWER(email) = LOWER(?) LIMIT 1;", (donor_email,))
            donor_match = cur.fetchone()
            if donor_match:
                donor_id_val = donor_match["id"]
                donor_code_val = donor_match["donor_id"]
            else:
                donor_id_val = None
                cur.execute("SELECT donor_id FROM appointments WHERE LOWER(donor_email) = LOWER(?) LIMIT 1;", (donor_email,))
                appt_match = cur.fetchone()
                donor_code_val = appt_match["donor_id"] if appt_match else None

            # Check hospital mapping
            cur.execute("SELECT hospital_user_id FROM hospital_profiles WHERE LOWER(hospital_name) = LOWER(?) LIMIT 1;", (center_name,))
            hosp_match = cur.fetchone()
            hospital_user_id_val = hosp_match["hospital_user_id"] if hosp_match else None

            canonical_status = "CONFIRMED" if (status or "").upper() in ("VERIFIED", "CONFIRMED") else "CONFIRMED"
            now_iso = datetime.now(timezone.utc).isoformat()
            approval_date_val = f"{d_date}T00:00:00Z" if d_date else now_iso
            notes_val = "Legacy verified donation backfilled from donations table"

            cur.execute("""
                INSERT INTO donation_history (
                    donor_id, donor_code, donor_name, donor_email, blood_group, units,
                    donation_date, donation_type, hospital_user_id, hospital_name,
                    appointment_id, status, approved_by_user_id, approval_date, notes,
                    certificate_code, is_synthetic, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                );
            """, (
                donor_id_val, donor_code_val, donor_name, donor_email, blood_group, units or 1,
                d_date, "Whole Blood", hospital_user_id_val, center_name,
                None, canonical_status, None, approval_date_val, notes_val,
                cert_code, 0, approval_date_val, approval_date_val
            ))
            inserted_count += 1
            print(f"  Inserted {cert_code}: {donor_name} ({units} units, {blood_group}, center={center_name})")

        if dry_run:
            print("\n[DRY RUN] Rolling back all SQLite changes...")
            conn.rollback()
            print("[DRY RUN] SQLite database remains unchanged.")
            return {"status": "DRY_RUN_SUCCESS", "inserted": inserted_count, "skipped": skipped_count}
        else:
            conn.commit()
            print(f"\n[LIVE] SQLite migration committed successfully. {inserted_count} inserted, {skipped_count} skipped.")
            return {"status": "SUCCESS", "inserted": inserted_count, "skipped": skipped_count}

    except Exception as e:
        conn.rollback()
        print(f"ERROR during SQLite migration: {e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate donation history schema and backfill legacy donations.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without committing changes.")
    parser.add_argument("--verify-only", action="store_true", help="Verify donation_history table and backfilled records.")
    parser.add_argument("--target", choices=["postgres", "sqlite", "both"], default="both", help="Target database.")
    args = parser.parse_args()

    results = {}
    if args.target in ("postgres", "both"):
        results["postgres"] = migrate_postgres(dry_run=args.dry_run, verify_only=args.verify_only)

    if args.target in ("sqlite", "both"):
        results["sqlite"] = migrate_sqlite(database.DATABASE_PATH, dry_run=args.dry_run, verify_only=args.verify_only)

    print("\n=== MIGRATION SUMMARY ===")
    for k, v in results.items():
        print(f"Target {k}: {v['status']}")


if __name__ == "__main__":
    main()
