"""
HaemoPulse Emergency Blood Request Response Tests & Hospital Endpoint Role Tests
Verifies:
1. Canonical actions 'ACCEPTED' and 'REJECTED' succeed (HTTP 200) and persist to database.
2. Shortened actions 'ACCEPT' and 'REJECT' are properly normalized to canonical form and succeed (HTTP 200).
3. Invalid actions are rejected with HTTP 400 ('action must be ACCEPTED or REJECTED').
4. Idempotency: Duplicate or updated responses succeed without violating unique constraints.
5. Role-based security: Non-donors receive HTTP 403 on emergency response.
6. Non-existent requests receive HTTP 404.
7. Donor requests list (GET /api/v1/requests) accurately populates 'donor_response'.
8. GET /api/v1/requests/{request_id}/response correctly returns HTTP 405 Method Not Allowed.
9. GET /api/v1/hospitals/donations strictly denies donors (HTTP 403) while allowing authorized hospitals (HTTP 200).
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


class EmergencyResponseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_bloodbank.db")
        original_db = os.path.join(BACKEND_DIR, "bloodbank.db")
        shutil.copyfile(original_db, cls.test_db)

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        cls.orig_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db

        cls.conn = database.get_db_connection()

        # Seed test donor user and profile
        c1 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776655', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Emergency Donor", "emergency_donor@haemopulse.invalid")
        )
        cls.donor_user_id = c1.lastrowid
        c_d1 = cls.conn.execute(
            "INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available, total_donations) VALUES (?, ?, ?, 'A+', 28, 'Male', 'Koppa', ?, 1, 0)",
            (f"DNR-EMERGENCY-{cls.donor_user_id}", "Emergency Donor", "emergency_donor@haemopulse.invalid", cls.donor_user_id)
        )
        cls.donor_pk = c_d1.lastrowid
        cls.donor_token = server.create_access_token({"sub": "emergency_donor@haemopulse.invalid", "id": cls.donor_user_id, "role": "ROLE_DONOR"})

        # Seed hospital user
        ch = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+918877665544', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("Koppa Govt Hospital", "koppa_hospital@haemopulse.invalid")
        )
        cls.hospital_user_id = ch.lastrowid
        cls.hospital_token = server.create_access_token({"sub": "koppa_hospital@haemopulse.invalid", "id": cls.hospital_user_id, "role": "ROLE_HOSPITAL"})

        # Seed emergency blood request
        cr = cls.conn.execute(
            """INSERT INTO blood_requests
               (hospital_name, blood_group, units_needed, urgency_level, patient_name, request_date, hospital_address, contact_phone, created_by_user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
            ("Koppa Government Hospital", "A+", 1, "EMERGENCY", "Patient A", "2026-10-25 10:00:00", "Main Road, Koppa", "+919988000000", cls.hospital_user_id)
        )
        cls.request_id = cr.lastrowid
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

    def test_01_accept_canonical_action(self):
        """Action 'ACCEPTED' is accepted and stored in DB."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("response"), "ACCEPTED")

        row = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request_id, str(self.donor_pk))
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "ACCEPTED")

    def test_02_accept_normalized_from_accept(self):
        """Action 'ACCEPT' is normalized to 'ACCEPTED' and updates DB."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "ACCEPT"}, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("response"), "ACCEPTED")

        row = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request_id, str(self.donor_pk))
        ).fetchone()
        self.assertEqual(row[0], "ACCEPTED")

    def test_03_reject_normalized_from_reject(self):
        """Action 'REJECT' is normalized to 'REJECTED' and updates DB."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "REJECT"}, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("response"), "REJECTED")

        row = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request_id, str(self.donor_pk))
        ).fetchone()
        self.assertEqual(row[0], "REJECTED")

    def test_04_reject_canonical_action(self):
        """Action 'REJECTED' is accepted and stored in DB."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "REJECTED"}, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("response"), "REJECTED")

    def test_05_invalid_action_rejected(self):
        """Non-conforming actions return HTTP 400."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "MAYBE"}, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("action must be ACCEPTED or REJECTED", res.json().get("detail", ""))

        res_empty = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": ""}, headers=headers)
        self.assertEqual(res_empty.status_code, 400)

    def test_06_non_donor_forbidden(self):
        """Hospital users cannot respond to blood requests as donors."""
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res = client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Donor access only", res.json().get("detail", ""))

    def test_07_nonexistent_request_not_found(self):
        """Non-existent request id returns HTTP 404."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.post("/api/v1/requests/999999/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_08_donor_requests_list_includes_response(self):
        """GET /api/v1/requests includes donor_response for the responding donor."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        # First ensure donor has ACCEPTED
        client.post(f"/api/v1/requests/{self.request_id}/response", json={"action": "ACCEPTED"}, headers=headers)

        res = client.get("/api/v1/requests", headers=headers)
        self.assertEqual(res.status_code, 200)
        requests = res.json()
        req_item = next((r for r in requests if r["id"] == self.request_id), None)
        self.assertIsNotNone(req_item)
        self.assertEqual(req_item.get("donor_response"), "ACCEPTED")

    def test_09_get_request_response_returns_405_method_not_allowed(self):
        """GET /api/v1/requests/{request_id}/response is not allowed and returns HTTP 405."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = client.get(f"/api/v1/requests/{self.request_id}/response", headers=headers)
        self.assertEqual(res.status_code, 405)
        self.assertIn("method not allowed", res.text.lower())

    def test_10_hospital_donations_role_restrictions(self):
        """Donors cannot access hospital donations (403), while authorized hospitals succeed (200)."""
        # 1. Donor attempting to read hospital donations receives 403 Forbidden
        donor_res = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.donor_token}"})
        self.assertEqual(donor_res.status_code, 403)
        self.assertIn("Hospital access only", donor_res.json().get("detail", ""))

        # 2. Authorized hospital receives 200 OK
        hosp_res = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.hospital_token}"})
        self.assertEqual(hosp_res.status_code, 200)
        self.assertIsInstance(hosp_res.json(), list)


if __name__ == "__main__":
    unittest.main()
