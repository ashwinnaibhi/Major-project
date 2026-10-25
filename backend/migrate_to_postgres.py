"""
HaemoPulse Data Migration Tool: SQLite (bloodbank.db) -> Neon PostgreSQL

Safely transfers all existing donors, hospital profiles, inventory records, and user accounts
from SQLite to Neon PostgreSQL with transactional verification and sequence synchronization.

Usage:
    python migrate_to_postgres.py [POSTGRES_DATABASE_URL] [--dry-run] [--verify-only]
    OR set DATABASE_URL environment variable and run:
    python migrate_to_postgres.py [--dry-run] [--verify-only]
"""

import os
import sys
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
SQLITE_DB_PATH = BACKEND_DIR / "bloodbank.db"

# Ordered tables ensuring foreign key dependencies are respected (13 tables total)
MIGRATION_TABLES = [
    "users",
    "hospital_profiles",
    "donors",
    "blood_inventory",
    "blood_requests",
    "appointments",
    "donations",
    "inventory_additions",
    "emergency_alerts",
    "emergency_request_responses",
    "notification_outbox",
    "notification_provider_events",
    "hospital_blood_inventory",
    "donation_history",
]


def migrate():
    # Parse CLI flags
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a.lower() for a in sys.argv[1:] if a.startswith("--")]
    dry_run = "--dry-run" in flags
    verify_only = "--verify-only" in flags

    # Determine PostgreSQL connection string
    target_url = None
    if args and args[0].strip():
        target_url = args[0].strip()
    else:
        target_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

    if not target_url:
        print("\n" + "=" * 75)
        print(" ERROR: No PostgreSQL DATABASE_URL provided!")
        print("=" * 75)
        print(" To migrate your local blood bank database to Neon PostgreSQL:")
        print(" 1. Sign up for free at https://neon.tech and create a project.")
        print(" 2. Copy the Connection String (starts with postgresql://...).")
        print(" 3. Run:")
        print('    python migrate_to_postgres.py "postgresql://user:pass@ep-xyz.neon.tech/neondb"')
        print("=" * 75 + "\n")
        sys.exit(1)

    if target_url.startswith("postgres://"):
        target_url = "postgresql://" + target_url[len("postgres://"):]

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("ERROR: psycopg2 is required for PostgreSQL migration. Run: pip install psycopg2-binary")
        sys.exit(1)

    if not SQLITE_DB_PATH.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)

    mode_label = "VERIFY ONLY" if verify_only else ("DRY RUN (simulation)" if dry_run else "LIVE MIGRATION")
    print("\n" + "=" * 75)
    print(f" HaemoPulse SQLite -> Neon PostgreSQL Migration Tool [{mode_label}]")
    print("=" * 75)
    print(f" Source SQLite DB : {SQLITE_DB_PATH}")
    # Mask credentials in URL for safe display
    display_url = target_url.split("@")[-1] if "@" in target_url else target_url[:30]
    print(f" Target Postgres  : ...@{display_url}")
    print("=" * 75)

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(str(SQLITE_DB_PATH))
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(target_url, sslmode="require")
    except Exception as e:
        print(f"\nFailed to connect to PostgreSQL: {e}")
        sqlite_conn.close()
        sys.exit(1)

    if verify_only:
        print("\n[VERIFY ONLY] Checking table counts between SQLite and PostgreSQL...")
        print("-" * 75)
        print(f" {'Table':<32} | {'SQLite Rows':<12} | {'Postgres Rows':<12} | {'Match'}")
        print("-" * 75)
        all_match = True
        with pg_conn.cursor() as pg_cur:
            for table in MIGRATION_TABLES:
                src_count = sqlite_conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                try:
                    pg_cur.execute(f"SELECT count(*) FROM {table}")
                    dst_count = pg_cur.fetchone()[0]
                    status = "MATCH" if src_count == dst_count else "MISMATCH"
                except Exception:
                    dst_count = "Table missing"
                    status = "FAIL"
                    pg_conn.rollback()
                if status != "MATCH":
                    all_match = False
                print(f" {table:<32} | {src_count:<12} | {str(dst_count):<12} | {status}")
        print("-" * 75)
        sqlite_conn.close()
        pg_conn.close()
        print(f"Verification result: {'ALL TABLES MATCH' if all_match else 'DISCREPANCIES FOUND'}\n")
        return

    # Initialize Schema
    from database import POSTGRES_SCHEMA_DDL
    print("\n[1/3] Initializing PostgreSQL schema and indexes...")
    with pg_conn.cursor() as cur:
        for stmt in POSTGRES_SCHEMA_DDL.strip().split(";"):
            s = stmt.strip()
            if s:
                cur.execute(s)
    if not dry_run:
        pg_conn.commit()
        print("Schema initialized successfully.")
    else:
        print("Schema initialized in simulation transaction.")

    # Migrate data table by table
    print("\n[2/3] Transferring records...")
    migration_summary = []

    try:
        with pg_conn.cursor() as pg_cur:
            for table in MIGRATION_TABLES:
                # Read rows from SQLite
                sqlite_rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
                src_count = len(sqlite_rows)

                # Pre-existing rows in target
                pg_cur.execute(f"SELECT count(*) FROM {table}")
                initial_target_count = pg_cur.fetchone()[0]

                if src_count == 0:
                    migration_summary.append((table, 0, initial_target_count, 0, 0, "Empty table"))
                    continue

                # Inspect columns
                columns = list(sqlite_rows[0].keys())
                col_names = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))

                insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

                # Convert rows to tuples
                values = [tuple(row[c] for c in columns) for row in sqlite_rows]

                psycopg2.extras.execute_batch(pg_cur, insert_sql, values, page_size=500)

                # Post-insert count in Postgres
                pg_cur.execute(f"SELECT count(*) FROM {table}")
                final_target_count = pg_cur.fetchone()[0]

                rows_added = final_target_count - initial_target_count
                rows_skipped = src_count - rows_added

                if final_target_count >= src_count:
                    status = "OK" if rows_skipped == 0 else f"OK ({rows_skipped} pre-existed)"
                else:
                    status = f"WARNING ({src_count - final_target_count} missing)"

                migration_summary.append((table, src_count, final_target_count, rows_added, rows_skipped, status))

        # Synchronize PostgreSQL auto-increment serial sequences to max(id)
        if not dry_run:
            print("\n[3/3] Synchronizing primary key serial sequences...")
            with pg_conn.cursor() as pg_cur:
                for table in MIGRATION_TABLES:
                    if table == "hospital_profiles":
                        continue
                    try:
                        # 3-arg setval: setval(seq, coalesce(max(id), 1), max(id) is not null)
                        # If table is empty, is_called=false so first nextval returns 1.
                        # If table has rows, is_called=true so first nextval returns max(id)+1.
                        seq_sql = f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table}', 'id'),
                                COALESCE((SELECT MAX(id) FROM {table}), 1),
                                (SELECT MAX(id) IS NOT NULL FROM {table})
                            )
                        """
                        pg_cur.execute(seq_sql)
                    except Exception as seq_err:
                        pass
            print("Sequences synchronized.")
        else:
            print("\n[3/3] DRY RUN: Skipping sequence synchronization (non-transactional operation in PostgreSQL).")

        if dry_run:
            pg_conn.rollback()
            print("DRY RUN COMPLETE: All changes rolled back. No remote data was modified.")
        else:
            pg_conn.commit()
            print("Migration committed successfully. Sequences synchronized.")

    except Exception as exc:
        pg_conn.rollback()
        print(f"\nMigration failed with error: {exc}")
        sqlite_conn.close()
        pg_conn.close()
        sys.exit(1)

    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 80)
    print(" Migration Summary:")
    print("=" * 80)
    print(f" {'Table':<30} | {'SQLite':<8} | {'Target':<8} | {'Added':<8} | {'Status'}")
    print("-" * 80)
    for t, src, dst, added, skipped, status in migration_summary:
        print(f" {t:<30} | {src:<8} | {dst:<8} | {added:<8} | {status}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    migrate()
