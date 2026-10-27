"""
Test Role-Based Access Control (RBAC) for:
1. Hospital ML Availability Simulator (/predict-availability, /api/v1/predict-availability)
2. Emergency Donor Search & Alert (/api/donors/emergency-search, /api/donors/emergency-alert, and /v1 aliases)

Access Matrix:
- Authenticated Hospital: ALLOW (200)
- Authenticated Donor: DENY (403)
- Authenticated Admin: DENY (403)
- Unauthenticated Visitor: DENY (401)
"""

import os
import sys
import shutil
import tempfile
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import server
import database
from fastapi.testclient import TestClient


class HospitalMLEmergencyRBACTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_rbac.db")
        original_db = os.path.join(BACKEND_DIR, "bloodbank.db")
        if not os.path.exists(original_db):
            database.ensure_sqlite_db_ready(original_db)
        shutil.copyfile(original_db, cls.test_db)
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        server.DATABASE_PATH = cls.test_db
        cls.client = TestClient(server.app)

        # Tokens for each role
        cls.hospital_token = server.create_access_token({"sub": "3", "id": 3, "role": "ROLE_HOSPITAL"})
        cls.donor_token = server.create_access_token({"sub": "1", "id": 1, "role": "ROLE_DONOR"})
        cls.admin_token = server.create_access_token({"sub": "256", "id": 256, "role": "ROLE_ADMIN"})

    @classmethod
    def tearDownClass(cls):
        server.DATABASE_PATH = os.path.join(BACKEND_DIR, "bloodbank.db")
        os.environ.pop("BLOODBANK_DB_FILE", None)
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Hospital ML Availability Simulator
    # ─────────────────────────────────────────────────────────────────────────

    def test_predict_availability_unauthenticated_denied(self):
        """Unauthenticated requests to ML Availability Simulator must return 401."""
        payload = {
            "taluk": "Koppa",
            "district": "Chikkamagaluru",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        }
        res1 = self.client.post("/predict-availability", json=payload)
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.post("/api/v1/predict-availability", json=payload)
        self.assertEqual(res2.status_code, 401)

    def test_predict_availability_donor_denied(self):
        """Authenticated Donor requests to ML Availability Simulator must return 403."""
        payload = {
            "taluk": "Koppa",
            "district": "Chikkamagaluru",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        }
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res1 = self.client.post("/predict-availability", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.post("/api/v1/predict-availability", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_predict_availability_admin_denied(self):
        """Authenticated Administrator requests to ML Availability Simulator must return 403."""
        payload = {
            "taluk": "Koppa",
            "district": "Chikkamagaluru",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res1 = self.client.post("/predict-availability", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.post("/api/v1/predict-availability", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_predict_availability_hospital_allowed(self):
        """Authenticated Hospital requests to ML Availability Simulator must return 200."""
        payload = {
            "taluk": "Koppa",
            "district": "Chikkamagaluru",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        }
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res1 = self.client.post("/predict-availability", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn("is_available", data1)
        self.assertIn("confidence", data1)

        res2 = self.client.post("/api/v1/predict-availability", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIn("is_available", data2)
        self.assertIn("confidence", data2)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Emergency Donor Search
    # ─────────────────────────────────────────────────────────────────────────

    def test_emergency_search_unauthenticated_denied(self):
        """Unauthenticated requests to Emergency Donor Search must return 401."""
        res1 = self.client.get("/api/donors/emergency-search?blood_group=A%2B")
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.get("/api/v1/donors/emergency-search?blood_group=A%2B")
        self.assertEqual(res2.status_code, 401)

    def test_emergency_search_donor_denied(self):
        """Authenticated Donor requests to Emergency Donor Search must return 403."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res1 = self.client.get("/api/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.get("/api/v1/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_emergency_search_admin_denied(self):
        """Authenticated Admin requests to Emergency Donor Search must return 403."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res1 = self.client.get("/api/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.get("/api/v1/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_emergency_search_hospital_allowed(self):
        """Authenticated Hospital requests to Emergency Donor Search must return 200."""
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res1 = self.client.get("/api/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn("donors", data1)
        self.assertIn("compatible_groups", data1)

        res2 = self.client.get("/api/v1/donors/emergency-search?blood_group=A%2B", headers=headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIn("donors", data2)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Emergency Donor Alert
    # ─────────────────────────────────────────────────────────────────────────

    def test_emergency_alert_unauthenticated_denied(self):
        """Unauthenticated requests to Emergency Donor Alert must return 401."""
        payload = {
            "blood_group": "A+",
            "urgency": "Critical",
            "units_needed": 2,
            "donor_ids": [1]
        }
        res1 = self.client.post("/api/donors/emergency-alert", json=payload)
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.post("/api/v1/donors/emergency-alert", json=payload)
        self.assertEqual(res2.status_code, 401)

    def test_emergency_alert_donor_denied(self):
        """Authenticated Donor requests to Emergency Donor Alert must return 403."""
        payload = {
            "blood_group": "A+",
            "urgency": "Critical",
            "units_needed": 2,
            "donor_ids": [1]
        }
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res1 = self.client.post("/api/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.post("/api/v1/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_emergency_alert_admin_denied(self):
        """Authenticated Admin requests to Emergency Donor Alert must return 403."""
        payload = {
            "blood_group": "A+",
            "urgency": "Critical",
            "units_needed": 2,
            "donor_ids": [1]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res1 = self.client.post("/api/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Hospital access required", res1.json().get("detail", ""))

        res2 = self.client.post("/api/v1/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Hospital access required", res2.json().get("detail", ""))

    def test_emergency_alert_hospital_allowed(self):
        """Authenticated Hospital requests to Emergency Donor Alert must succeed."""
        payload = {
            "blood_group": "A+",
            "urgency": "Critical",
            "units_needed": 2,
            "donor_ids": [1]
        }
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res1 = self.client.post("/api/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json().get("status"), "success")

        res2 = self.client.post("/api/v1/donors/emergency-alert", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json().get("status"), "success")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Non-breakage Verification for Donor, Hospital, and Admin
    # ─────────────────────────────────────────────────────────────────────────

    def test_donor_availability_score_still_works(self):
        """Donor personal availability score endpoint must remain accessible to donors."""
        headers = {"Authorization": f"Bearer {self.donor_token}"}
        res = self.client.get("/api/v1/donors/me/availability-score", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("availability_score", res.json())

    def test_admin_inventory_still_works(self):
        """Admin inventory endpoint must remain accessible to administrators."""
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.get("/api/v1/inventory", headers=headers)
        self.assertEqual(res.status_code, 200)

    def test_hospital_requisitions_still_works(self):
        """Hospital requisition endpoints must remain accessible to hospitals."""
        headers = {"Authorization": f"Bearer {self.hospital_token}"}
        res = self.client.get("/api/v1/requests", headers=headers)
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
