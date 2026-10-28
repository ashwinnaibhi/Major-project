"""
Tests for Hospital Login Email Format and Password Standardization.
Verifies:
1. Normalization of taluk names (<normalized_taluk>_ghpc@haemopulse.in).
2. Sringeri, N.R. Pura, Athani, and Koppa email generation.
3. Rejection of missing, empty, or uncatalogued taluks on registration.
4. Idempotent migration of hospital accounts, preservation of IDs/inventory.
5. Duplicate conflict detection (User 16 and User 26) flagged for manual review.
6. Standardized initial password (1234567890) and must_change_password flag.
7. Donor and admin passwords are completely preserved.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database
import server
from fastapi.testclient import TestClient
from provision_hospitals import (
    DEFAULT_INITIAL_PASSWORD,
    generate_hospital_slug,
    generate_hospital_username,
    hash_password,
    migrate_hospital_accounts_and_passwords,
    normalize_taluk_name,
)


class TestHospitalEmailAndPasswordStandardization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_bloodbank.db")
        master_db = BACKEND_DIR / "bloodbank.db"
        if master_db.is_file():
            shutil.copyfile(str(master_db), cls.test_db)
        else:
            conn = sqlite3.connect(cls.test_db)
            database._migrate_sqlite(conn)
            conn.close()

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        cls.orig_db_path = database.DATABASE_PATH
        cls.orig_server_db_path = server.DATABASE_PATH

        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = getattr(cls, "orig_db_path", database.DATABASE_PATH)
        server.DATABASE_PATH = getattr(cls, "orig_server_db_path", server.DATABASE_PATH)
        if getattr(cls, "orig_env_db", None) is not None:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        os.environ["BLOODBANK_DB_FILE"] = self.test_db
        database.DATABASE_PATH = self.test_db
        server.DATABASE_PATH = self.test_db

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Taluk Normalization Unit Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_01_taluk_normalization_rules(self):
        """Taluk names are normalized cleanly to lowercase alphanumeric slugs."""
        # Sringeri -> sringeri
        self.assertEqual(normalize_taluk_name("Sringeri"), "sringeri")
        # Athani -> athani
        self.assertEqual(normalize_taluk_name("Athani"), "athani")
        # Koppa -> koppa
        self.assertEqual(normalize_taluk_name("Koppa"), "koppa")
        # Narasimharajapura / N.R. Pura aliases -> nrpura
        self.assertEqual(normalize_taluk_name("Narasimharajapura"), "nrpura")
        self.assertEqual(normalize_taluk_name("N.R. Pura"), "nrpura")
        self.assertEqual(normalize_taluk_name("NR Pura"), "nrpura")
        self.assertEqual(normalize_taluk_name("nr_pura"), "nrpura")

    def test_02_empty_or_invalid_taluks_rejected(self):
        """Empty, whitespace-only, or non-alphanumeric taluks raise ValueError."""
        with self.assertRaises(ValueError):
            normalize_taluk_name("")
        with self.assertRaises(ValueError):
            normalize_taluk_name("   ")
        with self.assertRaises(ValueError):
            normalize_taluk_name(None)
        with self.assertRaises(ValueError):
            normalize_taluk_name("---!@#$")

    def test_03_email_username_generation(self):
        """generate_hospital_username follows <normalized_taluk>_ghpc@haemopulse.in convention."""
        self.assertEqual(
            generate_hospital_username("Sringeri", "CHC Sringeri"),
            "sringeri_ghpc@haemopulse.in"
        )
        self.assertEqual(
            generate_hospital_username("N.R. Pura", "Taluk Hospital NR Pura"),
            "nrpura_ghpc@haemopulse.in"
        )
        self.assertEqual(
            generate_hospital_username("Athani", "Athani General Hospital"),
            "athani_ghpc@haemopulse.in"
        )
        self.assertEqual(
            generate_hospital_username("Koppa", "General Hospital Koppa"),
            "koppa_ghpc@haemopulse.in"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Existing Account Migration & Idempotency Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_04_migration_standardizes_emails_and_passwords(self):
        """Migration updates accounts to _ghpc, sets initial password, and flags conflicts."""
        conn = database.get_db_connection()
        summary = migrate_hospital_accounts_and_passwords(conn=conn, dry_run=False)
        conn.close()

        self.assertGreaterEqual(summary["total_inspected"], 240)
        self.assertEqual(summary["duplicate_conflicts"], 2)
        # Check that manual review records contain User 16 and User 26
        manual_ids = [r["id"] for r in summary["manual_review_records"]]
        self.assertIn(16, manual_ids)
        self.assertIn(26, manual_ids)

        # Koppa primary hospital (User 3) retains koppa_ghpc@haemopulse.in
        conn = database.get_db_connection()
        u3 = conn.execute("SELECT email, must_change_password FROM users WHERE id = 3").fetchone()
        self.assertEqual(u3["email"], "koppa_ghpc@haemopulse.in")
        self.assertEqual(u3["must_change_password"], 1)

        # Sringeri (User 17) was updated to sringeri_ghpc@haemopulse.in
        u17 = conn.execute("SELECT email, must_change_password FROM users WHERE id = 17").fetchone()
        self.assertEqual(u17["email"], "sringeri_ghpc@haemopulse.in")
        self.assertEqual(u17["must_change_password"], 1)

        # Narasimharajapura (User 94) was updated to nrpura_ghpc@haemopulse.in
        u94 = conn.execute("SELECT email, must_change_password FROM users WHERE id = 94").fetchone()
        self.assertEqual(u94["email"], "nrpura_ghpc@haemopulse.in")
        self.assertEqual(u94["must_change_password"], 1)
        conn.close()

    def test_05_migration_is_fully_idempotent(self):
        """Running migration a second time makes zero unwanted modifications."""
        conn = database.get_db_connection()
        summary2 = migrate_hospital_accounts_and_passwords(conn=conn, dry_run=False)
        conn.close()

        self.assertEqual(summary2["corrected"], 0)
        self.assertGreaterEqual(summary2["already_correct"], 239)
        self.assertEqual(summary2["duplicate_conflicts"], 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Hospital Registration Validation Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_06_hospital_registration_requires_valid_taluk(self):
        """Registration rejects missing or invalid taluk not in district."""
        # Missing taluk
        bad_payload_no_taluk = {
            "hospital_name": "Test Clinic No Taluk",
            "email": "contact_no_taluk@clinic.org",
            "phone": "9876543210",
            "password": "Password123!",
            "address": "Main Street",
            "district": "Chikkamagaluru",
            "taluk": ""
        }
        res1 = self.client.post("/api/v1/auth/hospital/register", json=bad_payload_no_taluk)
        self.assertEqual(res1.status_code, 400)
        self.assertIn("taluk is required", res1.json()["detail"].lower())

        # Invalid taluk not belonging to district
        bad_payload_wrong_taluk = {
            "hospital_name": "Test Clinic Wrong Taluk",
            "email": "contact_wrong_taluk@clinic.org",
            "phone": "9876543210",
            "password": "Password123!",
            "address": "Main Street",
            "district": "Chikkamagaluru",
            "taluk": "Athani"  # Belagavi district, not Chikkamagaluru
        }
        res2 = self.client.post("/api/v1/auth/hospital/register", json=bad_payload_wrong_taluk)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("not a valid taluk in district", res2.json()["detail"])

    def test_07_successful_hospital_registration_assigns_ghpc_email(self):
        """Valid registration assigns <taluk>_ghpc@haemopulse.in email."""
        reg_payload = {
            "hospital_name": "Athani Community Health Center",
            "email": "contact_athani_test@clinic.org",
            "phone": "9876543211",
            "password": "Password123!",
            "address": "Station Road, Athani",
            "district": "Belagavi",
            "taluk": "Athani"
        }
        res = self.client.post("/api/v1/auth/hospital/register", json=reg_payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        # Primary facility athani_ghpc exists from state dataset, so secondary qualifies with slug
        self.assertTrue(data["user"]["email"].startswith("athani_"))
        self.assertTrue(data["user"]["email"].endswith("_ghpc@haemopulse.in"))
        self.assertEqual(data["user"]["role"], "ROLE_HOSPITAL")
        self.assertEqual(data["hospital_profile"]["taluk"], "Athani")

        # Clean up test registration
        conn = database.get_db_connection()
        user_id = data["user"]["id"]
        conn.execute("DELETE FROM hospital_profiles WHERE hospital_user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Authentication & Security Flow Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_08_hospital_authentication_with_standard_password(self):
        """Hospitals authenticate with 1234567890 and receive must_change_password=True."""
        # Sringeri GHPC login
        res = self.client.post("/api/v1/auth/login", json={
            "email": "sringeri_ghpc@haemopulse.in",
            "password": "1234567890"
        })
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["role"], "ROLE_HOSPITAL")
        self.assertTrue(data["must_change_password"])

        # Koppa GHPC login
        res_k = self.client.post("/api/v1/auth/login", json={
            "email": "koppa_ghpc@haemopulse.in",
            "password": "1234567890"
        })
        self.assertEqual(res_k.status_code, 200, res_k.text)
        self.assertEqual(res_k.json()["role"], "ROLE_HOSPITAL")

        # Narasimharajapura (N.R. Pura) login
        res_nr = self.client.post("/api/v1/auth/login", json={
            "email": "nrpura_ghpc@haemopulse.in",
            "password": "1234567890"
        })
        self.assertEqual(res_nr.status_code, 200, res_nr.text)
        self.assertEqual(res_nr.json()["role"], "ROLE_HOSPITAL")

    def test_09_invalid_password_rejected(self):
        """Incorrect password fails with HTTP 401."""
        res = self.client.post("/api/v1/auth/login", json={
            "email": "sringeri_ghpc@haemopulse.in",
            "password": "wrongpassword"
        })
        self.assertEqual(res.status_code, 401)

    def test_10_donor_and_admin_passwords_preserved(self):
        """Donor and Admin credentials are unchanged by hospital password standardization."""
        conn = database.get_db_connection()
        admin_row = conn.execute("SELECT email, role FROM users WHERE role = 'ROLE_ADMIN'").fetchone()
        self.assertIsNotNone(admin_row)
        self.assertEqual(admin_row["email"].lower(), "admin@haemopulse.in")

        donor_row = conn.execute("SELECT email, role FROM users WHERE LOWER(email) = 'ashwinkumarnsrao@gmail.com'").fetchone()
        self.assertIsNotNone(donor_row)
        self.assertEqual(donor_row["role"], "ROLE_DONOR")
        conn.close()

        # Admin can authenticate with admin password
        res_a = self.client.post("/api/v1/auth/login", json={
            "email": "admin@haemopulse.in",
            "password": "admin@123"
        })
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["role"], "ROLE_ADMIN")

        # Donor can still authenticate with donor password
        res_d = self.client.post("/api/v1/auth/login", json={
            "email": "ashwinkumarnsrao@gmail.com",
            "password": "password123"
        })
        if res_d.status_code != 200:
            res_d = self.client.post("/api/v1/auth/login", json={
                "email": "ashwinkumarnsrao@gmail.com",
                "password": "12345678"
            })
        self.assertEqual(res_d.status_code, 200)
        self.assertEqual(res_d.json()["role"], "ROLE_DONOR")
        self.assertEqual(res_d.status_code, 200)
        self.assertEqual(res_d.json()["role"], "ROLE_DONOR")


if __name__ == "__main__":
    unittest.main()
