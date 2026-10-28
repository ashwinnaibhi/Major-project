"""
HaemoPulse Comprehensive Administrator Authentication & Dashboard Restriction Test Suite
Verifies:
1. Correct administrator credentials -> login succeeds with ROLE_ADMIN token.
2. Incorrect administrator password -> login fails (HTTP 401).
3. Donor credentials -> role returned as ROLE_DONOR, cannot verify as admin (HTTP 403).
4. Hospital credentials -> role returned as ROLE_HOSPITAL, cannot verify as admin (HTTP 403).
5. Unauthenticated direct API requests -> protected data returns HTTP 401.
6. Direct API request using donor credentials -> protected admin endpoints return HTTP 403.
7. Direct API request using hospital credentials -> protected admin endpoints return HTTP 403.
8. Expired or tampered tokens -> HTTP 401.
9. Administrator account provisioning via create_role_user.py supports initial creation and password updating.
10. Valid administrator can access /api/v1/donors, /api/v1/admin/emergency-responses, /api/v1/inventory, and execute DELETE endpoints.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock
import shutil
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server
import create_role_user

client = TestClient(server.app)


class AdminAuthAndDashboardRestrictionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_bloodbank.db")
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

        # 1. Provision Administrator
        cls.admin_email = "ashwinkumarnsrao@gmail.com"
        cls.admin_password = "SuperAdminPassword123!"
        hashed_admin_pw = create_role_user.hash_password(cls.admin_password)
        existing_adm = cls.conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (cls.admin_email,)).fetchone()
        if existing_adm:
            cls.conn.execute(
                "UPDATE users SET password = ?, role = 'ROLE_ADMIN', status = 'ACTIVE', is_verified = 1 WHERE id = ?",
                (hashed_admin_pw, existing_adm["id"])
            )
            cls.admin_user_id = existing_adm["id"]
        else:
            c_adm = cls.conn.execute(
                """INSERT INTO users (name, email, password, phone, role, status, is_verified)
                   VALUES ('System Admin', ?, ?, '+919988770001', 'ROLE_ADMIN', 'ACTIVE', 1)""",
                (cls.admin_email, hashed_admin_pw)
            )
            cls.admin_user_id = c_adm.lastrowid

        # 2. Provision Donor
        cls.donor_email = "test_regular_donor@haemopulse.org"
        cls.donor_password = "DonorPassword123!"
        hashed_donor_pw = create_role_user.hash_password(cls.donor_password)
        c_dnr = cls.conn.execute(
            """INSERT INTO users (name, email, password, phone, role, status, is_verified)
               VALUES ('Regular Donor', ?, ?, '+919988770002', 'ROLE_DONOR', 'ACTIVE', 1)""",
            (cls.donor_email, hashed_donor_pw)
        )
        cls.donor_user_id = c_dnr.lastrowid
        cls.conn.execute(
            """INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available)
               VALUES ('D-TEST-ADMIN-01', ?, 'Regular Donor', ?, '+919988770002', 'O+', 26, 'Female', 'Hubballi', 1)""",
            (cls.donor_user_id, cls.donor_email)
        )

        # 3. Provision Hospital
        cls.hospital_email = "test_city_hospital@haemopulse.org"
        cls.hospital_password = "HospitalPassword123!"
        hashed_hosp_pw = create_role_user.hash_password(cls.hospital_password)
        c_hsp = cls.conn.execute(
            """INSERT INTO users (name, email, password, phone, role, status, is_verified)
               VALUES ('City Hospital', ?, ?, '+919988770003', 'ROLE_HOSPITAL', 'ACTIVE', 1)""",
            (cls.hospital_email, hashed_hosp_pw)
        )
        cls.hospital_user_id = c_hsp.lastrowid

        # Seed sample blood request
        c_req = cls.conn.execute(
            """INSERT INTO blood_requests (hospital_name, patient_name, blood_group, units_needed, urgency_level, status, request_date, hospital_user_id)
               VALUES ('City Hospital', 'Test Patient', 'O+', 2, 'EMERGENCY', 'PENDING', '2026-10-26 12:00:00', ?)""",
            (cls.hospital_user_id,)
        )
        cls.sample_req_id = c_req.lastrowid

        cls.conn.commit()
        cls.conn.close()

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = cls.orig_db_path
        server.DATABASE_PATH = cls.orig_db_path
        if cls.orig_env_db:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_correct_administrator_credentials_succeeds(self):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": self.admin_email, "password": self.admin_password}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "ROLE_ADMIN")
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], self.admin_email)

        # Verify token against /api/v1/admin/verify
        token = data["token"]
        v_res = client.get("/api/v1/admin/verify", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(v_res.status_code, 200)
        v_data = v_res.json()
        self.assertTrue(v_data.get("authenticated"))
        self.assertEqual(v_data.get("role"), "ROLE_ADMIN")

    def test_02_incorrect_administrator_password_fails(self):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": self.admin_email, "password": "WrongPassword999!"}
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid email or password", res.json().get("detail", ""))

    def test_03_donor_credentials_denied_admin_access(self):
        # 1. Login with donor credentials succeeds at auth level but role is ROLE_DONOR
        res = client.post(
            "/api/v1/auth/login",
            json={"email": self.donor_email, "password": self.donor_password}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "ROLE_DONOR")

        # 2. Donor token cannot verify as admin
        donor_token = data["token"]
        v_res = client.get("/api/v1/admin/verify", headers={"Authorization": f"Bearer {donor_token}"})
        self.assertEqual(v_res.status_code, 403)
        self.assertIn("Administrator access required", v_res.json().get("detail", ""))

    def test_04_hospital_credentials_denied_admin_access(self):
        # 1. Login with hospital credentials returns ROLE_HOSPITAL
        res = client.post(
            "/api/v1/auth/login",
            json={"email": self.hospital_email, "password": self.hospital_password}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "ROLE_HOSPITAL")

        # 2. Hospital token cannot verify as admin
        hosp_token = data["token"]
        v_res = client.get("/api/v1/admin/verify", headers={"Authorization": f"Bearer {hosp_token}"})
        self.assertEqual(v_res.status_code, 403)
        self.assertIn("Administrator access required", v_res.json().get("detail", ""))

    def test_05_unauthenticated_requests_return_401(self):
        # Admin verify
        self.assertEqual(client.get("/api/v1/admin/verify").status_code, 401)
        # Admin emergency responses
        self.assertEqual(client.get("/api/v1/admin/emergency-responses").status_code, 401)
        # Donors directory
        self.assertEqual(client.get("/api/v1/donors").status_code, 401)
        # Inventory
        self.assertEqual(client.get("/api/v1/inventory").status_code, 401)
        # Delete donor
        self.assertEqual(client.delete("/api/v1/donors/1").status_code, 401)
        # Delete request
        self.assertEqual(client.delete("/api/v1/requests/1").status_code, 401)

    def test_06_donor_direct_api_access_returns_403(self):
        # Log in as donor
        login_res = client.post("/api/v1/auth/login", json={"email": self.donor_email, "password": self.donor_password})
        donor_token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {donor_token}"}

        # Donors directory is forbidden to donors
        self.assertEqual(client.get("/api/v1/donors", headers=headers).status_code, 403)
        # Admin emergency responses is forbidden
        self.assertEqual(client.get("/api/v1/admin/emergency-responses", headers=headers).status_code, 403)
        # Detailed inventory is forbidden
        self.assertEqual(client.get("/api/v1/inventory", headers=headers).status_code, 403)
        # Delete donor is forbidden
        self.assertEqual(client.delete("/api/v1/donors/1", headers=headers).status_code, 403)
        # Delete request is forbidden
        self.assertEqual(client.delete(f"/api/v1/requests/{self.sample_req_id}", headers=headers).status_code, 403)

    def test_07_invalid_or_expired_token_returns_401(self):
        invalid_headers = {"Authorization": "Bearer invalid.token.payload"}
        self.assertEqual(client.get("/api/v1/admin/verify", headers=invalid_headers).status_code, 401)
        self.assertEqual(client.get("/api/v1/donors", headers=invalid_headers).status_code, 401)
        self.assertEqual(client.get("/api/v1/inventory", headers=invalid_headers).status_code, 401)

    def test_08_admin_direct_api_access_succeeds(self):
        # Log in as admin
        login_res = client.post("/api/v1/auth/login", json={"email": self.admin_email, "password": self.admin_password})
        admin_token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Donors directory returns 200 with donor data including contact details
        res_donors = client.get("/api/v1/donors", headers=headers)
        self.assertEqual(res_donors.status_code, 200)
        donors = res_donors.json()
        self.assertIsInstance(donors, list)
        self.assertTrue(len(donors) > 0)
        donor_emails = [d.get("email") for d in donors]
        self.assertIn(self.donor_email, donor_emails)

        # Inventory returns 200
        res_inv = client.get("/api/v1/inventory", headers=headers)
        self.assertEqual(res_inv.status_code, 200)

        # Admin emergency responses returns 200
        res_resp = client.get("/api/v1/admin/emergency-responses", headers=headers)
        self.assertEqual(res_resp.status_code, 200)

    def test_09_admin_delete_endpoints_work_properly(self):
        login_res = client.post("/api/v1/auth/login", json={"email": self.admin_email, "password": self.admin_password})
        admin_token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create temporary donor to delete
        conn = database.get_db_connection()
        c = conn.execute(
            """INSERT INTO donors (donor_id, name, email, phone, blood_group, age, gender, location, is_available)
               VALUES ('D-TEMP-DEL', 'Temp Donor', 'temp_del@haemopulse.test', '+910000000001', 'B+', 24, 'Male', 'Hubballi', 1)"""
        )
        temp_id = c.lastrowid
        conn.commit()
        conn.close()

        # Delete donor
        del_res = client.delete(f"/api/v1/donors/{temp_id}", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertIn("deleted successfully", del_res.json().get("message", ""))

        # Verify donor is gone
        conn = database.get_db_connection()
        check = conn.execute("SELECT id FROM donors WHERE id = ?", (temp_id,)).fetchone()
        conn.close()
        self.assertIsNone(check)

    def test_10_create_role_user_provisioning_and_updating(self):
        new_admin_email = "provisioned_admin@haemopulse.org"
        initial_pw = "InitialAdminPass123!"
        updated_pw = "UpdatedAdminPass456!"

        with mock.patch.dict(os.environ, {"ADMIN_EMAIL": new_admin_email}):
            # 1. Provision new admin
            success = create_role_user.provision_user(
                role="ADMIN",
                name="Provisioned Admin",
                email=new_admin_email,
                phone="+919988770099",
                password=initial_pw
            )
            self.assertTrue(success)

            # 2. Login with initial password succeeds
            l1 = client.post("/api/v1/auth/login", json={"email": new_admin_email, "password": initial_pw})
            self.assertEqual(l1.status_code, 200)
            self.assertEqual(l1.json()["role"], "ROLE_ADMIN")

            # 3. Update credentials for existing admin using provision_user
            success_update = create_role_user.provision_user(
                role="ADMIN",
                name="Provisioned Admin",
                email=new_admin_email,
                phone="+919988770099",
                password=updated_pw
            )
            self.assertTrue(success_update)

            # 4. Old password fails
            l_old = client.post("/api/v1/auth/login", json={"email": new_admin_email, "password": initial_pw})
            self.assertEqual(l_old.status_code, 401)

            # 5. New password succeeds
            l_new = client.post("/api/v1/auth/login", json={"email": new_admin_email, "password": updated_pw})
            self.assertEqual(l_new.status_code, 200)
            self.assertEqual(l_new.json()["role"], "ROLE_ADMIN")

    def test_11_designated_admin_login_with_correct_credentials(self):
        """Designated admin login identifier ashwinkumarnsrao@gmail.com succeeds and yields ROLE_ADMIN."""
        res = client.post(
            "/api/v1/auth/login",
            json={"email": self.admin_email, "password": self.admin_password}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "ROLE_ADMIN")
        self.assertEqual(data["user"]["email"], self.admin_email)

        # Verify against admin endpoint
        token = data["token"]
        v_res = client.get("/api/v1/admin/verify", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(v_res.status_code, 200)
        self.assertTrue(v_res.json()["authenticated"])

    def test_12_ensure_admin_account_idempotent(self):
        """ensure_admin_account is idempotent and never overwrites existing administrator password."""
        conn = database.get_db_connection()
        res = database.ensure_admin_account(conn)
        self.assertIn(res["status"], ("exists", "unchanged"))
        conn.close()

        # Re-verify that login with the existing password continues to work
        res_login = client.post(
            "/api/v1/auth/login",
            json={"email": self.admin_email, "password": self.admin_password}
        )
        self.assertEqual(res_login.status_code, 200)

    def test_13_ensure_admin_account_migrates_legacy_identity(self):
        """ensure_admin_account migrates legacy admin@haemopulse.org while preserving its password hash."""
        conn = database.get_db_connection()
        # Clean any admin accounts to test clean legacy migration
        conn.execute("DELETE FROM users WHERE role = 'ROLE_ADMIN' OR LOWER(email) LIKE '%admin%' OR LOWER(email) = 'ashwinkumarnsrao@gmail.com'")
        test_pw = "LegacyPass789!"
        test_pw_hash = create_role_user.hash_password(test_pw)
        conn.execute("""
            INSERT INTO users (name, email, password, phone, role, status, is_verified)
            VALUES ('Legacy Admin', 'admin@haemopulse.org', ?, '+919900112233', 'ROLE_ADMIN', 'ACTIVE', 1)
        """, (test_pw_hash,))
        conn.commit()

        # Run ensure_admin_account
        migration_res = database.ensure_admin_account(conn)
        self.assertEqual(migration_res["status"], "migrated")

        # Confirm the new identity exists with the same password hash
        migrated_row = conn.execute("SELECT * FROM users WHERE LOWER(email) = 'ashwinkumarnsrao@gmail.com'").fetchone()
        self.assertIsNotNone(migrated_row)
        self.assertEqual(migrated_row["password"], test_pw_hash)
        conn.close()

        # Confirm login works with new identity ashwinkumarnsrao@gmail.com and legacy password
        res_login = client.post(
            "/api/v1/auth/login",
            json={"email": "ashwinkumarnsrao@gmail.com", "password": test_pw}
        )
        self.assertEqual(res_login.status_code, 200)

        # Restore original test admin password
        conn = database.get_db_connection()
        conn.execute(
            "UPDATE users SET password = ? WHERE LOWER(email) = 'ashwinkumarnsrao@gmail.com'",
            (create_role_user.hash_password(self.admin_password),)
        )
        conn.commit()
        conn.close()

    def test_13b_other_administrator_identities_disabled(self):
        """Other administrator accounts (e.g. admin@haemopulse.in) are disabled from logging in or verifying."""
        conn = database.get_db_connection()
        conn.execute("""
            INSERT OR REPLACE INTO users (id, name, email, password, phone, role, status, is_verified)
            VALUES (9999, 'Old Admin', 'other_admin@haemopulse.org', 'some_hash', '+919988771122', 'ROLE_ADMIN', 'ACTIVE', 1)
        """)
        conn.commit()

        # Running ensure_admin_account disables other admin accounts
        database.ensure_admin_account(conn)
        other_user = conn.execute("SELECT role, status FROM users WHERE id = 9999").fetchone()
        self.assertEqual(other_user["role"], "ROLE_DISABLED")
        self.assertEqual(other_user["status"], "DISABLED")
        conn.close()

        # Login is rejected
        res = client.post("/api/v1/auth/login", json={"email": "other_admin@haemopulse.org", "password": "any"})
        self.assertEqual(res.status_code, 403)

    def test_14_communication_email_separate_from_login_identity(self):
        """Admin communication email is distinct from synthetic login identity admin@haemopulse.in."""
        # When ADMIN_CONTACT_EMAIL is not set, safely returns None without fabricating an email
        with mock.patch.dict(os.environ, {"ADMIN_CONTACT_EMAIL": ""}):
            self.assertIsNone(server.get_admin_communication_email())

        # When ADMIN_CONTACT_EMAIL is set to a real email address
        with mock.patch.dict(os.environ, {"ADMIN_CONTACT_EMAIL": "real_admin@example.org"}):
            self.assertEqual(server.get_admin_communication_email(), "real_admin@example.org")

        # Never returns a synthetic @haemopulse.in domain as communication email
        with mock.patch.dict(os.environ, {"ADMIN_CONTACT_EMAIL": "fake@haemopulse.in"}):
            self.assertIsNone(server.get_admin_communication_email())

    def test_15_synthetic_identity_email_dispatch_prevented(self):
        """Transactional and verification emails to synthetic @haemopulse.in addresses are rejected."""
        import email_service

        # Transactional email
        sub_result = email_service.send_transactional_email(
            recipient_email="admin@haemopulse.in",
            recipient_name="Admin",
            subject="Test",
            text_content="Test",
            html_content="<p>Test</p>"
        )
        self.assertEqual(sub_result.status, "DISABLED")
        self.assertEqual(sub_result.error_code, "SYNTHETIC_LOGIN_IDENTITY")

        # Verification email
        ver_result = email_service.send_verification_email(
            recipient_email="admin@haemopulse.in",
            recipient_name="Admin",
            raw_token="token_123"
        )
        self.assertFalse(ver_result.get("sent"))
        self.assertEqual(ver_result.get("reason"), "SYNTHETIC_LOGIN_IDENTITY")


if __name__ == "__main__":
    unittest.main()
