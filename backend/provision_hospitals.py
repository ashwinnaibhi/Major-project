"""
Provision dedicated hospital login accounts and synchronize government hospitals.
Enforces the <taluk>_phc@haemopulse.in login identity standard across all 31 districts
and 239 taluks of Karnataka while keeping real notification contact emails separated.
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


def clean_taluk_name(taluk: str) -> str:
    """Normalize taluk name to clean snake_case slug."""
    return re.sub(r"[^a-z0-9]+", "_", (taluk or "karnataka").lower().strip()).strip("_") or "general"


def generate_hospital_slug(taluk: str, hospital_name: str) -> str:
    """Generate slug according to standard rules: chc, dh, gh, hims, mcgann, ghpc, etc."""
    h_lower = (hospital_name or "").lower()
    if "ghpc" in h_lower or ("koppa" in h_lower and "general" in h_lower):
        return "ghpc"
    if "nr pura" in h_lower or "nrpura" in h_lower:
        return "nrpura"
    if "mcgann" in h_lower:
        return "mcgann"
    if "hims" in h_lower or "medical sciences" in h_lower:
        return "hims"
    if "wenlock" in h_lower:
        return "wenlock"
    if "kims" in h_lower:
        return "kims"
    if "vims" in h_lower:
        return "vims"
    if "bowring" in h_lower:
        return "bowring"
    if "kc general" in h_lower or "k c general" in h_lower:
        return "kc"
    if "victoria" in h_lower:
        return "victoria"
    if "district hospital" in h_lower or " dh" in h_lower or h_lower.endswith("dh"):
        return "dh"
    if "chc" in h_lower or "community health" in h_lower:
        return "chc"
    if "general hospital" in h_lower or " gh" in h_lower or h_lower.endswith("gh"):
        return "gh"
    if "phc" in h_lower or "primary health" in h_lower:
        return "phc"

    t_clean = clean_taluk_name(taluk)
    words = re.findall(r"[a-z0-9]+", h_lower)
    meaningful = [w for w in words if w not in {
        "hospital", "centre", "center", "health", "care", "government", "govt",
        "the", "and", "of", "in", "taluk", "district", "road", "karnataka", t_clean
    }]
    if meaningful:
        return "_".join(meaningful)[:12]
    return "".join(w[0] for w in words if w)[:6] or "hosp"


def generate_hospital_username(taluk: str, hospital_name: str, conn: Any = None, exclude_user_id: int | None = None) -> str:
    """
    Returns standard dedicated login identity:
    Primary facility: <taluk>_phc@haemopulse.in
    Preserved accounts:
      User 3: koppa_ghpc@haemopulse.in
      User 16: koppa_nrpura@haemopulse.in
    Collision resolution:
      Secondary facility in same taluk: <taluk>_<slug>_phc@haemopulse.in
    """
    t_clean = clean_taluk_name(taluk)
    h_lower = (hospital_name or "").lower().strip()

    # Preserved account: Koppa General Hospital (User 3)
    if "koppa" in t_clean and ("ghpc" in h_lower or "general" in h_lower):
        return "koppa_ghpc@haemopulse.in"

    # Preserved account: Koppa NR Pura (User 16)
    if ("nrpura" in t_clean or "narasimharajapura" in t_clean or "koppa" in t_clean) and ("nrpura" in h_lower or "nr pura" in h_lower):
        if exclude_user_id == 16:
            return "koppa_nrpura@haemopulse.in"

    base = f"{t_clean}_phc@haemopulse.in"
    if not conn:
        return base

    existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (base,)).fetchone()
    if not existing or (exclude_user_id and existing["id"] == exclude_user_id):
        return base

    # Deterministic collision resolution: qualify with slug
    slug = generate_hospital_slug(taluk, hospital_name)
    candidate = f"{t_clean}_{slug}_phc@haemopulse.in"
    counter = 1
    while True:
        existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (candidate,)).fetchone()
        if not existing or (exclude_user_id and existing["id"] == exclude_user_id):
            return candidate
        counter += 1
        candidate = f"{t_clean}_{slug}_{counter}_phc@haemopulse.in"


def provision_all_hospitals(initial_password: str = DEFAULT_INITIAL_PASSWORD, dry_run: bool = False, conn: Any = None) -> dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = database.get_db_connection()
        close_conn = True
    now_iso = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    results: dict[str, Any] = {
        "migrated": [],
        "provisioned": [],
        "unchanged": [],
        "errors": [],
        "preserved_accounts": [],
        "collisions_resolved": [],
        "by_district": {},
        "by_category": {},
        "total_facilities": 0,
        "blood_banks_count": 0,
        "no_blood_banks_count": 0,
    }

    session_allocated_usernames: set[str] = set()

    # 1. Migrate / Preserve User ID 3 (General Hospital Koppa)
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
                    category = 'Taluk Hospital',
                    has_blood_bank = 1,
                    verification_status = 'VERIFIED',
                    blood_bank_status = 'VERIFIED',
                    is_centroid_coordinates = 0,
                    contact_phone = COALESCE(contact_phone, '08265-221234'),
                    must_change_password = ?,
                    updated_at = ?
                WHERE hospital_user_id = ?
            """, (contact_email, must_change, now_iso, u3_id))
        else:
            conn.execute("""
                INSERT INTO hospital_profiles
                (hospital_user_id, hospital_name, address, district, taluk, latitude, longitude, contact_email, contact_phone, category, has_blood_bank, verification_status, blood_bank_status, is_centroid_coordinates, must_change_password, created_at, updated_at)
                VALUES (?, 'General Hospital Koppa', 'Hospital Road, Koppa, Chikmagalur - 577126', 'Chikkamagaluru', 'Koppa', 13.5333, 75.3667, ?, '08265-221234', 'Taluk Hospital', 1, 'VERIFIED', 'VERIFIED', 0, ?, ?, ?)
            """, (u3_id, contact_email, must_change, now_iso, now_iso))
        results["migrated"].append({"id": u3_id, "username": target_username, "contact_email": contact_email})
        results["preserved_accounts"].append({"id": u3_id, "username": target_username, "name": "General Hospital Koppa"})

    # 2. Migrate / Preserve User ID 16 (Koppa NR Pura)
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
                    category = 'Taluk Hospital',
                    has_blood_bank = 1,
                    verification_status = 'VERIFIED',
                    blood_bank_status = 'VERIFIED',
                    is_centroid_coordinates = 0,
                    contact_phone = COALESCE(contact_phone, '08265-221999'),
                    updated_at = ?
                WHERE hospital_user_id = ?
            """, (contact_email, must_change, now_iso, u16_id))
        results["migrated"].append({"id": u16_id, "username": target_username, "contact_email": contact_email})
        results["preserved_accounts"].append({"id": u16_id, "username": target_username, "name": "Koppa NR Pura"})

    # 3. Load Statewide Karnataka Government Hospitals JSON
    json_path = BACKEND_DIR / "karnataka_government_hospitals.json"
    if json_path.is_file():
        with open(json_path, "r", encoding="utf-8") as f:
            hospitals_data = json.load(f)

        results["total_facilities"] = len(hospitals_data)

        results["verified_facilities_count"] = 0
        results["provisional_facilities_count"] = 0
        results["verified_blood_banks_count"] = 0
        results["unknown_blood_banks_count"] = 0
        results["no_blood_banks_count"] = 0

        # Account for User 3 and User 16
        if user_3:
            session_allocated_usernames.add("koppa_ghpc@haemopulse.in")
            results["verified_facilities_count"] += 1
            results["verified_blood_banks_count"] += 1
        if user_16:
            session_allocated_usernames.add("koppa_nrpura@haemopulse.in")
            results["verified_facilities_count"] += 1
            results["verified_blood_banks_count"] += 1

        for h in hospitals_data:
            taluk = h.get("taluk") or "Karnataka"
            district = h.get("district") or "Karnataka"
            h_name = h.get("name")
            category = h.get("category") or "Taluk Hospital"
            has_bb = bool(h.get("has_blood_bank", False))
            ver_status = h.get("verification_status", "PROVISIONAL")
            bb_status = h.get("blood_bank_status", "UNKNOWN")
            is_centroid = 1 if h.get("is_centroid_coordinates") else 0
            phone_val = h.get("phone")

            if not h_name:
                continue

            # Stats aggregation
            dist_stats = results["by_district"].setdefault(district, {
                "total": 0, "with_blood_bank": 0, "without_blood_bank": 0, "taluks": set()
            })
            dist_stats["total"] += 1
            dist_stats["taluks"].add(taluk)
            if has_bb:
                dist_stats["with_blood_bank"] += 1
                results["blood_banks_count"] += 1
            else:
                dist_stats["without_blood_bank"] += 1
                results["no_blood_banks_count"] += 1

            if ver_status == "VERIFIED":
                results["verified_facilities_count"] += 1
            else:
                results["provisional_facilities_count"] += 1

            if bb_status == "VERIFIED":
                results["verified_blood_banks_count"] += 1
            elif bb_status == "UNKNOWN":
                results["unknown_blood_banks_count"] += 1
            else:
                results["no_blood_banks_count"] += 1

            results["by_category"][category] = results["by_category"].get(category, 0) + 1

            # Special case: General Hospital Koppa is User ID 3 (already handled)
            if "koppa" in taluk.lower() and "general" in h_name.lower():
                continue

            # Determine dedicated login username for facility
            t_clean = clean_taluk_name(taluk)
            primary_username = f"{t_clean}_phc@haemopulse.in"

            # Check if this facility already exists by taluk + hospital_name OR by primary_username
            existing_by_profile = conn.execute("""
                SELECT u.id, u.email, u.name, hp.hospital_name, hp.taluk
                FROM users u
                JOIN hospital_profiles hp ON u.id = hp.hospital_user_id
                WHERE (LOWER(hp.taluk) = LOWER(?) AND LOWER(hp.hospital_name) = LOWER(?))
                   OR LOWER(u.email) = LOWER(?)
                ORDER BY u.id ASC
                LIMIT 1
            """, (taluk, h_name, primary_username)).fetchone()

            if existing_by_profile:
                username = existing_by_profile["email"]
                session_allocated_usernames.add(username)
                u_id = existing_by_profile["id"]
                results["unchanged"].append({
                    "name": h_name, "username": username, "id": u_id,
                    "taluk": taluk, "district": district, "has_blood_bank": has_bb
                })
                try:
                    conn.execute("""
                        UPDATE hospital_profiles
                        SET hospital_name = ?,
                            address = ?,
                            district = ?,
                            taluk = ?,
                            latitude = ?,
                            longitude = ?,
                            category = COALESCE(category, ?),
                            has_blood_bank = ?,
                            verification_status = ?,
                            blood_bank_status = ?,
                            is_centroid_coordinates = ?,
                            contact_phone = ?
                        WHERE hospital_user_id = ?
                    """, (
                        h_name, h.get("address", ""), district, taluk,
                        h.get("latitude"), h.get("longitude"),
                        category, 1 if has_bb else 0, ver_status, bb_status, is_centroid, phone_val, u_id
                    ))
                    conn.execute("UPDATE users SET name = ? WHERE id = ?", (h_name, u_id))
                except Exception:
                    pass
                continue

            if primary_username not in session_allocated_usernames:
                # Check DB for collision with a different user
                db_existing = conn.execute(
                    "SELECT id, email FROM users WHERE LOWER(email) = LOWER(?)", (primary_username,)
                ).fetchone()
                if not db_existing:
                    username = primary_username
                else:
                    username = generate_hospital_username(taluk, h_name, conn=conn)
                    results["collisions_resolved"].append({
                        "facility": h_name, "taluk": taluk, "username": username
                    })
            else:
                # In-session collision (multiple facilities in the same taluk)
                slug = generate_hospital_slug(taluk, h_name)
                candidate = f"{t_clean}_{slug}_phc@haemopulse.in"
                counter = 1
                while candidate in session_allocated_usernames or conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (candidate,)).fetchone():
                    counter += 1
                    candidate = f"{t_clean}_{slug}_{counter}_phc@haemopulse.in"
                username = candidate
                results["collisions_resolved"].append({
                    "facility": h_name, "taluk": taluk, "username": username
                })

            session_allocated_usernames.add(username)

            # Check if user with this username already exists in database
            existing_user = conn.execute(
                "SELECT id, password, must_change_password FROM users WHERE LOWER(email) = LOWER(?)",
                (username,)
            ).fetchone()

            if existing_user:
                u_id = existing_user["id"]
                results["unchanged"].append({
                    "name": h_name, "username": username, "id": u_id,
                    "taluk": taluk, "district": district, "has_blood_bank": has_bb
                })
                try:
                    conn.execute("""
                        UPDATE hospital_profiles
                        SET category = COALESCE(category, ?),
                            has_blood_bank = ?,
                            verification_status = ?,
                            blood_bank_status = ?,
                            is_centroid_coordinates = ?,
                            contact_phone = ?
                        WHERE hospital_user_id = ?
                    """, (category, 1 if has_bb else 0, ver_status, bb_status, is_centroid, phone_val, u_id))
                except Exception:
                    pass
            else:
                pw_hash = hash_password(initial_password)
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO users (name, email, password, phone, role, is_verified, status, must_change_password)
                    VALUES (?, ?, ?, ?, 'ROLE_HOSPITAL', 1, 'ACTIVE', 1)
                """, (h_name, username, pw_hash, phone_val or ""))
                u_id = cur.lastrowid

                cur.execute("""
                    INSERT INTO hospital_profiles
                    (hospital_user_id, hospital_name, address, district, taluk, latitude, longitude, contact_phone, category, has_blood_bank, verification_status, blood_bank_status, is_centroid_coordinates, must_change_password, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    u_id, h_name, h.get("address", ""), district, taluk,
                    h.get("latitude"), h.get("longitude"), phone_val,
                    category, 1 if has_bb else 0, ver_status, bb_status, is_centroid,
                    now_iso, now_iso
                ))
                results["provisioned"].append({
                    "name": h_name,
                    "district": district,
                    "taluk": taluk,
                    "username": username,
                    "id": u_id,
                    "has_blood_bank": has_bb,
                    "verification_status": ver_status,
                    "blood_bank_status": bb_status,
                    "category": category
                })

    # Convert sets to counts/lists for JSON serialization
    for d, s in results["by_district"].items():
        s["taluks_count"] = len(s["taluks"])
        s["taluks"] = sorted(list(s["taluks"]))

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
    print(f"================================================================================")
    print(f"HaemoPulse Karnataka Statewide Hospital Account Provisioning {mode_label}")
    print(f"================================================================================")
    target_name = "Neon PostgreSQL (Production)" if database.is_postgres() else "Local SQLite (bloodbank.db)"
    print(f"Database Target: {target_name}")
    print(f"Initial password default: '{DEFAULT_INITIAL_PASSWORD}'")
    summary = provision_all_hospitals(dry_run=is_dry_run)
    print(f"\n--- EXECUTION STATUS ---")
    print(f"Dry run mode: {summary.get('dry_run', False)}")
    print(f"Total Facilities in Dataset: {summary.get('total_facilities', 0)}")
    print(f"Total Districts Covered: {len(summary.get('by_district', {}))}")
    print(f"Verified Facilities: {summary.get('verified_facilities_count', 0)}")
    print(f"Provisional Facilities: {summary.get('provisional_facilities_count', 0)}")
    print(f"Facilities With Verified Blood Bank: {summary.get('verified_blood_banks_count', 0)}")
    print(f"Facilities With Unknown Blood Bank Status: {summary.get('unknown_blood_banks_count', 0)}")
    print(f"Facilities Without Blood Bank (Requisition Hubs): {summary.get('no_blood_banks_count', 0)}")
    print(f"\n--- CATEGORY BREAKDOWN ---")
    for cat, cnt in summary.get("by_category", {}).items():
        print(f"  {cat}: {cnt}")
    print(f"\n--- PRESERVED ACCOUNTS ({len(summary['preserved_accounts'])}) ---")
    for acc in summary["preserved_accounts"]:
        print(f"  ID {acc['id']}: {acc['username']} ({acc['name']})")
    print(f"\n--- MIGRATED ACCOUNTS ({len(summary['migrated'])}) ---")
    for acc in summary["migrated"]:
        print(f"  ID {acc['id']}: {acc['username']} (Contact: {acc['contact_email']})")
    print(f"\n--- PROVISIONING BREAKDOWN ---")
    print(f"Newly Provisioned: {len(summary['provisioned'])}")
    print(f"Unchanged Existing: {len(summary['unchanged'])}")
    print(f"Collisions Resolved: {len(summary['collisions_resolved'])}")
    print(f"\n--- SAMPLE STATEWIDE LOGIN IDENTITIES ---")
    sample_list = summary["provisioned"][:10] if summary["provisioned"] else summary["unchanged"][:10]
    for s in sample_list:
        bb_str = "Blood Bank" if s.get("has_blood_bank") else "No Blood Bank (Requisition Hub)"
        print(f"  {s.get('taluk')} ({s.get('district')}): {s.get('username')} | {s.get('name')} [{bb_str}]")
    print("================================================================================")
