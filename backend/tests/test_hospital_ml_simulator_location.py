"""
Test suite for Hospital ML Availability Simulator location resolution & server-side enforcement.
Validates:
1. Koppa hospital receives stored taluk (Koppa) and district (Chikkamagaluru).
2. Sringeri hospital receives stored taluk (Sringeri) and district (Chikkamagaluru).
3. Athani hospital receives stored taluk (Athani) and district (Belagavi).
4. Switching hospital accounts updates profile and prediction location dynamically.
5. No universal Koppa/Chikkamagaluru fallback used for non-Koppa hospitals.
6. Unauthenticated requests are rejected with HTTP 401.
7. Donor requests are rejected with HTTP 403.
8. Hospitals cannot override or tamper with location parameters (rejected with HTTP 403).
9. Missing or incomplete hospital profiles return clear errors rather than fabricated locations.
10. Prediction verdict and metrics response contract is preserved.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database
import server
from fastapi.testclient import TestClient


class TestHospitalMLSimulatorLocation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_ml_loc.db")
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
    # 1. Location Resolution by Authenticated Identity
    # ─────────────────────────────────────────────────────────────────────────

    def test_01_koppa_hospital_receives_stored_location(self):
        """User ID 3 (Koppa) receives its own stored taluk Koppa and district Chikkamagaluru."""
        token = server.create_access_token({"sub": "koppa_ghpc@haemopulse.in", "id": 3, "role": "ROLE_HOSPITAL"})
        headers = {"Authorization": f"Bearer {token}"}

        # Check hospital profile endpoint
        prof_res = self.client.get("/api/v1/hospitals/me/profile", headers=headers)
        self.assertEqual(prof_res.status_code, 200, prof_res.text)
        hp = prof_res.json()["hospital_profile"]
        self.assertEqual(hp["taluk"], "Koppa")
        self.assertEqual(hp["district"], "Chikkamagaluru")

        # Check simulator prediction endpoint
        pred_res = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        })
        self.assertEqual(pred_res.status_code, 200, pred_res.text)
        data = pred_res.json()
        self.assertEqual(data["taluk"], "Koppa")
        self.assertEqual(data["district"], "Chikkamagaluru")
        self.assertIn("is_available", data)
        self.assertIn("confidence", data)

    def test_02_sringeri_hospital_receives_stored_location(self):
        """User ID 17 (Sringeri) receives its own stored taluk Sringeri and district Chikkamagaluru."""
        token = server.create_access_token({"sub": "sringeri_ghpc@haemopulse.in", "id": 17, "role": "ROLE_HOSPITAL"})
        headers = {"Authorization": f"Bearer {token}"}

        prof_res = self.client.get("/api/v1/hospitals/me/profile", headers=headers)
        self.assertEqual(prof_res.status_code, 200, prof_res.text)
        hp = prof_res.json()["hospital_profile"]
        self.assertEqual(hp["taluk"], "Sringeri")
        self.assertEqual(hp["district"], "Chikkamagaluru")

        pred_res = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "blood_group": "O+",
            "units_requested": 3,
            "urgency_level": "Medium"
        })
        self.assertEqual(pred_res.status_code, 200, pred_res.text)
        data = pred_res.json()
        self.assertEqual(data["taluk"], "Sringeri")
        self.assertEqual(data["district"], "Chikkamagaluru")
        self.assertNotEqual(data["taluk"], "Koppa")

    def test_03_athani_hospital_receives_stored_location(self):
        """User ID 41 (Athani, Belagavi) receives its own stored taluk Athani and district Belagavi."""
        token = server.create_access_token({"sub": "athani_ghpc@haemopulse.in", "id": 41, "role": "ROLE_HOSPITAL"})
        headers = {"Authorization": f"Bearer {token}"}

        prof_res = self.client.get("/api/v1/hospitals/me/profile", headers=headers)
        self.assertEqual(prof_res.status_code, 200, prof_res.text)
        hp = prof_res.json()["hospital_profile"]
        self.assertEqual(hp["taluk"], "Athani")
        self.assertEqual(hp["district"], "Belagavi")

        pred_res = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "blood_group": "A+",
            "units_requested": 1,
            "urgency_level": "Low"
        })
        self.assertEqual(pred_res.status_code, 200, pred_res.text)
        data = pred_res.json()
        self.assertEqual(data["taluk"], "Athani")
        self.assertEqual(data["district"], "Belagavi")
        self.assertNotEqual(data["taluk"], "Koppa")
        self.assertNotEqual(data["district"], "Chikkamagaluru")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Dynamic Update Across Different Logged-In Sessions
    # ─────────────────────────────────────────────────────────────────────────

    def test_04_switching_hospital_updates_simulator_location(self):
        """Switching from Sringeri to Athani dynamically changes simulator location."""
        # 1. Sringeri Session
        token_sringeri = server.create_access_token({"sub": "sringeri_ghpc@haemopulse.in", "id": 17, "role": "ROLE_HOSPITAL"})
        res_s = self.client.post("/api/v1/predict-availability", headers={"Authorization": f"Bearer {token_sringeri}"}, json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res_s.status_code, 200)
        self.assertEqual(res_s.json()["taluk"], "Sringeri")

        # 2. Athani Session
        token_athani = server.create_access_token({"sub": "athani_ghpc@haemopulse.in", "id": 41, "role": "ROLE_HOSPITAL"})
        res_a = self.client.post("/api/v1/predict-availability", headers={"Authorization": f"Bearer {token_athani}"}, json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["taluk"], "Athani")
        self.assertEqual(res_a.json()["district"], "Belagavi")

    def test_05_no_universal_koppa_or_chikmagalur_fallback(self):
        """Athani hospital never falls back to Koppa or Chikkamagaluru."""
        token = server.create_access_token({"sub": "athani_ghpc@haemopulse.in", "id": 41, "role": "ROLE_HOSPITAL"})
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "blood_group": "AB+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res.status_code, 200)
        result = res.json()
        self.assertNotIn("Koppa", [result["taluk"], result["district"]])
        self.assertNotIn("Chikkamagaluru", [result["taluk"], result["district"]])
        self.assertNotIn("Chikmagalur", [result["taluk"], result["district"]])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Security, Authorization & Tampering Prevention
    # ─────────────────────────────────────────────────────────────────────────

    def test_06_unauthenticated_request_rejected(self):
        """Unauthenticated requests are rejected with HTTP 401."""
        res = self.client.post("/api/v1/predict-availability", json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res.status_code, 401)

    def test_07_donor_access_rejected(self):
        """Authenticated donor requests are rejected with HTTP 403."""
        token = server.create_access_token({"sub": "ashwinkumarnsrao@gmail.com", "id": 1, "role": "ROLE_DONOR"})
        res = self.client.post("/api/v1/predict-availability", headers={"Authorization": f"Bearer {token}"}, json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn("Hospital access required", res.json()["detail"])

    def test_08_hospital_cannot_override_stored_location(self):
        """Hospital cannot tamper with request parameters to simulate a different taluk or district."""
        # Sringeri hospital attempts to query Koppa taluk
        token_s = server.create_access_token({"sub": "sringeri_ghpc@haemopulse.in", "id": 17, "role": "ROLE_HOSPITAL"})
        headers = {"Authorization": f"Bearer {token_s}"}

        tamper_res_taluk = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "taluk": "Koppa",  # Mismatch with stored Sringeri
            "district": "Chikkamagaluru",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        })
        self.assertEqual(tamper_res_taluk.status_code, 403)
        self.assertIn("Location mismatch", tamper_res_taluk.json()["detail"])

        tamper_res_district = self.client.post("/api/v1/predict-availability", headers=headers, json={
            "taluk": "Sringeri",
            "district": "Belagavi",  # Mismatch with stored Chikkamagaluru
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        })
        self.assertEqual(tamper_res_district.status_code, 403)
        self.assertIn("Location mismatch", tamper_res_district.json()["detail"])

    def test_09_missing_or_incomplete_hospital_profile_returns_error(self):
        """Hospital user without a profile receives HTTP 404 rather than a fabricated fallback."""
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (name, email, password, phone, role, is_verified, status) VALUES ('Ghost Hospital', 'ghost@clinic.org', 'hash', '9999999999', 'ROLE_HOSPITAL', 1, 'ACTIVE')")
        ghost_id = cur.lastrowid
        conn.commit()
        conn.close()

        token_ghost = server.create_access_token({"sub": "ghost@clinic.org", "id": ghost_id, "role": "ROLE_HOSPITAL"})
        res = self.client.post("/api/v1/predict-availability", headers={"Authorization": f"Bearer {token_ghost}"}, json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res.status_code, 404)
        self.assertIn("Hospital profile not found", res.json()["detail"])

    def test_10_prediction_contract_and_metrics_preserved(self):
        """Simulation verdict contains all required fields and metrics endpoint operates normally."""
        token = server.create_access_token({"sub": "sringeri_ghpc@haemopulse.in", "id": 17, "role": "ROLE_HOSPITAL"})
        res = self.client.post("/api/v1/predict-availability", headers={"Authorization": f"Bearer {token}"}, json={
            "blood_group": "B+", "units_requested": 2, "urgency_level": "High"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_available", data)
        self.assertIsInstance(data["is_available"], bool)
        self.assertIn("confidence", data)
        self.assertIn("fulfillment_score", data)
        self.assertIn("method", data)
        self.assertIn("taluk", data)
        self.assertIn("district", data)

        metrics_res = self.client.get("/api/v1/metrics")
        self.assertEqual(metrics_res.status_code, 200)
        metrics = metrics_res.json()
        self.assertIn("Random Forest", metrics)


if __name__ == "__main__":
    unittest.main()
