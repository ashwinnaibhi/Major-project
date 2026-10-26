"""
HaemoPulse Multi-Database Engine Adapter (SQLite for local / PostgreSQL for Neon production)

Provides seamless transparency:
- If DATABASE_URL starts with 'postgresql://' or 'postgres://', connects to PostgreSQL (Neon).
- If DATABASE_URL is unset or starts with 'sqlite://', connects to local SQLite (bloodbank.db).
- Transparently converts SQLite query syntax and '?' placeholders to PostgreSQL '%s'.
- Provides identical dict-like row access (mimicking sqlite3.Row) and cur.lastrowid support.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Iterator, Mapping, Sequence

DATABASE_PATH = os.getenv("BLOODBANK_DB_FILE") or os.path.join(os.path.dirname(__file__), "bloodbank.db")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("POSTGRESQL_URL") or ""


def is_postgres() -> bool:
    url = (DATABASE_URL or "").strip().lower()
    return url.startswith("postgres://") or url.startswith("postgresql://")


def get_clean_postgres_url() -> str:
    url = (DATABASE_URL or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL DDL Schema for Neon / Cloud Database Initialization
# ─────────────────────────────────────────────────────────────────────────────

POSTGRES_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    is_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    verification_token_expiry TEXT,
    last_verification_email_sent_at TEXT
);

CREATE TABLE IF NOT EXISTS donors (
    id SERIAL PRIMARY KEY,
    donor_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    blood_group TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    location TEXT NOT NULL,
    distance_km DOUBLE PRECISION DEFAULT 5.0,
    last_donation_days INTEGER DEFAULT 180,
    total_donations INTEGER DEFAULT 0,
    donation_frequency INTEGER DEFAULT 2,
    previous_response_rate DOUBLE PRECISION DEFAULT 0.90,
    preferred_time TEXT DEFAULT 'Morning',
    health_score INTEGER DEFAULT 95,
    availability_status TEXT DEFAULT 'HIGH',
    availability_score DOUBLE PRECISION DEFAULT 91.5,
    user_id INTEGER,
    last_donation_date TEXT,
    is_available INTEGER DEFAULT 1,
    dob TEXT,
    phone TEXT,
    district TEXT,
    taluk TEXT,
    fictional_address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    consent TEXT,
    response_time_hrs DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS blood_inventory (
    id SERIAL PRIMARY KEY,
    blood_group TEXT UNIQUE NOT NULL,
    component_type TEXT DEFAULT 'Whole Blood',
    units_available INTEGER DEFAULT 0,
    expiry_date TEXT NOT NULL,
    status TEXT DEFAULT 'AVAILABLE'
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id SERIAL PRIMARY KEY,
    hospital_name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units_needed INTEGER NOT NULL,
    urgency_level TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    request_date TEXT NOT NULL,
    hospital_address TEXT,
    contact_phone TEXT,
    created_by_user_id INTEGER,
    district TEXT,
    taluk TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    destination_latitude DOUBLE PRECISION,
    destination_longitude DOUBLE PRECISION,
    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assigned_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assigned_admin_id INTEGER NULL,
    units_fulfilled INTEGER DEFAULT 0,
    fulfilled_at TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    donor_name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    appointment_date TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    status TEXT DEFAULT 'SCHEDULED',
    donor_id TEXT,
    donor_email TEXT,
    center_name TEXT DEFAULT 'Central Blood Bank Hub #1',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS donations (
    id SERIAL PRIMARY KEY,
    donation_code TEXT UNIQUE,
    donor_email TEXT NOT NULL,
    donor_name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units INTEGER DEFAULT 1,
    donation_date TEXT NOT NULL,
    center_name TEXT NOT NULL,
    status TEXT DEFAULT 'Verified'
);

CREATE TABLE IF NOT EXISTS inventory_additions (
    id SERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    inventory_id INTEGER,
    blood_group TEXT NOT NULL,
    component_type TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_alerts (
    id SERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_id INTEGER,
    requested_by_user_id INTEGER NOT NULL,
    donor_id TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    hospital_name TEXT NOT NULL,
    urgency_level TEXT NOT NULL,
    patient_reference TEXT,
    delivery_status TEXT NOT NULL,
    email_configured INTEGER NOT NULL DEFAULT 0,
    delivered INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_request_responses (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES blood_requests(id) ON DELETE CASCADE,
    donor_id TEXT NOT NULL,
    response TEXT NOT NULL CHECK(response IN ('ACCEPTED', 'REJECTED')),
    created_at TEXT NOT NULL,
    UNIQUE(request_id, donor_id)
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id SERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    request_id INTEGER REFERENCES blood_requests(id) ON DELETE SET NULL,
    donor_id TEXT,
    recipient_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    recipient_email TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK(status IN ('PENDING','PROCESSING','RETRY','SUBMITTED','DELIVERED','BOUNCED','FAILED','NEEDS_REVIEW')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    next_retry_at TEXT,
    claimed_by TEXT,
    claimed_at TEXT,
    claim_expires_at TEXT,
    provider_message_id TEXT,
    last_error_code TEXT,
    last_provider_event_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_provider_events (
    id SERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    provider_message_id TEXT,
    event_type TEXT NOT NULL,
    event_at TEXT,
    received_at TEXT NOT NULL,
    matched_outbox_id INTEGER REFERENCES notification_outbox(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS hospital_profiles (
    hospital_user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    hospital_name TEXT NOT NULL,
    address TEXT NOT NULL,
    district TEXT,
    taluk TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hospital_blood_inventory (
    id SERIAL PRIMARY KEY,
    hospital_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blood_group TEXT NOT NULL,
    component_type TEXT NOT NULL DEFAULT 'Whole Blood',
    units_available INTEGER NOT NULL DEFAULT 0 CHECK(units_available >= 0),
    expiry_date TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(hospital_user_id, blood_group)
);

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
    requisition_id INTEGER REFERENCES blood_requests(id) ON DELETE SET NULL,
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

CREATE INDEX IF NOT EXISTS idx_donors_blood_group ON donors(blood_group);
CREATE INDEX IF NOT EXISTS idx_donors_district_taluk ON donors(district, taluk);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email));
CREATE INDEX IF NOT EXISTS idx_donation_history_donor_id ON donation_history(donor_id);
CREATE INDEX IF NOT EXISTS idx_donation_history_donor_email ON donation_history(LOWER(donor_email));
CREATE INDEX IF NOT EXISTS idx_donation_history_hospital ON donation_history(hospital_user_id);
CREATE INDEX IF NOT EXISTS idx_donation_history_status ON donation_history(status);
CREATE INDEX IF NOT EXISTS idx_donation_history_date ON donation_history(donation_date DESC);
CREATE INDEX IF NOT EXISTS idx_donation_history_synthetic ON donation_history(is_synthetic);
CREATE INDEX IF NOT EXISTS idx_donation_history_cert ON donation_history(UPPER(certificate_code));
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_appointment_donor_email ON appointments (LOWER(TRIM(donor_email))) WHERE UPPER(TRIM(status)) IN ('SCHEDULED', 'PENDING', 'CONFIRMED', 'APPROVED');
"""


