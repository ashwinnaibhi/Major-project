"""
HaemoPulse Multi-Database Engine Adapter (SQLite for local / PostgreSQL for Neon production)

Provides seamless transparency:
- If DATABASE_URL starts with 'postgresql://' or 'postgres://', connects to PostgreSQL (Neon).
- If DATABASE_URL is unset or starts with 'sqlite://', connects to local SQLite (bloodbank.db).
- Transparently converts SQLite query syntax and '?' placeholders to PostgreSQL '%s'.
- Provides identical dict-like row access (mimicking sqlite3.Row) and cur.lastrowid support.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
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
    last_verification_email_sent_at TEXT,
    must_change_password INTEGER DEFAULT 0
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
    contact_email TEXT,
    contact_phone TEXT,
    category TEXT DEFAULT 'General Hospital',
    has_blood_bank INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT 'PROVISIONAL',
    blood_bank_status TEXT DEFAULT 'UNKNOWN',
    is_centroid_coordinates INTEGER DEFAULT 0,
    must_change_password INTEGER DEFAULT 0,
    initial_password_changed_at TEXT,
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

SQLITE_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    is_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    verification_token_expiry TEXT,
    last_verification_email_sent_at TEXT,
    must_change_password INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    blood_group TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    location TEXT NOT NULL,
    distance_km REAL DEFAULT 5.0,
    last_donation_days INTEGER DEFAULT 180,
    total_donations INTEGER DEFAULT 0,
    donation_frequency INTEGER DEFAULT 2,
    previous_response_rate REAL DEFAULT 0.90,
    preferred_time TEXT DEFAULT 'Morning',
    health_score INTEGER DEFAULT 95,
    availability_status TEXT DEFAULT 'HIGH',
    availability_score REAL DEFAULT 91.5,
    user_id INTEGER,
    last_donation_date TEXT,
    is_available INTEGER DEFAULT 1,
    dob TEXT,
    phone TEXT,
    district TEXT,
    taluk TEXT,
    fictional_address TEXT,
    latitude REAL,
    longitude REAL,
    consent TEXT,
    response_time_hrs REAL
);

CREATE TABLE IF NOT EXISTS blood_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_group TEXT UNIQUE NOT NULL,
    component_type TEXT DEFAULT 'Whole Blood',
    units_available INTEGER DEFAULT 0,
    expiry_date TEXT NOT NULL,
    status TEXT DEFAULT 'AVAILABLE'
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    latitude REAL,
    longitude REAL,
    destination_latitude REAL,
    destination_longitude REAL,
    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assigned_admin_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assigned_admin_id INTEGER NULL,
    units_fulfilled INTEGER DEFAULT 0,
    fulfilled_at TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    inventory_id INTEGER,
    blood_group TEXT NOT NULL,
    component_type TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    donor_id TEXT NOT NULL,
    response TEXT NOT NULL CHECK(response IN ('ACCEPTED', 'REJECTED')),
    created_at TEXT NOT NULL,
    UNIQUE(request_id, donor_id),
    FOREIGN KEY(request_id) REFERENCES blood_requests(id)
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    request_id INTEGER,
    donor_id TEXT,
    recipient_user_id INTEGER,
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
    delivered_at TEXT,
    FOREIGN KEY(request_id) REFERENCES blood_requests(id) ON DELETE SET NULL,
    FOREIGN KEY(recipient_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notification_provider_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    provider_message_id TEXT,
    event_type TEXT NOT NULL,
    event_at TEXT,
    received_at TEXT NOT NULL,
    matched_outbox_id INTEGER,
    FOREIGN KEY(matched_outbox_id) REFERENCES notification_outbox(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS hospital_profiles (
    hospital_user_id INTEGER PRIMARY KEY,
    hospital_name TEXT NOT NULL,
    address TEXT NOT NULL,
    district TEXT,
    taluk TEXT,
    latitude REAL,
    longitude REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT,
    must_change_password INTEGER DEFAULT 0,
    initial_password_changed_at TEXT,
    category TEXT DEFAULT 'General Hospital',
    has_blood_bank INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT 'PROVISIONAL',
    blood_bank_status TEXT DEFAULT 'UNKNOWN',
    is_centroid_coordinates INTEGER DEFAULT 0,
    FOREIGN KEY(hospital_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hospital_blood_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_user_id INTEGER NOT NULL,
    blood_group TEXT NOT NULL,
    component_type TEXT NOT NULL DEFAULT 'Whole Blood',
    units_available INTEGER NOT NULL DEFAULT 0 CHECK(units_available >= 0),
    expiry_date TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(hospital_user_id, blood_group),
    FOREIGN KEY(hospital_user_id) REFERENCES users(id) ON DELETE CASCADE
);

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
    updated_at TEXT NOT NULL,
    requisition_id INTEGER REFERENCES blood_requests(id)
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
        "ALTER TABLE donation_history ADD COLUMN IF NOT EXISTS requisition_id INTEGER REFERENCES blood_requests(id) ON DELETE SET NULL;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password INTEGER DEFAULT 0;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS contact_email TEXT;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS contact_phone TEXT;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'General Hospital';",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS has_blood_bank INTEGER DEFAULT 0;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'PROVISIONAL';",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS blood_bank_status TEXT DEFAULT 'UNKNOWN';",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS is_centroid_coordinates INTEGER DEFAULT 0;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS must_change_password INTEGER DEFAULT 0;",
        "ALTER TABLE hospital_profiles ADD COLUMN IF NOT EXISTS initial_password_changed_at TEXT;"
    ]
    for m_stmt in migration_stmts:
        try:
            conn._conn.cursor().execute(m_stmt)
        except Exception:
            pass
    conn.commit()


def _migrate_sqlite(conn: sqlite3.Connection) -> None:
    """Ensures tables, columns, indexes, and baseline seeds exist in SQLite database."""
    conn.executescript(SQLITE_SCHEMA_DDL)
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
    try:
        u_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if u_cols and "must_change_password" not in u_cols:
            conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        hp_cols = [r[1] for r in conn.execute("PRAGMA table_info(hospital_profiles)").fetchall()]
        if hp_cols:
            if "contact_email" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN contact_email TEXT")
            if "contact_phone" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN contact_phone TEXT")
            if "category" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN category TEXT DEFAULT 'General Hospital'")
            if "has_blood_bank" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN has_blood_bank INTEGER DEFAULT 0")
            if "verification_status" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN verification_status TEXT DEFAULT 'PROVISIONAL'")
            if "blood_bank_status" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN blood_bank_status TEXT DEFAULT 'UNKNOWN'")
            if "is_centroid_coordinates" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN is_centroid_coordinates INTEGER DEFAULT 0")
            if "must_change_password" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN must_change_password INTEGER DEFAULT 0")
            if "initial_password_changed_at" not in hp_cols:
                conn.execute("ALTER TABLE hospital_profiles ADD COLUMN initial_password_changed_at TEXT")
    except Exception:
        pass

    # Baseline seed: Blood inventory
    try:
        b_count = conn.execute("SELECT count(*) FROM blood_inventory").fetchone()[0]
        if b_count == 0:
            for bg in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
                conn.execute(
                    "INSERT OR IGNORE INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status) VALUES (?, 'Whole Blood', 10, '2027-12-31', 'AVAILABLE')",
                    (bg,)
                )
    except Exception:
        pass

    try:
        ensure_admin_account(conn)
    except Exception:
        pass

    # Baseline seed: Hospitals
    try:
        h_count = conn.execute("SELECT count(*) FROM hospital_profiles").fetchone()[0]
        if h_count == 0:
            from provision_hospitals import provision_all_hospitals
            provision_all_hospitals(conn=conn)
    except Exception:
        pass

    conn.commit()


def ensure_sqlite_db_ready(db_path: str | None = None) -> None:
    """Ensures the SQLite database file exists and has all 14 tables with baseline data."""
    path = db_path or (os.getenv("BLOODBANK_DB_FILE") or DATABASE_PATH)
    dir_name = os.path.dirname(os.path.abspath(path))
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    _migrate_sqlite(conn)
    conn.close()


DESIGNATED_ADMIN_EMAIL = "admin@haemopulse.in"
DEFAULT_ADMIN_PASSWORD_HASH = (
    "pbkdf2_sha256$310000$3b8348412b9b0270e8c8af77088a42a6$2bad50a1e21b706c5a0e5d6dc5e71c08fb58289e58ee35b4b5f76f8bbf448458"
)


def _hash_pbkdf2_admin(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest}"


def ensure_admin_account(conn: Any = None) -> dict[str, Any]:
    """Ensures the single designated administrator account (admin@haemopulse.in) exists.
    - Idempotent: does NOT reset or overwrite an existing administrator password on restart.
    - Preserves existing administrator credentials / password hash.
    - If admin@haemopulse.org or an older admin identity exists, migrates login email to admin@haemopulse.in.
    - If no admin exists in a fresh database, initializes admin@haemopulse.in securely.
    - Respects environment variable ADMIN_PASSWORD / ADMIN_INITIAL_PASSWORD or HAEMOPULSE_ADMIN_PASSWORD_HASH if provided.
    - Never exposes passwords or password hashes in logs.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    designated_email = DESIGNATED_ADMIN_EMAIL
    result: dict[str, Any] = {"status": "unchanged", "email": designated_email}

    try:
        # 1. Check if admin@haemopulse.in already exists
        existing_designated = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (designated_email,)
        ).fetchone()

        if existing_designated:
            try:
                u_dict = dict(existing_designated)
            except Exception:
                u_dict = {}
            u_id = u_dict.get("id")
            if u_id:
                if u_dict.get("role") != "ROLE_ADMIN" or u_dict.get("status") != "ACTIVE" or not u_dict.get("is_verified"):
                    conn.execute(
                        "UPDATE users SET role = 'ROLE_ADMIN', status = 'ACTIVE', is_verified = 1 WHERE id = ?",
                        (u_id,)
                    )
                    conn.commit()
            result["status"] = "exists"
            result["user_id"] = u_id
            return result

        # 2. Check if a legacy admin exists (e.g. admin@haemopulse.org, admin@bloodbank.org, or role = 'ROLE_ADMIN')
        legacy_admin = conn.execute("""
            SELECT * FROM users
            WHERE role = 'ROLE_ADMIN'
               OR LOWER(email) = 'admin@haemopulse.org'
               OR LOWER(email) = 'admin@bloodbank.org'
            ORDER BY id ASC
            LIMIT 1
        """).fetchone()

        if legacy_admin:
            try:
                leg_dict = dict(legacy_admin)
            except Exception:
                leg_dict = {}
            leg_id = leg_dict.get("id")
            if leg_id:
                # Migrate legacy admin login identity to admin@haemopulse.in PRESERVING existing password hash
                conn.execute(
                    "UPDATE users SET email = ?, name = 'System Admin', is_verified = 1, status = 'ACTIVE', role = 'ROLE_ADMIN' WHERE id = ?",
                    (designated_email, leg_id)
                )
                conn.commit()
            result["status"] = "migrated"
            result["user_id"] = leg_id
            return result

        # 3. No admin exists at all (fresh database) -> provision designated admin
        env_hash = (os.getenv("HAEMOPULSE_ADMIN_PASSWORD_HASH") or os.getenv("ADMIN_PASSWORD_HASH") or "").strip()
        if env_hash and env_hash.startswith("pbkdf2_"):
            pw_hash = env_hash
        else:
            env_pw = (os.getenv("ADMIN_INITIAL_PASSWORD") or os.getenv("ADMIN_PASSWORD") or os.getenv("HAEMOPULSE_ADMIN_PASSWORD") or "").strip()
            if env_pw and len(env_pw) >= 8:
                pw_hash = _hash_pbkdf2_admin(env_pw)
            else:
                pw_hash = DEFAULT_ADMIN_PASSWORD_HASH

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password, phone, role, is_verified, status, must_change_password)
            VALUES ('System Admin', ?, ?, '+919900112233', 'ROLE_ADMIN', 1, 'ACTIVE', 0)
        """, (designated_email, pw_hash))
        conn.commit()
        result["status"] = "created"
        result["user_id"] = cur.lastrowid
        return result
    finally:
        if close_conn:
            conn.close()


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


if not is_postgres():
    try:
        ensure_sqlite_db_ready()
    except Exception:
        pass
