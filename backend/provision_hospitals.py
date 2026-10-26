"""
Provision dedicated hospital login accounts and synchronize government hospitals.
Enforces the <taluk>_<slug>@haemopulse.in login identity standard while keeping
real notification contact emails separated.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

import database

DEFAULT_INITIAL_PASSWORD = os.getenv("HOSPITAL_INITIAL_PASSWORD", "haemo@123")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest}"


def generate_hospital_slug(taluk: str, hospital_name: str) -> str:
    """Generate slug according to standard rules: chc, dh, gh, hims, mcgann, ghpc, etc."""
    h_lower = (hospital_name or "").lower()
    if "ghpc" in h_lower or "koppa government" in h_lower:
        return "ghpc"
    if "nr pura" in h_lower or "nrpura" in h_lower:
        return "nrpura"
    if "chc" in h_lower or "community health" in h_lower:
        return "chc"
    if "district hospital" in h_lower or " dh" in h_lower or h_lower.endswith("dh"):
        return "dh"
    if "general hospital" in h_lower or " gh" in h_lower or h_lower.endswith("gh"):
        return "gh"
    if "hims" in h_lower or "medical sciences" in h_lower:
        return "hims"
    if "mcgann" in h_lower:
        return "mcgann"

    t_clean = re.sub(r"[^a-z0-9]", "", (taluk or "").lower().strip())
    words = re.findall(r"[a-z0-9]+", h_lower)
    meaningful = [w for w in words if w not in {
        "hospital", "centre", "center", "health", "care", "government", "govt",
        "the", "and", "of", "in", "taluk", "district", "road", "karnataka", t_clean
    }]
    if meaningful:
        return "_".join(meaningful)[:15]
    return "".join(w[0] for w in words if w)[:6] or "hosp"


def generate_hospital_username(taluk: str, hospital_name: str, conn: Any = None, exclude_user_id: int | None = None) -> str:
    """Returns <taluk>_<slug>@haemopulse.in, ensuring uniqueness if conn provided."""
    t_clean = re.sub(r"[^a-z0-9]", "", (taluk or "karnataka").lower().strip()) or "general"
    slug = generate_hospital_slug(taluk, hospital_name)
    base = f"{t_clean}_{slug}@haemopulse.in"
    if not conn:
        return base

    candidate = base
    counter = 1
    while True:
        existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (candidate,)).fetchone()
        if not existing or (exclude_user_id and existing["id"] == exclude_user_id):
            return candidate
        counter += 1
        candidate = f"{t_clean}_{slug}{counter}@haemopulse.in"


def provision_all_hospitals(initial_password: str = DEFAULT_INITIAL_PASSWORD, dry_run: bool = False, conn: Any = None) -> dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = database.get_db_connection()
        close_conn = True
    now_iso = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    results = {
        "migrated": [],
        "provisioned": [],
        "unchanged": [],
        "errors": [],
    }

    # 1. Migrate User ID 3 (Koppa Government Hospital)
    user_3 = conn.execute("""
        SELECT * FROM users
        WHERE LOWER(email) = 'ashwinkumarns1995@gmail.com'
           OR LOWER(email) = 'koppa_ghpc@haemopulse.in'
           OR (id = 3 AND role = 'ROLE_HOSPITAL')
        LIMIT 1
    """).fetchone()
    if user_3:
        target_username = "koppa_ghpc@haemopulse.in"
        current_email = user_3["email"]
        contact_email = "ashwinkumarns1995@gmail.com" if "gmail" in current_email.lower() else None

        # Check existing hospital_profile
        hp3 = conn.execute("SELECT * FROM hospital_profiles WHERE hospital_user_id = 3").fetchone()
        if hp3 and hp3["contact_email"]:
            contact_email = hp3["contact_email"]
        elif not contact_email:
            contact_email = "ashwinkumarns1995@gmail.com"

        user_3_dict = dict(user_3)
        must_change = 0 if (user_3_dict.get("must_change_password") == 0 and current_email == target_username) else 1
        pw_hash = user_3["password"] if must_change == 0 else hash_password(initial_password)

        u3_id = user_3["id"]
        conn.execute("""
            UPDATE users
            SET email = ?, password = ?, must_change_password = ?, is_verified = 1, status = 'ACTIVE'
            WHERE id = ?
        """, (target_username, pw_hash, must_change, u3_id))

        if hp3:
            conn.execute("""
                UPDATE hospital_profiles
                SET contact_email = ?,
                    hospital_name = 'General Hospital Koppa',
                    district = 'Chikkamagaluru',
                    taluk = 'Koppa',
                    must_change_password = ?,
                    updated_at = ?
                WHERE hospital_user_id = ?
            """, (contact_email, must_change, now_iso, u3_id))
        else:
            conn.execute("""
                INSERT INTO hospital_profiles
                (hospital_user_id, hospital_name, address, district, taluk, latitude, longitude, contact_email, must_change_password, created_at, updated_at)
                VALUES (?, 'General Hospital Koppa', 'Hospital Road, Koppa, Chikmagalur - 577126', 'Chikkamagaluru', 'Koppa', 13.5333, 75.3667, ?, ?, ?, ?)
            """, (u3_id, contact_email, must_change, now_iso, now_iso))
        results["migrated"].append({"id": u3_id, "username": target_username, "contact_email": contact_email})

    # 2. Migrate User ID 16 (Koppa Nr Pura)
    user_16 = conn.execute("""
        SELECT * FROM users
        WHERE LOWER(email) = 'venka.naibhi@gmail.com'
           OR LOWER(email) = 'koppa_nrpura@haemopulse.in'
           OR (id = 16 AND role = 'ROLE_HOSPITAL')
        LIMIT 1
    """).fetchone()
    if user_16:
        target_username = "koppa_nrpura@haemopulse.in"
        current_email = user_16["email"]
        contact_email = "venka.naibhi@gmail.com" if "gmail" in current_email.lower() else None

        hp16 = conn.execute("SELECT * FROM hospital_profiles WHERE hospital_user_id = 16").fetchone()
        if hp16 and hp16["contact_email"]:
            contact_email = hp16["contact_email"]
        elif not contact_email:
            contact_email = "venka.naibhi@gmail.com"

        user_16_dict = dict(user_16)
        must_change = 0 if (user_16_dict.get("must_change_password") == 0 and current_email == target_username) else 1
        pw_hash = user_16["password"] if must_change == 0 else hash_password(initial_password)

        u16_id = user_16["id"]
        conn.execute("""
            UPDATE users
            SET email = ?, password = ?, must_change_password = ?, is_verified = 1, status = 'ACTIVE'
            WHERE id = ?
        """, (target_username, pw_hash, must_change, u16_id))

        if hp16:
            conn.execute("""
                UPDATE hospital_profiles
                SET contact_email = ?,
                    must_change_password = ?,
                    updated_at = ?
                WHERE hospital_user_id = ?
            """, (contact_email, must_change, now_iso, u16_id))
        results["migrated"].append({"id": u16_id, "username": target_username, "contact_email": contact_email})

    # 3. Load Karnataka Government Hospitals JSON
    json_path = BACKEND_DIR / "karnataka_government_hospitals.json"
    if json_path.is_file():
        with open(json_path, "r", encoding="utf-8") as f:
            hospitals_data = json.load(f)

        for h in hospitals_data:
            taluk = h.get("taluk") or "Karnataka"
            h_name = h.get("name")
            if not h_name:
                continue

            # Special case: General Hospital Koppa is User ID 3
            if "koppa" in taluk.lower() and "general" in h_name.lower():
                continue

            username = generate_hospital_username(taluk, h_name, conn=None)

            # Check if user with this username already exists
            existing_user = conn.execute(
                "SELECT id, password, must_change_password FROM users WHERE LOWER(email) = LOWER(?)",
                (username,)
            ).fetchone()

            if existing_user:
                u_id = existing_user["id"]
                results["unchanged"].append({"name": h_name, "username": username, "id": u_id})
            else:
                pw_hash = hash_password(initial_password)
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO users (name, email, password, phone, role, is_verified, status, must_change_password)
                    VALUES (?, ?, ?, ?, 'ROLE_HOSPITAL', 1, 'ACTIVE', 1)
                """, (h_name, username, pw_hash, h.get("phone", "+918000000000")))
                u_id = cur.lastrowid

                cur.execute("""
                    INSERT INTO hospital_profiles
                    (hospital_user_id, hospital_name, address, district, taluk, latitude, longitude, contact_phone, must_change_password, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    u_id, h_name, h.get("address", ""), h.get("district", ""), taluk,
                    h.get("latitude"), h.get("longitude"), h.get("phone", ""),
                    now_iso, now_iso
                ))
                results["provisioned"].append({"name": h_name, "username": username, "id": u_id})

    if dry_run:
        conn.rollback()
        results["dry_run"] = True
    else:
        conn.commit()
        results["dry_run"] = False

    if close_conn:
        conn.close()

    return results


if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    mode_label = "[DRY-RUN PREVIEW (no changes committed)]" if is_dry_run else "[PRODUCTION COMMIT]"
    print(f"Running HaemoPulse Hospital Account Provisioning {mode_label}...")
    print(f"Initial password default: '{DEFAULT_INITIAL_PASSWORD}'")
    summary = provision_all_hospitals(dry_run=is_dry_run)
    print("Provisioning complete!")
    print(f"Dry run: {summary.get('dry_run', False)}")
    print(f"Migrated accounts ({len(summary['migrated'])}): {summary['migrated']}")
    print(f"Newly provisioned ({len(summary['provisioned'])}): {summary['provisioned']}")
    print(f"Unchanged existing ({len(summary['unchanged'])}): {summary['unchanged']}")