# ─────────────────────────────────────────────────────────────────────────────
# Row and Cursor Abstractions
# ─────────────────────────────────────────────────────────────────────────────

class RowWrapper:
    """Provides dictionary-like and tuple-like row access, mimicking sqlite3.Row."""
    def __init__(self, mapping: dict):
        self._data = dict(mapping)
        self._keys = list(mapping.keys())
        self._values = list(mapping.values())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self) -> Sequence[str]:
        return self._data.keys()

    def values(self) -> Sequence[Any]:
        return self._data.values()

    def items(self) -> Any:
        return self._data.items()

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: Any) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"<RowWrapper {self._data}>"


def _convert_query_to_postgres(sql: str) -> tuple[str, bool]:
    """Converts SQLite SQL to PostgreSQL syntax:
    - Converts ? parameter placeholders outside string literals to %s
    - Appends RETURNING id to INSERT statements to provide cur.lastrowid
    - Ignores SQLite PRAGMA statements
    """
    cleaned = sql.strip()
    if cleaned.upper().startswith("PRAGMA"):
        return "SELECT 1", False

    # Convert SQLite datetime('now') to PostgreSQL NOW()
    cleaned = re.sub(r"datetime\s*\(\s*'now'\s*\)", "NOW()", cleaned, flags=re.IGNORECASE)

    # Convert ? outside string literals
    pattern = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")|(\?)")
    def repl(m):
        if m.group(1):
            return m.group(1)
        return "%s"
    converted = pattern.sub(repl, cleaned)

    is_insert = converted.strip().upper().startswith("INSERT INTO")
    if is_insert and "RETURNING" not in converted.upper():
        parts = converted.split()
        table_name = parts[2].strip('"\'`') if len(parts) > 2 else ""
        if table_name.lower() == "hospital_profiles":
            converted = converted.rstrip("; \t\n") + " RETURNING hospital_user_id"
        else:
            converted = converted.rstrip("; \t\n") + " RETURNING id"

    return converted, is_insert


