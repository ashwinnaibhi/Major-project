"""Create an authorized non-donor account for a local HaemoPulse installation.

Run after configuring BLOODBANK_DB_FILE (if used) and before logging in with an
ADMIN, HOSPITAL, or STAFF account. Credentials are entered interactively and are
never written to a configuration file or printed.
"""
from __future__ import annotations

import getpass
import hashlib
import os
import re
import secrets
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass
DB_PATH = Path(os.getenv("BLOODBANK_DB_FILE", str(BACKEND_DIR / "bloodbank.db"))).expanduser().resolve()
ALLOWED_ROLES = {"ADMIN": "ROLE_ADMIN", "HOSPITAL": "ROLE_HOSPITAL", "STAFF": "ROLE_STAFF"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def main() -> int:
    print("HaemoPulse role account provisioning (local database only)")
    print(f"Database path: {DB_PATH}")
    role_input = input("Role [ADMIN/HOSPITAL/STAFF]: ").strip().upper()
    if role_input not in ALLOWED_ROLES:
        print("Unsupported role. No account was created.")
        return 2
    name = input("Account display name: ").strip()
    email = input("Account email: ").strip().lower()
    phone = input("Contact phone: ").strip()
    if len(name) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(phone) < 6:
        print("Name, valid email, and phone are required. No account was created.")
        return 2
    password = getpass.getpass("Password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirmation:
        print("Passwords must match and be at least 12 characters. No account was created.")
        return 2

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH))
    try:
        connection.execute("""
          CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_token_expiry TEXT,
            last_verification_email_sent_at TEXT,
            status TEXT DEFAULT 'ACTIVE'
          )
        """)
        connection.execute("""
          INSERT INTO users (name, email, password, phone, role, is_verified, status)
          VALUES (?, ?, ?, ?, ?, 1, 'ACTIVE')
        """, (name, email, hash_password(password), phone, ALLOWED_ROLES[role_input]))
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        print("An account with that email already exists. No account was created.")
        return 2
    finally:
        connection.close()
    print(f"Created {role_input} account for {email}. Keep the credentials secure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
