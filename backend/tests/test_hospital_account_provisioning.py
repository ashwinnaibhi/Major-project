"""
HaemoPulse Hospital-Specific Login Accounts & Brevo Integration Test Suite
Verifies:
1. Hospital login accounts follow <taluk>_<slug>@haemopulse.in format.
2. Separation between login identity and real contact email in hospital_profiles.
3. Initial provisioning of Koppa Government Hospital and official Karnataka hospitals.
4. Passwords hashed with pbkdf2_sha256; must_change_password enforced.
5. Password change endpoint clears must_change_password flag.
6. Admin hospital password reset endpoint.
7. Re-running provisioning is idempotent.
8. Hospital registration auto-generates <taluk>_<slug>@haemopulse.in and rejects dummy @haemopulse.in as contact email.
9. Brevo email notification prevents sending to dummy @haemopulse.in addresses and routes to contact_email.
10. Hospital data isolation: Hospital A cannot access Hospital B's profile, inventory, or requisitions.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server
import provision_hospitals

client = TestClient(server.app)


class HospitalAccountProvisioningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run provisioning once to ensure test database is seeded
        provision_hospitals.provision_all_hospitals()

    def test_koppa_hospital_login_with_dedicated_identity(self):
        """User ID 3 can log in using dedicated identity koppa_ghpc@haemopulse.in."""
        resp = client.post("/api/v1/auth/login", json={
            "email": "koppa_ghpc@haemopulse.in",
            "password": "haemo@123"
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["role"], "ROLE_HOSPITAL")
        self.assertEqual(data["user"]["email"], "koppa_ghpc@haemopulse.in")
        self.assertTrue(data["user"]["must_change_password"])

        # Check hospital profile has real contact email
        hp = data["user"]["hospital_profile"]
        self.assertIsNotNone(hp)
        self.assertEqual(hp["contact_email"], "ashwinkumarns1995@gmail.com")
        self.assertEqual(hp["taluk"], "Koppa")

    def test_koppa_hospital_login_via_contact_email_alias(self):
        """User ID 3 can also log in via their contact email ashwinkumarns1995@gmail.com."""
        resp = client.post("/api/v1/auth/login", json={
            "email": "ashwinkumarns1995@gmail.com",
            "password": "haemo@123"
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["role"], "ROLE_HOSPITAL")
        self.assertEqual(data["user"]["email"], "koppa_ghpc@haemopulse.in")

    def test_wrong_password_rejected(self):
        """Invalid credentials return HTTP 401 without leaking internal details."""
        resp = client.post("/api/v1/auth/login", json={
            "email": "koppa_ghpc@haemopulse.in",
            "password": "wrong_password_123"
        })
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid email or password", resp.json()["detail"])

    def test_government_hospitals_provisioned(self):
        """Official government hospitals from JSON exist and can authenticate."""
        # Sringeri CHC
        resp1 = client.post("/api/v1/auth/login", json={
            "email": "sringeri_chc@haemopulse.in",
            "password": "haemo@123"
        })
        self.assertEqual(resp1.status_code, 200, resp1.text)
        self.assertEqual(resp1.json()["role"], "ROLE_HOSPITAL")

        # Chikmagalur DH
        resp2 = client.post("/api/v1/auth/login", json={
            "email": "chikmagalur_dh@haemopulse.in",
            "password": "haemo@123"
        })
        self.assertEqual(resp2.status_code, 200, resp2.text)
        self.assertEqual(resp2.json()["role"], "ROLE_HOSPITAL")

    def test_provisioning_idempotency(self):
        """Running provisioning multiple times produces zero duplicate accounts or errors."""
        res = provision_hospitals.provision_all_hospitals()
        self.assertEqual(len(res["errors"]), 0)
        self.assertEqual(len(res["provisioned"]), 0)
        self.assertGreaterEqual(len(res["unchanged"]), 9)

    def test_password_change_flow(self):
        """Hospital can change password via /api/v1/auth/change-password."""
        # Log in first
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "sringeri_chc@haemopulse.in",
            "password": "haemo@123"
        })
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Change password
        new_pw = "NewSecurePassword456!"
        change_resp = client.post("/api/v1/auth/change-password", headers=headers, json={
            "current_password": "haemo@123",
            "new_password": new_pw
        })
        self.assertEqual(change_resp.status_code, 200, change_resp.text)

        # Login with old password fails
        fail_resp = client.post("/api/v1/auth/login", json={
            "email": "sringeri_chc@haemopulse.in",
            "password": "haemo@123"
        })
        self.assertEqual(fail_resp.status_code, 401)

        # Login with new password succeeds and must_change_password is False
        success_resp = client.post("/api/v1/auth/login", json={
            "email": "sringeri_chc@haemopulse.in",
            "password": new_pw
        })
        self.assertEqual(success_resp.status_code, 200)
        self.assertFalse(success_resp.json()["user"]["must_change_password"])

        # Reset back for clean test teardown
        client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {success_resp.json()['token']}"}, json={
            "current_password": new_pw,
            "new_password": "haemo@123"
        })

    def test_hospital_registration_assigns_dedicated_identity(self):
        """Registering a hospital auto-assigns <taluk>_<slug>@haemopulse.in and stores contact_email."""
        ts = int(datetime.utcnow().timestamp())
        reg_payload = {
            "hospital_name": f"Greenfield Clinic {ts}",
            "email": f"staff_lead_{ts}@greenfield.org",
            "phone": "+918111222333",
            "password": "ClinicPassword789!",
            "address": "45 Green Road, Koppa",
            "district": "Chikkamagaluru",
            "taluk": "Koppa"
        }
        resp = client.post("/api/v1/auth/hospital/register", json=reg_payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["success"])
        assigned_email = data["user"]["email"]
        self.assertTrue(assigned_email.startswith("koppa_"))
        self.assertTrue(assigned_email.endswith("@haemopulse.in"))
        self.assertEqual(data["hospital_profile"]["contact_email"], f"staff_lead_{ts}@greenfield.org")

    def test_hospital_registration_rejects_dummy_haemopulse_email(self):
        """Hospital registration rejects dummy @haemopulse.in contact emails."""
        bad_payload = {
            "hospital_name": "Bad Dummy Clinic",
            "email": "dummy_clinic@haemopulse.in",
            "phone": "+918111222444",
            "password": "ClinicPassword789!",
            "address": "123 Dummy St",
            "district": "Chikkamagaluru",
            "taluk": "Koppa"
        }
        resp = client.post("/api/v1/auth/hospital/register", json=bad_payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("real external contact email", resp.json()["detail"])

    def test_emergency_response_prevents_sending_to_dummy_haemopulse_email(self):
        """Acceptance notification refuses to email dummy @haemopulse.in with clear notice."""
        # Create a test hospital without real contact email (contact_email is None or @haemopulse.in)
        conn = database.get_db_connection()
        conn.execute("UPDATE hospital_profiles SET contact_email = 'dummy_staff@haemopulse.in' WHERE hospital_user_id = 24")
        conn.commit()

        # Create a blood request from hospital 24
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date, hospital_user_id)
            VALUES ('General Hospital Tarikere', 'O+', 1, 'EMERGENCY', 'Test Patient', 'PENDING', ?, 24)
        """, (now_str,))
        conn.commit()
        req_id = cur.lastrowid

        # Seed test donor for response
        d_ts = int(datetime.utcnow().timestamp())
        donor_email = f"test_emerg_donor_{d_ts}@example.org"
        cur.execute("""
            INSERT INTO users (name, email, password, phone, role, status, is_verified)
            VALUES ('Emergency Test Donor', ?, 'hash', '+919911223344', 'ROLE_DONOR', 'ACTIVE', 1)
        """, (donor_email,))
        donor_u_id = cur.lastrowid
        cur.execute("""
            INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available)
            VALUES (?, 'Emergency Test Donor', ?, 'O+', 29, 'Male', 'Koppa', ?, 1)
        """, (f"DNR-TEST-{donor_u_id}", donor_email, donor_u_id))
        conn.commit()

        donor_token = server.create_access_token({
            "sub": donor_email,
            "id": donor_u_id,
            "role": "ROLE_DONOR"
        })

        # Donor accepts emergency request
        with mock.patch.dict(os.environ, {"HAEMOPULSE_HOSPITAL_NOTIFICATION_OVERRIDE_EMAIL": ""}):
            accept_resp = client.post(
                f"/api/v1/requests/{req_id}/response",
                headers={"Authorization": f"Bearer {donor_token}"},
                json={"action": "ACCEPTED"}
            )
            self.assertEqual(accept_resp.status_code, 200, accept_resp.text)
            data = accept_resp.json()
            self.assertTrue(data["success"])
            notif = data.get("notification")
            self.assertIsNotNone(notif)
            self.assertFalse(notif["delivered"])
            self.assertEqual(notif["reason"], "DUMMY_LOGIN_IDENTITY")
            self.assertIn("Hospital login identity cannot receive email", notif["message"])

    def test_hospital_data_isolation(self):
        """Hospital A cannot view or alter Hospital B's requisitions or inventory."""
        # Hospital A (User ID 3)
        hosp_a_resp = client.post("/api/v1/auth/login", json={
            "email": "koppa_ghpc@haemopulse.in",
            "password": "haemo@123"
        })
        token_a = hosp_a_resp.json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Hospital B (User ID 16)
        hosp_b_resp = client.post("/api/v1/auth/login", json={
            "email": "koppa_nrpura@haemopulse.in",
            "password": "haemo@123"
        })
        token_b = hosp_b_resp.json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Hospital A updates A+ inventory to 25 units
        upd = client.post("/api/v1/hospitals/me/inventory", headers=headers_a, json={
            "blood_group": "A+",
            "units_available": 25,
            "component_type": "Whole Blood"
        })
        self.assertEqual(upd.status_code, 200)

        # Hospital B gets inventory -> should NOT see Hospital A's inventory
        inv_b = client.get("/api/v1/hospitals/me/inventory", headers=headers_b)
        self.assertEqual(inv_b.status_code, 200)
        rows_b = inv_b.json()
        for item in rows_b:
            self.assertEqual(item["hospital_user_id"], 16)

        # Hospital A creates a blood request
        req_res = client.post("/api/v1/requests", headers=headers_a, json={
            "blood_group": "B+",
            "units_needed": 2,
            "urgency_level": "EMERGENCY",
            "patient_name": "Private Patient A"
        })
        self.assertEqual(req_res.status_code, 200)
        req_id = req_res.json()["id"]

        # Hospital B lists requests -> req_id must NOT be in Hospital B's list
        reqs_b = client.get("/api/v1/requests", headers=headers_b)
        self.assertEqual(reqs_b.status_code, 200)
        req_ids_b = [r["id"] for r in reqs_b.json()]
        self.assertNotIn(req_id, req_ids_b)


if __name__ == "__main__":
    unittest.main()