class PostgresCursorWrapper:
    """Wraps psycopg2 cursor to offer identical API to sqlite3.Cursor."""
    def __init__(self, real_cursor: Any):
        self._cursor = real_cursor
        self.lastrowid: int | None = None

    def execute(self, query: str, params: Sequence[Any] | None = None) -> PostgresCursorWrapper:
        converted, is_insert = _convert_query_to_postgres(query)
        if params is not None:
            # Flatten or adapt tuple parameters if needed
            self._cursor.execute(converted, params)
        else:
            self._cursor.execute(converted)

        if is_insert and "RETURNING" in converted.upper():
            try:
                row = self._cursor.fetchone()
                if row:
                    self.lastrowid = row[0] if isinstance(row, (tuple, list)) else (
                        row.get("id") or row.get("hospital_user_id")
                    )
            except Exception:
                pass

        return self

    def fetchone(self) -> RowWrapper | None:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return RowWrapper(dict(row))

    def fetchall(self) -> list[RowWrapper]:
        rows = self._cursor.fetchall()
        return [RowWrapper(dict(r)) for r in rows]

    def close(self) -> None:
        self._cursor.close()


class PostgresConnectionWrapper:
    """Wraps psycopg2 connection to mimic sqlite3.Connection with auto-row-factory and execute()."""
    def __init__(self, real_conn: Any):
        self._conn = real_conn

    def execute(self, query: str, params: Sequence[Any] | None = None) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def cursor(self) -> PostgresCursorWrapper:
        import psycopg2.extras
        real_cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return PostgresCursorWrapper(real_cur)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Schema Initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_postgres_schema(conn: PostgresConnectionWrapper) -> None:
    """Ensures all 14 tables, indexes, and required schema updates exist in PostgreSQL."""
    for statement in POSTGRES_SCHEMA_DDL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            conn._conn.cursor().execute(stmt)
    migration_stmts = [
        "ALTER TABLE blood_requests ADD COLUMN IF NOT EXISTS units_fulfilled INTEGER DEFAULT 0;",
        "ALTER TABLE blood_requests ADD COLUMN IF NOT EXISTS fulfilled_at TEXT;",
        "ALTER TABLE donation_history ADD COLUMN IF NOT EXISTS requisition_id INTEGER REFERENCES blood_requests(id) ON DELETE SET NULL;"
    ]
    for m_stmt in migration_stmts:
        try:
            conn._conn.cursor().execute(m_stmt)
        except Exception:
            pass
    conn.commit()


def _migrate_sqlite(conn: sqlite3.Connection) -> None:
    """Ensures tables and columns exist in SQLite database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emergency_request_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            donor_id TEXT NOT NULL,
            response TEXT NOT NULL CHECK(response IN ('ACCEPTED', 'REJECTED')),
            created_at TEXT NOT NULL,
            UNIQUE(request_id, donor_id),
            FOREIGN KEY(request_id) REFERENCES blood_requests(id)
        )
    """)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(blood_requests)").fetchall()]
        if cols and "units_fulfilled" not in cols:
            conn.execute("ALTER TABLE blood_requests ADD COLUMN units_fulfilled INTEGER DEFAULT 0")
        if cols and "fulfilled_at" not in cols:
            conn.execute("ALTER TABLE blood_requests ADD COLUMN fulfilled_at TEXT")
    except Exception:
        pass
    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_appointment_donor_email
            ON appointments (LOWER(TRIM(donor_email)))
            WHERE UPPER(TRIM(status)) IN ('SCHEDULED', 'PENDING', 'CONFIRMED', 'APPROVED')
        """)
    except Exception:
        pass
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(donation_history)").fetchall()]
        if cols and "requisition_id" not in cols:
            conn.execute("ALTER TABLE donation_history ADD COLUMN requisition_id INTEGER REFERENCES blood_requests(id)")
    except Exception:
        pass
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Database Dependency
# ─────────────────────────────────────────────────────────────────────────────

def get_db_connection():
    """Returns a connected database instance (PostgresConnectionWrapper or sqlite3.Connection)."""
    if is_postgres():
        import psycopg2
        url = get_clean_postgres_url()
        raw_conn = psycopg2.connect(url, sslmode="require")
        wrapper = PostgresConnectionWrapper(raw_conn)
        return wrapper
    else:
        env_path = os.getenv("BLOODBANK_DB_FILE")
        if env_path and os.path.exists(env_path):
            db_path = env_path
        else:
            db_path = DATABASE_PATH
        conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        _migrate_sqlite(conn)
        return conn


def get_db() -> Iterator[Any]:
    """FastAPI Request Dependency: provides an isolated connection per request with auto-rollback on error."""
    conn = get_db_connection()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
