"""Idempotent additive migration for durable HaemoPulse email notifications.

The application calls migrate(conn) during its existing SQLite initialization path.
Existing rows are preserved; nullable assignments are never guessed or backfilled.
"""
from __future__ import annotations


def migrate(conn):
    cur = conn.cursor()

    def add_column_if_missing(table: str, column: str, declaration: str) -> None:
        names = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in names:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    # Nullable references: historical requests remain explicitly unassigned.
    add_column_if_missing("blood_requests", "hospital_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")
    add_column_if_missing("blood_requests", "assigned_admin_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")

    cur.execute("""
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
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_notification_outbox_due ON notification_outbox(status, next_retry_at, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_notification_outbox_request ON notification_outbox(request_id, event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_notification_outbox_provider_message ON notification_outbox(provider_message_id)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notification_provider_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_key TEXT NOT NULL UNIQUE,
        provider_message_id TEXT,
        event_type TEXT NOT NULL,
        event_at TEXT,
        received_at TEXT NOT NULL,
        matched_outbox_id INTEGER,
        FOREIGN KEY(matched_outbox_id) REFERENCES notification_outbox(id) ON DELETE SET NULL
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_notification_provider_events_message ON notification_provider_events(provider_message_id)")
    return {"hospital_user_id", "assigned_admin_user_id"}
