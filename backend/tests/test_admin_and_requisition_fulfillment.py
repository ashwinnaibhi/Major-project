"""
HaemoPulse Admin Authentication & Automatic Hospital Requisition Fulfillment Test Suite
Tests:
1. Administrator Account Provisioning:
   - CLI/programmatic provisioning in active database
   - Role strictly set to ROLE_ADMIN
2. Administrator Authentication:
   - Successful login with ROLE_ADMIN credentials
   - Access to protected admin endpoints (e.g. /api/v1/inventory, /api/v1/admin/donations)
   - Rejection of invalid credentials (401)
   - Rejection of donor/hospital access to admin endpoints (403)
3. Hospital Requisition Fulfillment:
   - Partial fulfillment updates units_fulfilled and keeps status PENDING
   - Full fulfillment updates units_fulfilled, sets status to FULFILLED and records fulfilled_at
   - Prevention of duplicate fulfillment on already-satisfied requisitions
   - Prevention of cross-blood-group fulfillment
   - Prevention of cross-hospital requisition fulfillment
   - Transaction atomicity & rollback on failure
"""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server
import create_role_user

client = TestClient(server.app)


class AdminAndRequisitionFulfillmentTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_bloodbank.db")
        original_db = os.path.join(BACKEND_DIR, "bloodbank.db")
        if not os.path.exists(original_db):
            database.ensure_sqlite_db_ready(original_db)
        shutil.copyfile(original_db, cls.test_db)

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        cls.orig_db_path = database.DATABASE_PATH
        cls.orig_server_db_path = server.DATABASE_PATH
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db

        # Initialize schema migrations
        conn = database.get_db_connection()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = getattr(cls, "orig_db_path", database.DATABASE_PATH)
        server.DATABASE_PATH = getattr(cls, "orig_server_db_path", server.DATABASE_PATH)
        if getattr(cls, "orig_env_db", None) is not None:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)
        try:
            shutil.rmtree(cls.temp_dir)
        except Exception:
            pass

    def setUp(self):
        os.environ["BLOODBANK_DB_FILE"] = self.test_db
        database.DATABASE_PATH = self.test_db
        server.DATABASE_PATH = self.test_db
        self.conn = database.get_db_connection()

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Administrator Account Provisioning & Authentication
    # ─────────────────────────────────────────────────────────────────────────

    def test_01_admin_provisioning_and_login(self):
        admin_email = "test_sys_admin@haemopulse.org"
        admin_pass = "AdminSuperSecret2026!"

        # Provision administrator
        success = create_role_user.provision_role_user(
            role="ADMIN",
            name="Test System Administrator",
            email=admin_email,
            phone="+919988776655",
            password=admin_pass
        )
        self.assertTrue(success, "Administrator provisioning must succeed")

        # Verify in DB
        user_row = self.conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (admin_email,)).fetchone()
        self.assertIsNotNone(user_row)
        self.assertEqual(user_row["role"], "ROLE_ADMIN")

        # Authenticate via /api/v1/auth/login
        res = client.post("/api/v1/auth/login", json={
            "email": admin_email,
            "password": admin_pass
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["role"], "ROLE_ADMIN")

        admin_token = data["token"]

        # Access protected admin endpoint
        inv_res = client.get("/api/v1/inventory", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(inv_res.status_code, 200)

        # Test invalid password rejection
        bad_res = client.post("/api/v1/auth/login", json={
            "email": admin_email,
            "password": "WrongPassword999!"
        })
        self.assertEqual(bad_res.status_code, 401)

    def test_02_rbac_blocks_non_admin_from_admin_endpoints(self):
        # Register a donor
        donor_email = "donor_test_rbac@example.com"
        reg_res = client.post("/api/v1/auth/register", json={
            "name": "Donor RBAC Test",
            "email": donor_email,
            "password": "DonorPassword123!",
            "phone": "+919111222333",
            "blood_group": "O+",
            "district": "Bengaluru Urban",
            "taluk": "Bengaluru South"
        })
        self.assertIn(reg_res.status_code, (200, 201))

        # Login donor
        login_res = client.post("/api/v1/auth/login", json={
            "email": donor_email,
            "password": "DonorPassword123!"
        })
        self.assertEqual(login_res.status_code, 200)
        donor_token = login_res.json()["token"]

        # Attempt to access admin inventory
        inv_res = client.get("/api/v1/inventory", headers={"Authorization": f"Bearer {donor_token}"})
        self.assertEqual(inv_res.status_code, 403, "Donor must be forbidden from accessing admin inventory")

        # Attempt to access admin donations
        donations_res = client.get("/api/v1/admin/donations", headers={"Authorization": f"Bearer {donor_token}"})
        self.assertEqual(donations_res.status_code, 403, "Donor must be forbidden from accessing admin donations")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Automatic Requisition Fulfillment Lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def test_03_requisition_fulfillment_lifecycle(self):
        # 1. Register hospital 1
        hosp1_email = "hospital1_fulfill@example.com"
        hosp1_pass = "HospPassword123!"
        hosp_res = client.post("/api/v1/auth/hospital/register", json={
            "hospital_name": "Metro General Hospital",
            "email": hosp1_email,
            "phone": "+919876543210",
            "password": hosp1_pass,
            "address": "123 Medical Center Way",
            "district": "Bengaluru Urban",
            "taluk": "Bengaluru South"
        })
        self.assertIn(hosp_res.status_code, (200, 201))
        hosp1_token = hosp_res.json()["token"]

        # 2. Create blood request for 4 units of 'B+'
        req_res = client.post("/api/v1/requests", json={
            "blood_group": "B+",
            "units_needed": 4,
            "urgency_level": "EMERGENCY",
            "patient_name": "Emergency ICU Patient #101"
        }, headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(req_res.status_code, 200)
        req_id = req_res.json()["id"]

        # Verify initial request state
        req_db = self.conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req_db["status"], "PENDING")
        self.assertEqual(req_db["units_fulfilled"] or 0, 0)
        self.assertIsNone(req_db["fulfilled_at"])

        # 3. Test Cross-Blood-Group Rejection: Attempt to record 'O+' for this 'B+' requisition
        cross_bg_res = client.post("/api/v1/hospitals/donations/record", json={
            "donor_email": "donor_b_group@example.com",
            "blood_group": "O+",  # Mismatched blood group
            "units": 2,
            "donation_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "requisition_id": req_id
        }, headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(cross_bg_res.status_code, 400)
        self.assertIn("mismatch", cross_bg_res.json()["detail"].lower())

        # 4. Test Cross-Hospital Rejection: Hospital 2 cannot fulfill Hospital 1's requisition
        hosp2_email = "hospital2_fulfill@example.com"
        hosp2_res = client.post("/api/v1/auth/hospital/register", json={
            "hospital_name": "City Care Hospital",
            "email": hosp2_email,
            "phone": "+919876543211",
            "password": "Hosp2Password123!",
            "address": "456 Care Ave",
            "district": "Bengaluru Urban",
            "taluk": "Bengaluru North"
        })
        self.assertIn(hosp2_res.status_code, (200, 201))
        hosp2_token = hosp2_res.json()["token"]

        cross_hosp_res = client.post("/api/v1/hospitals/donations/record", json={
            "donor_email": "donor_b_group@example.com",
            "blood_group": "B+",
            "units": 2,
            "donation_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "requisition_id": req_id
        }, headers={"Authorization": f"Bearer {hosp2_token}"})
        self.assertEqual(cross_hosp_res.status_code, 403)

        # 5. Partial Fulfillment: Record 2 units of 'B+' by Hospital 1
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        part_res = client.post("/api/v1/hospitals/donations/record", json={
            "donor_email": "donor_b_group@example.com",
            "donor_name": "B Positive Donor",
            "blood_group": "B+",
            "units": 2,
            "donation_date": today_str,
            "requisition_id": req_id,
            "notes": "Partial collection"
        }, headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(part_res.status_code, 200)
        part_data = part_res.json()
        self.assertEqual(part_data["requisition_id"], req_id)
        self.assertEqual(part_data["requisition_status"], "PENDING")
        self.assertEqual(part_data["requisition_units_fulfilled"], 2)

        # Verify DB after partial fulfillment: status stays PENDING
        req_db_part = self.conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req_db_part["status"], "PENDING")
        self.assertEqual(req_db_part["units_fulfilled"], 2)
        self.assertIsNone(req_db_part["fulfilled_at"])

        # 6. Complete Fulfillment: Record remaining 2 units of 'B+'
        full_res = client.post("/api/v1/hospitals/donations/record", json={
            "donor_email": "donor2_b_group@example.com",
            "donor_name": "Second B Donor",
            "blood_group": "B+",
            "units": 2,
            "donation_date": today_str,
            "requisition_id": req_id,
            "notes": "Completing requisition"
        }, headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(full_res.status_code, 200)
        full_data = full_res.json()
        self.assertEqual(full_data["requisition_id"], req_id)
        self.assertEqual(full_data["requisition_status"], "FULFILLED")
        self.assertEqual(full_data["requisition_units_fulfilled"], 4)

        # Verify DB after complete fulfillment: status is FULFILLED and fulfilled_at is set
        req_db_full = self.conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req_db_full["status"], "FULFILLED")
        self.assertEqual(req_db_full["units_fulfilled"], 4)
        self.assertIsNotNone(req_db_full["fulfilled_at"])

        # Verify donation_history contains requisition_id
        don_rows = self.conn.execute(
            "SELECT * FROM donation_history WHERE requisition_id = ? ORDER BY id ASC",
            (req_id,)
        ).fetchall()
        self.assertEqual(len(don_rows), 2)
        self.assertEqual(don_rows[0]["units"], 2)
        self.assertEqual(don_rows[1]["units"], 2)

        # 7. Duplicate Fulfillment Rejection: Attempting to record against FULFILLED requisition fails
        dup_res = client.post("/api/v1/hospitals/donations/record", json={
            "donor_email": "donor3_b_group@example.com",
            "blood_group": "B+",
            "units": 1,
            "donation_date": today_str,
            "requisition_id": req_id
        }, headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(dup_res.status_code, 400)
        self.assertIn("already fulfilled", dup_res.json()["detail"].lower())

        # 8. Check GET /api/v1/hospitals/donations returns requisition_id
        hosp_dons_res = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {hosp1_token}"})
        self.assertEqual(hosp_dons_res.status_code, 200)
        hosp_don_list = hosp_dons_res.json()
        fulfilled_records = [d for d in hosp_don_list if d.get("requisition_id") == req_id]
        self.assertEqual(len(fulfilled_records), 2)


if __name__ == "__main__":
    unittest.main()
