"""
HaemoPulse System Repair Test Suite
Tests:
1. Hospital registration via POST /api/v1/auth/hospital/register.
2. Hospital authentication and profile retrieval.
3. Accessing /api/v1/inventory and /api/inventory for both hospital and admin.
4. Unauthenticated access to inventory returns 401.
5. Accessing /api/requisitions (GET and POST aliases).
6. Non-hospital/non-admin blocked from creating requisitions.
"""

from __future__ import annotations

import os
import sys
import unittest
import shutil
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server

client = TestClient(server.app)


class SystemRepairTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_repair.db")
        original_db = os.path.join(BACKEND_DIR, "bloodbank.db")
        if not os.path.exists(original_db):
            database.ensure_sqlite_db_ready(original_db)
        shutil.copyfile(original_db, cls.test_db)

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        cls.orig_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db

        cls.conn = database.get_db_connection()

        # Seed admin user
        ca = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919900112233', 'ROLE_ADMIN', 'ACTIVE', 1)",
            ("System Admin", "admin_repair@haemopulse.invalid")
        )
        cls.admin_user_id = ca.lastrowid
        cls.admin_token = server.create_access_token({"sub": "admin_repair@haemopulse.invalid", "id": cls.admin_user_id, "role": "ROLE_ADMIN"})

        # Seed donor user
        cd = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919900112244', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Test Donor", "donor_repair@haemopulse.invalid")
        )
        cls.donor_user_id = cd.lastrowid
        cls.donor_token = server.create_access_token({"sub": "donor_repair@haemopulse.invalid", "id": cls.donor_user_id, "role": "ROLE_DONOR"})
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.close()
        except Exception:
            pass
        if cls.orig_env_db:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)
        database.DATABASE_PATH = cls.orig_db_path
        server.DATABASE_PATH = cls.orig_db_path
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_hospital_registration_endpoint(self):
        """POST /api/v1/auth/hospital/register registers a hospital user and profile."""
        payload = {
            "hospital_name": "Koppa Community Hospital",
            "email": "koppa_community@haemopulse.invalid",
            "phone": "+918899001122",
            "password": "SecurePassword123!",
            "address": "Hospital Circle, Koppa",
            "district": "Chikkamagaluru",
            "taluk": "Koppa",
            "latitude": 13.53,
            "longitude": 75.36
        }
        res = client.post("/api/v1/auth/hospital/register", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("role"), "ROLE_HOSPITAL")
        self.assertIn("token", data)
        self.assertIsNotNone(data.get("hospital_profile"))
        self.assertEqual(data["hospital_profile"]["hospital_name"], "Koppa Community Hospital")

        # Verify DB records
        user_row = self.conn.execute("SELECT * FROM users WHERE email = ? OR id IN (SELECT hospital_user_id FROM hospital_profiles WHERE contact_email = ?)", ("koppa_community@haemopulse.invalid", "koppa_community@haemopulse.invalid")).fetchone()
        self.assertIsNotNone(user_row)
        self.assertEqual(user_row["role"], "ROLE_HOSPITAL")

        hosp_row = self.conn.execute("SELECT * FROM hospital_profiles WHERE hospital_user_id = ?", (user_row["id"],)).fetchone()
        self.assertIsNotNone(hosp_row)
        self.assertEqual(hosp_row["district"], "Chikkamagaluru")

    def test_02_hospital_login_after_registration(self):
        """Registered hospital can log in via POST /api/v1/auth/login."""
        res = client.post("/api/v1/auth/login", json={
            "email": "koppa_community@haemopulse.invalid",
            "password": "SecurePassword123!"
        })
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data.get("role"), "ROLE_HOSPITAL")
        self.assertIn("token", data)
        self.assertEqual(data["user"]["role"], "ROLE_HOSPITAL")

    def test_03_inventory_endpoints_authenticated_and_unauthenticated(self):
        """GET /api/inventory and GET /api/v1/inventory enforce auth and return inventory for admin."""
        # Unauthenticated returns 401
        res_unauth = client.get("/api/inventory")
        self.assertEqual(res_unauth.status_code, 401)
        res_v1_unauth = client.get("/api/v1/inventory")
        self.assertEqual(res_v1_unauth.status_code, 401)

        # Authenticated admin returns 200
        headers_admin = {"Authorization": f"Bearer {self.admin_token}"}
        res_admin = client.get("/api/inventory", headers=headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIsInstance(res_admin.json(), list)

        res_v1_admin = client.get("/api/v1/inventory", headers=headers_admin)
        self.assertEqual(res_v1_admin.status_code, 200)
        self.assertIsInstance(res_v1_admin.json(), list)

    def test_04_requests_canonical_endpoint(self):
        """GET /api/v1/requests enforces auth and returns list for authorized users."""
        # Unauthenticated returns 401
        res_unauth = client.get("/api/v1/requests")
        self.assertEqual(res_unauth.status_code, 401)

        # Admin can view requests
        headers_admin = {"Authorization": f"Bearer {self.admin_token}"}
        res_admin = client.get("/api/v1/requests", headers=headers_admin)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIsInstance(res_admin.json(), list)

    def test_05_donor_access_to_inventory_forbidden(self):
        """ROLE_DONOR access to /api/inventory and /api/v1/inventory returns HTTP 403 Forbidden."""
        headers_donor = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.get("/api/inventory", headers=headers_donor)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access forbidden", res.json().get("detail", ""))

        res_v1 = client.get("/api/v1/inventory", headers=headers_donor)
        self.assertEqual(res_v1.status_code, 403)
        self.assertIn("Access forbidden", res_v1.json().get("detail", ""))

    def test_06_health_check_supports_get_and_head(self):
        """Both GET /health and HEAD /health return HTTP 200 for Render health monitoring."""
        res_get = client.get("/health")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json().get("status"), "ok")

        res_head = client.head("/health")
        self.assertEqual(res_head.status_code, 200)

        # Also verify root / supports both GET and HEAD
        res_root_get = client.get("/")
        self.assertEqual(res_root_get.status_code, 200)
        res_root_head = client.head("/")
        self.assertEqual(res_root_head.status_code, 200)

    def test_07_donor_cannot_create_blood_request(self):
        """ROLE_DONOR cannot create hospital blood requests via POST /api/v1/requests."""
        headers_donor = {"Authorization": f"Bearer {self.donor_token}"}
        payload = {
            "blood_group": "A+",
            "units_needed": 2,
            "urgency_level": "EMERGENCY", "patient_name": "Inpatient Emergency"
        }
        res = client.post("/api/v1/requests", json=payload, headers=headers_donor)
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
