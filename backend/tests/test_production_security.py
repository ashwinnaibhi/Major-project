"""
HaemoPulse Production Security & Authorization Regression Test Suite

Tests:
1. Role-based access control on POST /api/inventory/add-stock:
   - Donors are strictly blocked (HTTP 403).
   - Staff or other unauthorized roles are blocked (HTTP 403).
   - Unauthenticated callers are rejected (HTTP 401).
   - Database records remain unaltered on forbidden requests.
   - Administrators can update global inventory (HTTP 200).
   - Hospitals can only update their own facility inventory (HTTP 200).
2. JWT Secret production safety:
   - Fails safe with RuntimeError during production startup if JWT_SECRET is missing or default.
   - Allows safe fallback in local development mode.
"""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server

client = TestClient(server.app)


class ProductionSecurityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary test database to prevent polluting production or dev SQLite
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_security_bloodbank.db")
        original_db = os.path.join(BACKEND_DIR, "bloodbank.db")
        shutil.copyfile(original_db, cls.test_db)

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        cls.orig_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db

        conn = sqlite3.connect(cls.test_db)
        conn.row_factory = sqlite3.Row

        # Setup Test Users
        # 1. Admin
        cur = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+911111111111', 'ROLE_ADMIN', 'ACTIVE', 1)",
            ("Security Admin", "sec_admin@example.com")
        )
        cls.admin_id = cur.lastrowid
        cls.admin_token = server.create_access_token({"sub": "sec_admin@example.com", "id": cls.admin_id, "role": "ROLE_ADMIN"})

        # 2. Donor
        cur = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+912222222222', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Security Donor", "sec_donor@example.com")
        )
        cls.donor_id = cur.lastrowid
        cls.donor_token = server.create_access_token({"sub": "sec_donor@example.com", "id": cls.donor_id, "role": "ROLE_DONOR"})

        # 3. Hospital 1
        cur = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+913333333333', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("Hospital One", "sec_hosp1@example.com")
        )
        cls.hosp1_id = cur.lastrowid
        cls.hosp1_token = server.create_access_token({"sub": "sec_hosp1@example.com", "id": cls.hosp1_id, "role": "ROLE_HOSPITAL"})

        # 4. Hospital 2
        cur = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+914444444444', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("Hospital Two", "sec_hosp2@example.com")
        )
        cls.hosp2_id = cur.lastrowid
        cls.hosp2_token = server.create_access_token({"sub": "sec_hosp2@example.com", "id": cls.hosp2_id, "role": "ROLE_HOSPITAL"})

        # 5. Staff
        cur = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+915555555555', 'ROLE_STAFF', 'ACTIVE', 1)",
            ("Staff Member", "sec_staff@example.com")
        )
        cls.staff_id = cur.lastrowid
        cls.staff_token = server.create_access_token({"sub": "sec_staff@example.com", "id": cls.staff_id, "role": "ROLE_STAFF"})

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = cls.orig_db_path
        server.DATABASE_PATH = cls.orig_db_path
        if cls.orig_env_db is not None:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)

        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_donor_cannot_add_stock(self):
        """Verify authenticated donor is blocked from modifying inventory (HTTP 403)."""
        conn = sqlite3.connect(self.test_db)
        initial_count = conn.execute("SELECT units_available FROM blood_inventory WHERE blood_group = 'O+'").fetchone()[0]
        conn.close()

        res = client.post(
            "/api/inventory/add-stock",
            headers={"Authorization": f"Bearer {self.donor_token}"},
            json={"blood_group": "O+", "units": 5}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access forbidden", res.json()["detail"])

        # Verify database remained untouched
        conn = sqlite3.connect(self.test_db)
        post_count = conn.execute("SELECT units_available FROM blood_inventory WHERE blood_group = 'O+'").fetchone()[0]
        conn.close()
        self.assertEqual(initial_count, post_count)

    def test_02_staff_and_unauthorized_roles_cannot_add_stock(self):
        """Verify unauthorized roles (e.g. ROLE_STAFF) and unauthenticated callers receive 403/401."""
        # Unauthenticated
        res_no_auth = client.post("/api/inventory/add-stock", json={"blood_group": "A+", "units": 2})
        self.assertEqual(res_no_auth.status_code, 401)

        # Staff role
        res_staff = client.post(
            "/api/inventory/add-stock",
            headers={"Authorization": f"Bearer {self.staff_token}"},
            json={"blood_group": "A+", "units": 2}
        )
        self.assertEqual(res_staff.status_code, 403)

    def test_03_admin_can_add_stock_to_global_inventory(self):
        """Verify administrator can update global blood_inventory."""
        conn = sqlite3.connect(self.test_db)
        initial_units = conn.execute("SELECT units_available FROM blood_inventory WHERE blood_group = 'AB+'").fetchone()[0]
        conn.close()

        res = client.post(
            "/api/inventory/add-stock",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"blood_group": "AB+", "units": 10}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Global AB+ stock updated", res.json()["message"])

        conn = sqlite3.connect(self.test_db)
        updated_units = conn.execute("SELECT units_available FROM blood_inventory WHERE blood_group = 'AB+'").fetchone()[0]
        conn.close()
        self.assertEqual(updated_units, initial_units + 10)

    def test_04_hospital_can_only_modify_its_own_inventory(self):
        """Verify hospital updates only its own hospital_blood_inventory record."""
        # Hospital 1 adds 3 units of B+
        res1 = client.post(
            "/api/inventory/add-stock",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={"blood_group": "B+", "units": 3}
        )
        self.assertEqual(res1.status_code, 200)

        # Check hospital 1 has 3 units
        conn = sqlite3.connect(self.test_db)
        h1_row = conn.execute(
            "SELECT units_available FROM hospital_blood_inventory WHERE hospital_user_id = ? AND blood_group = 'B+'",
            (self.hosp1_id,)
        ).fetchone()
        self.assertIsNotNone(h1_row)
        self.assertEqual(h1_row[0], 3)

        # Check hospital 2 does NOT have these units
        h2_row = conn.execute(
            "SELECT units_available FROM hospital_blood_inventory WHERE hospital_user_id = ? AND blood_group = 'B+'",
            (self.hosp2_id,)
        ).fetchone()
        self.assertIsNone(h2_row)
        conn.close()

    def test_05_jwt_secret_fails_safe_in_production(self):
        """Verify get_jwt_secret() raises RuntimeError in production if secret is missing or default."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                server.get_jwt_secret()
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        # Check legacy default secret also raises
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": server.LEGACY_INSECURE_SECRET}):
            with self.assertRaises(RuntimeError) as ctx:
                server.get_jwt_secret()
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

        # Valid production secret succeeds
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": "c7f93e98ab1234cd5678ef901234567890abcdef1234567890abcdef12345678"}):
            sec = server.get_jwt_secret()
            self.assertEqual(sec, "c7f93e98ab1234cd5678ef901234567890abcdef1234567890abcdef12345678")

    def test_06_jwt_secret_development_fallback(self):
        """Verify development mode allows safe default secret without crashing."""
        with patch.dict(os.environ, {"ENVIRONMENT": "", "HAEMOPULSE_ENV": "", "RENDER": "", "DATABASE_URL": "", "JWT_SECRET": ""}):
            sec = server.get_jwt_secret()
            self.assertEqual(sec, server.DEV_DEFAULT_JWT_SECRET)


if __name__ == "__main__":
    unittest.main()
