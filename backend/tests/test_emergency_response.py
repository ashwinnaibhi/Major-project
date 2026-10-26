"""
HaemoPulse Comprehensive Emergency Blood Request Response & Persistence Test Suite
Verifies:
1. Donor accepts emergency request -> persisted in DB (HTTP 200).
2. Action normalization ('ACCEPT' -> 'ACCEPTED', 'REJECT' -> 'REJECTED').
3. Donor updates response -> updates cleanly via ON CONFLICT without duplicate rows.
4. Multiple donors responding to the same request -> kept completely separate and isolated.
5. Donor cannot modify another donor's response.
6. Unauthenticated requests are rejected with HTTP 401.
7. Non-donors (hospitals, admins) are rejected with HTTP 403.
8. Invalid actions (e.g. 'MAYBE') are rejected with HTTP 400.
9. Nonexistent requests return HTTP 404.
10. GET /api/v1/requests returns each donor's own response, never another donor's response.
11. Persistence across new DB connections / backend restarts.
12. GET /api/v1/donors/me/emergency-responses returns the authenticated donor's response history.
13. Hospital/unauthorized users cannot access donor emergency response history.
14. GET /api/v1/requests/{id}/response correctly returns HTTP 405 Method Not Allowed.
15. GET /api/v1/hospitals/donations strictly enforces hospital RBAC (403 for donors, 200 for hospitals).
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
        if not os.path.exists(original_db):
            database.ensure_sqlite_db_ready(original_db)
        shutil.copyfile(original_db, cls.test_db)

        cls.orig_env_db = os.environ.get("BLOODBANK_DB_FILE")
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        cls.orig_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = cls.test_db
        server.DATABASE_PATH = cls.test_db

        cls.conn = database.get_db_connection()

        # Seed test donor 1
        c1 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776655', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor One", "donor1_emergency@haemopulse.invalid")
        )
        cls.donor1_user_id = c1.lastrowid
        c_d1 = cls.conn.execute(
            "INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available, total_donations) VALUES (?, ?, ?, 'A+', 28, 'Male', 'Koppa', ?, 1, 0)",
            (f"DNR-TEST-1-{cls.donor1_user_id}", "Donor One", "donor1_emergency@haemopulse.invalid", cls.donor1_user_id)
        )
        cls.donor1_pk = c_d1.lastrowid
        cls.donor1_token = server.create_access_token({"sub": "donor1_emergency@haemopulse.invalid", "id": cls.donor1_user_id, "role": "ROLE_DONOR"})

        # Seed test donor 2 (same blood group A+)
        c2 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776656', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Two", "donor2_emergency@haemopulse.invalid")
        )
        cls.donor2_user_id = c2.lastrowid
        c_d2 = cls.conn.execute(
            "INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available, total_donations) VALUES (?, ?, ?, 'A+', 32, 'Female', 'Koppa', ?, 1, 0)",
            (f"DNR-TEST-2-{cls.donor2_user_id}", "Donor Two", "donor2_emergency@haemopulse.invalid", cls.donor2_user_id)
        )
        cls.donor2_pk = c_d2.lastrowid
        cls.donor2_token = server.create_access_token({"sub": "donor2_emergency@haemopulse.invalid", "id": cls.donor2_user_id, "role": "ROLE_DONOR"})

        # Seed hospital user
        ch = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+918877665544', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("Koppa Govt Hospital", "koppa_hospital@haemopulse.invalid")
        )
        cls.hospital_user_id = ch.lastrowid
        cls.hospital_token = server.create_access_token({"sub": "koppa_hospital@haemopulse.invalid", "id": cls.hospital_user_id, "role": "ROLE_HOSPITAL"})

        # Seed admin user
        ca = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919900112233', 'ROLE_ADMIN', 'ACTIVE', 1)",
            ("System Admin", "admin_emergency@haemopulse.invalid")
        )
        cls.admin_user_id = ca.lastrowid
        cls.admin_token = server.create_access_token({"sub": "admin_emergency@haemopulse.invalid", "id": cls.admin_user_id, "role": "ROLE_ADMIN"})

        # Seed emergency blood request 1
        cr1 = cls.conn.execute(
            """INSERT INTO blood_requests
               (hospital_name, blood_group, units_needed, urgency_level, patient_name, request_date, hospital_address, contact_phone, created_by_user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
            ("Koppa Government Hospital", "A+", 2, "EMERGENCY", "Patient Alpha", "2026-10-25 10:00:00", "Main Road, Koppa", "+919988000000", cls.hospital_user_id)
        )
        cls.request1_id = cr1.lastrowid

        # Seed emergency blood request 2
        cr2 = cls.conn.execute(
            """INSERT INTO blood_requests
               (hospital_name, blood_group, units_needed, urgency_level, patient_name, request_date, hospital_address, contact_phone, created_by_user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
            ("City Trauma Center", "A+", 1, "EMERGENCY", "Patient Beta", "2026-10-25 11:00:00", "Hospital Road, Koppa", "+919988000001", cls.hospital_user_id)
        )
        cls.request2_id = cr2.lastrowid
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

    def setUp(self):
        os.environ["BLOODBANK_DB_FILE"] = self.test_db
        database.DATABASE_PATH = self.test_db
        server.DATABASE_PATH = self.test_db

    def test_01_donor1_accepts_and_persists_in_database(self):
        """Donor 1 accepts request 1; verified written to database table emergency_request_responses."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json().get("success"))
        self.assertEqual(res.json().get("response"), "ACCEPTED")

        row = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request1_id, str(self.donor1_pk))
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "ACCEPTED")

    def test_02_action_normalization_from_accept_string(self):
        """Passing 'ACCEPT' normalizes to 'ACCEPTED' in database."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        res = client.post(f"/api/v1/requests/{self.request2_id}/response", json={"action": "ACCEPT"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("response"), "ACCEPTED")

        row = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request2_id, str(self.donor1_pk))
        ).fetchone()
        self.assertEqual(row[0], "ACCEPTED")

    def test_03_donor1_updates_response_to_rejected_without_duplicates(self):
        """Donor 1 changes response from ACCEPTED to REJECTED via ON CONFLICT without duplicate rows."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "REJECT"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("response"), "REJECTED")

        rows = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request1_id, str(self.donor1_pk))
        ).fetchall()
        self.assertEqual(len(rows), 1, "There should be exactly one row per donor and request")
        self.assertEqual(rows[0][0], "REJECTED")

    def test_04_donor2_accepts_same_request_keeps_responses_isolated(self):
        """Donor 2 accepts request 1; Donor 1's response remains REJECTED and Donor 2's is ACCEPTED."""
        headers = {"Authorization": f"Bearer {self.donor2_token}"}
        res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 200)

        # Check Donor 1 row
        row_d1 = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request1_id, str(self.donor1_pk))
        ).fetchone()
        self.assertEqual(row_d1[0], "REJECTED", "Donor 1's response must not be overwritten by Donor 2")

        # Check Donor 2 row
        row_d2 = self.conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (self.request1_id, str(self.donor2_pk))
        ).fetchone()
        self.assertEqual(row_d2[0], "ACCEPTED", "Donor 2's response must be ACCEPTED")

        # Total rows for request 1
        count = self.conn.execute(
            "SELECT COUNT(*) FROM emergency_request_responses WHERE request_id = ?",
            (self.request1_id,)
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_05_unauthenticated_request_rejected(self):
        """Unauthenticated user cannot respond to requests (HTTP 401)."""
        res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "ACCEPTED"})
        self.assertEqual(res.status_code, 401)

    def test_06_non_donor_forbidden(self):
        """Hospital user cannot submit donor responses (HTTP 403)."""
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Donor access only", res.json().get("detail", ""))

    def test_07_invalid_action_rejected(self):
        """Actions other than ACCEPT/ACCEPTED or REJECT/REJECTED return HTTP 400."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        for bad_action in ["MAYBE", "HOLD", "TBD", "", "   ", "UNKNOWN"]:
            res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": bad_action}, headers=headers)
            self.assertEqual(res.status_code, 400, f"Expected 400 for action '{bad_action}'")
            self.assertIn("action must be ACCEPTED or REJECTED", res.json().get("detail", ""))

    def test_08_nonexistent_request_returns_404(self):
        """Nonexistent request ID returns HTTP 404."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        res = client.post("/api/v1/requests/999999/response", json={"action": "ACCEPTED"}, headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_09_get_requests_returns_each_donors_own_response(self):
        """GET /api/v1/requests returns donor_response specific to the querying donor."""
        # Query as Donor 1
        res1 = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(res1.status_code, 200)
        req1_d1 = next(r for r in res1.json() if r["id"] == self.request1_id)
        self.assertEqual(req1_d1.get("donor_response"), "REJECTED")

        # Query as Donor 2
        res2 = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {self.donor2_token}"})
        self.assertEqual(res2.status_code, 200)
        req1_d2 = next(r for r in res2.json() if r["id"] == self.request1_id)
        self.assertEqual(req1_d2.get("donor_response"), "ACCEPTED")

    def test_10_database_reconnection_and_restart_preserves_data(self):
        """Responses remain persistent after opening a fresh database connection (simulating restart)."""
        fresh_conn = database.get_db_connection()
        try:
            row1 = fresh_conn.execute(
                "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
                (self.request1_id, str(self.donor1_pk))
            ).fetchone()
            self.assertEqual(row1[0], "REJECTED")

            row2 = fresh_conn.execute(
                "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
                (self.request1_id, str(self.donor2_pk))
            ).fetchone()
            self.assertEqual(row2[0], "ACCEPTED")
        finally:
            fresh_conn.close()

    def test_11_donor_me_emergency_responses_history_endpoint(self):
        """GET /api/v1/donors/me/emergency-responses returns all responses for authenticated donor."""
        # Donor 1 has responded to request 1 and request 2
        res1 = client.get("/api/v1/donors/me/emergency-responses", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(res1.status_code, 200)
        history1 = res1.json()
        self.assertIsInstance(history1, list)
        self.assertGreaterEqual(len(history1), 2)
        req_ids1 = [h["request_id"] for h in history1]
        self.assertIn(self.request1_id, req_ids1)
        self.assertIn(self.request2_id, req_ids1)

        # Donor 2 has only responded to request 1
        res2 = client.get("/api/v1/donors/me/emergency-responses", headers={"Authorization": f"Bearer {self.donor2_token}"})
        self.assertEqual(res2.status_code, 200)
        history2 = res2.json()
        req_ids2 = [h["request_id"] for h in history2]
        self.assertIn(self.request1_id, req_ids2)
        self.assertNotIn(self.request2_id, req_ids2)

        # Hospital cannot access donor emergency responses history
        res_hosp = client.get("/api/v1/donors/me/emergency-responses", headers={"Authorization": f"Bearer {self.hospital_token}"})
        self.assertEqual(res_hosp.status_code, 403)

    def test_12_get_request_response_returns_405_method_not_allowed(self):
        """GET /api/v1/requests/{request_id}/response is not allowed and returns HTTP 405."""
        headers = {"Authorization": f"Bearer {self.donor1_token}"}
        res = client.get(f"/api/v1/requests/{self.request1_id}/response", headers=headers)
        self.assertEqual(res.status_code, 405)
        self.assertIn("method not allowed", res.text.lower())

    def test_13_hospital_donations_role_restrictions(self):
        """Donors cannot access hospital donations (403), while authorized hospitals succeed (200)."""
        donor_res = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(donor_res.status_code, 403)
        self.assertIn("Hospital access only", donor_res.json().get("detail", ""))

        hosp_res = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.hospital_token}"})
        self.assertEqual(hosp_res.status_code, 200)
        self.assertIsInstance(hosp_res.json(), list)

    def test_14_admin_emergency_responses_authorization_and_data(self):
        """GET /api/v1/admin/emergency-responses is restricted to ROLE_ADMIN and blocked for others."""
        # 1. Admin succeeds (HTTP 200)
        admin_res = client.get("/api/v1/admin/emergency-responses", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(admin_res.status_code, 200)
        responses = admin_res.json()
        self.assertIsInstance(responses, list)
        self.assertGreaterEqual(len(responses), 1)

        # 2. Donor is rejected (HTTP 403)
        donor_res = client.get("/api/v1/admin/emergency-responses", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(donor_res.status_code, 403)
        self.assertIn("Administrator access required", donor_res.json().get("detail", ""))

        # 3. Hospital is rejected (HTTP 403)
        hosp_res = client.get("/api/v1/admin/emergency-responses", headers={"Authorization": f"Bearer {self.hospital_token}"})
        self.assertEqual(hosp_res.status_code, 403)
        self.assertIn("Administrator access required", hosp_res.json().get("detail", ""))

        # 4. Unauthenticated is rejected (HTTP 401)
        anon_res = client.get("/api/v1/admin/emergency-responses")
        self.assertEqual(anon_res.status_code, 401)

    def test_15_respond_to_request_rollback_on_database_error(self):
        """Database execution failure during response triggers conn.rollback() and returns HTTP 500."""
        class FailingConn:
            def __init__(self, real_conn):
                self._real = real_conn
                self.rollback_called = False

            def execute(self, query, params=None):
                if "INSERT INTO emergency_request_responses" in query:
                    raise Exception("Simulated disk I/O or constraint failure")
                return self._real.execute(query, params) if params is not None else self._real.execute(query)

            def rollback(self):
                self.rollback_called = True
                self._real.rollback()

            def commit(self):
                self._real.commit()

        failing_conn = FailingConn(self.conn)
        server.app.dependency_overrides[database.get_db] = lambda: failing_conn
        try:
            headers = {"Authorization": f"Bearer {self.donor1_token}"}
            res = client.post(f"/api/v1/requests/{self.request1_id}/response", json={"action": "ACCEPTED"}, headers=headers)
            self.assertEqual(res.status_code, 500)
            self.assertIn("Database failed to record emergency response", res.json().get("detail", ""))
            self.assertTrue(failing_conn.rollback_called, "conn.rollback() must be called on DB failure")
        finally:
            server.app.dependency_overrides.pop(database.get_db, None)

    def test_16_postgresql_schema_and_query_parity(self):
        """Verify PostgreSQL schema definition and query conversion for emergency responses."""
        import re

        # 1. Verify DDL contains emergency_request_responses table with exact constraints
        ddl = database.POSTGRES_SCHEMA_DDL
        self.assertIn("CREATE TABLE IF NOT EXISTS emergency_request_responses", ddl)
        self.assertIn("REFERENCES blood_requests(id) ON DELETE CASCADE", ddl)
        self.assertIn("CHECK(response IN ('ACCEPTED', 'REJECTED'))", ddl)
        self.assertIn("UNIQUE(request_id, donor_id)", ddl)

        # 2. Verify INSERT ON CONFLICT query conversion to Postgres
        q_insert = """INSERT INTO emergency_request_responses
                 (request_id, donor_id, response, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(request_id, donor_id) DO UPDATE SET
                 response = excluded.response,
                 created_at = excluded.created_at"""
        converted_insert, is_insert = database._convert_query_to_postgres(q_insert)
        self.assertTrue(is_insert)
        self.assertIn("%s, %s, %s, %s", converted_insert)
        self.assertNotIn("?", converted_insert)
        self.assertTrue(converted_insert.endswith("RETURNING id"))
        self.assertIn("ON CONFLICT(request_id, donor_id) DO UPDATE SET", converted_insert)

        # 3. Verify list_requests query conversion
        q_list = """SELECT r.*, err.response AS donor_response
                    FROM blood_requests r
                    LEFT JOIN emergency_request_responses err
                      ON err.request_id = r.id AND (err.donor_id = ? OR err.donor_id = ?)
                    WHERE r.blood_group IN (?, ?) AND r.status = 'PENDING'
                    ORDER BY r.request_date DESC"""
        converted_list, _ = database._convert_query_to_postgres(q_list)
        self.assertIn("err.donor_id = %s OR err.donor_id = %s", converted_list)
        self.assertNotIn("?", converted_list)

        # 4. Verify donor history query conversion
        q_history = """SELECT err.id AS response_id, err.request_id, err.response, err.created_at AS responded_at
               FROM emergency_request_responses err
               JOIN blood_requests r ON r.id = err.request_id
               WHERE err.donor_id = ? OR err.donor_id = ?
               ORDER BY err.created_at DESC, err.id DESC"""
        converted_history, _ = database._convert_query_to_postgres(q_history)
        self.assertIn("err.donor_id = %s OR err.donor_id = %s", converted_history)
        self.assertNotIn("?", converted_history)

    def test_17_postgres_lifespan_startup_schema_initialization(self):
        """Verify application lifespan runs init_postgres_schema on startup in Postgres mode."""
        from unittest.mock import patch, MagicMock
        import asyncio

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn._conn.cursor.return_value = mock_cursor

        with patch("server.is_postgres", return_value=True):
            with patch("server.get_db_connection", return_value=mock_conn):
                async def run_startup():
                    async with server.lifespan(server.app):
                        pass

                asyncio.run(run_startup())

                # Verified executed all DDL statements and committed
                self.assertGreater(mock_cursor.execute.call_count, 10)
                self.assertTrue(mock_conn.commit.called)
                mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
