"""Create an authorized non-donor account for a HaemoPulse installation.

Supports both interactive CLI mode and scriptable arguments:
    python create_role_user.py --role ADMIN --name "System Admin" --email "admin@haemopulse.in" --password "SecurePassword123!"

Works transparently with the configured database (SQLite or PostgreSQL via DATABASE_URL).
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

import database

ALLOWED_ROLES = {
    "ADMIN": "ROLE_ADMIN",
    "ROLE_ADMIN": "ROLE_ADMIN",
    "HOSPITAL": "ROLE_HOSPITAL",
    "ROLE_HOSPITAL": "ROLE_HOSPITAL",
    "STAFF": "ROLE_STAFF",
    "ROLE_STAFF": "ROLE_STAFF",
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest}"


def provision_user(role_name: str | None = None, name: str = "", email: str = "", phone: str = "+910000000000", password: str = "", role: str | None = None) -> bool:
    target_role = role or role_name
    if not target_role:
        print("Error: Role is required (ADMIN, HOSPITAL, STAFF).")
        return False
    clean_role = ALLOWED_ROLES.get(target_role.strip().upper())
    if not clean_role:
        print(f"Error: Unsupported role '{target_role}'. Allowed: ADMIN, HOSPITAL, STAFF")
        return False

    clean_email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", clean_email):
        print(f"Error: Invalid email format '{email}'.")
        return False

    clean_name = name.strip()
    if len(clean_name) < 2:
        print("Error: Name must contain at least 2 characters.")
        return False

    if len(password) < 8:
        print("Error: Password must contain at least 8 characters.")
        return False

    conn = database.get_db_connection()
    try:
        # Check if email exists
        existing = conn.execute(
            "SELECT id, role FROM users WHERE LOWER(email) = LOWER(?)", (clean_email,)
        ).fetchone()

        if existing:
            existing_role = existing["role"]
            if existing_role == clean_role:
                hashed_pw = hash_password(password)
                conn.execute(
                    "UPDATE users SET password = ?, is_verified = 1, status = 'ACTIVE' WHERE id = ?",
                    (hashed_pw, existing["id"])
                )
                if clean_role == "ROLE_ADMIN":
                    conn.execute(
                        "UPDATE users SET role = 'ROLE_DISABLED', status = 'DISABLED' WHERE role = 'ROLE_ADMIN' AND LOWER(email) != LOWER(?)",
                        (clean_email,)
                    )
                conn.commit()
                print(f"Successfully updated credentials for existing {clean_role} account {clean_email}.")
                return True
            elif clean_role == "ROLE_ADMIN":
                hashed_pw = hash_password(password)
                conn.execute(
                    "UPDATE users SET password = ?, role = 'ROLE_ADMIN', is_verified = 1, status = 'ACTIVE' WHERE id = ?",
                    (hashed_pw, existing["id"])
                )
                conn.execute(
                    "UPDATE users SET role = 'ROLE_DISABLED', status = 'DISABLED' WHERE role = 'ROLE_ADMIN' AND LOWER(email) != LOWER(?)",
                    (clean_email,)
                )
                conn.commit()
                print(f"Successfully provisioned/updated credentials for ROLE_ADMIN account {clean_email}.")
                return True
            else:
                print(f"Error: User '{clean_email}' already exists with different role '{existing_role}'.")
                return False

        hashed_pw = hash_password(password)
        conn.execute("""
            INSERT INTO users (name, email, password, phone, role, is_verified, status)
            VALUES (?, ?, ?, ?, ?, 1, 'ACTIVE')
        """, (clean_name, clean_email, hashed_pw, phone.strip(), clean_role))
        if clean_role == "ROLE_ADMIN":
            conn.execute(
                "UPDATE users SET role = 'ROLE_DISABLED', status = 'DISABLED' WHERE role = 'ROLE_ADMIN' AND LOWER(email) != LOWER(?)",
                (clean_email,)
            )
        conn.commit()
        print(f"Successfully provisioned {clean_role} account for {clean_email}.")
        return True
    except Exception as exc:
        conn.rollback()
        print(f"Database error while provisioning user: {exc}")
        return False
    finally:
        conn.close()


provision_role_user = provision_user


def main() -> int:
    parser = argparse.ArgumentParser(description="HaemoPulse Role Account Provisioning")
    parser.add_argument("--role", choices=["ADMIN", "HOSPITAL", "STAFF"], help="Role for the new account")
    parser.add_argument("--name", help="Display name for the account")
    parser.add_argument("--email", help="Account email address")
    parser.add_argument("--phone", default="+910000000000", help="Account contact phone")
    parser.add_argument("--password", help="Account password (at least 8 characters)")
    args = parser.parse_args()

    # If all required arguments provided, execute non-interactively
    if args.role and args.name and args.email and args.password:
        success = provision_user(args.role, args.name, args.email, args.phone, args.password)
        return 0 if success else 1

    # Otherwise run interactively
    print("HaemoPulse Role Account Provisioning")
    print(f"Configured Database: {'PostgreSQL' if database.is_postgres() else 'SQLite'}")
    role_input = input("Role [ADMIN/HOSPITAL/STAFF]: ").strip().upper()
    name = input("Account display name: ").strip()
    email = input("Account email: ").strip().lower()
    phone = input("Contact phone [+910000000000]: ").strip() or "+910000000000"
    password = getpass.getpass("Password (at least 8 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Error: Passwords do not match.")
        return 2

    success = provision_user(role_input, name, email, phone, password)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
