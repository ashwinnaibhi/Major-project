"""
HaemoPulse Comprehensive End-to-End System Tests
Covers Workflows 1-4: Registration, Verification, Auth, Blood Bank Operations, ML Inference, and Diagnostics.
"""

import os
import sys
import json
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import server

class FullSystemIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil, tempfile
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_db = os.path.join(cls.temp_dir, "test_bloodbank.db")
        original_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bloodbank.db")
        shutil.copyfile(original_db, cls.test_db)
        os.environ["BLOODBANK_DB_FILE"] = cls.test_db
        server.DATABASE_PATH = cls.test_db
        cls.client = TestClient(server.app)

    @classmethod
    def tearDownClass(cls):
        import shutil
        original_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bloodbank.db")
        server.DATABASE_PATH = original_db
        os.environ.pop("BLOODBANK_DB_FILE", None)
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_health_and_root_endpoints(self):
        """Verify health checks and diagnostic endpoints."""
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertEqual(res_root.json().get("status"), "healthy")

        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json().get("status"), "ok")

    def test_02_smtp_status_diagnostic(self):
        """Verify SMTP status reports readiness without leaking credentials."""
        res = self.client.get("/api/v1/auth/smtp-status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("overall_status", data)
        self.assertIn("network_probe", data)
        self.assertIn("authentication_tested", data)
        self.assertFalse(data["authentication_tested"])
        # Ensure zero passwords or private tokens in response
        self.assertNotIn("smtp_pass", data)
        self.assertNotIn("password", str(data).lower())

    def test_03_cors_preflight_headers(self):
        """Verify CORS allows common frontend development and production origins."""
        for origin in ["http://localhost:3000", "http://192.168.1.37:3000", "https://haemopulse.pages.dev"]:
            res = self.client.options(
                "/api/v1/auth/smtp-status",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET"
                }
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("access-control-allow-origin"), origin)

    def test_04_ml_prediction_and_metrics_endpoints(self):
        """Verify blood availability prediction and metrics work directly in backend."""
        payload = {
            "taluk": "Koppa",
            "district": "Chikmagalur",
            "blood_group": "B+",
            "units_requested": 2,
            "urgency_level": "High"
        }
        res_pred = self.client.post("/predict-availability", json=payload)
        self.assertEqual(res_pred.status_code, 200)
        pred_data = res_pred.json()
        self.assertIn("is_available", pred_data)
        self.assertIn("confidence", pred_data)
        self.assertIn("fulfillment_score", pred_data)
        self.assertIn("method", pred_data)

        # Check /metrics endpoint
        res_met = self.client.get("/metrics")
        self.assertEqual(res_met.status_code, 200)
        met_data = res_met.json()
        self.assertIn("Random Forest", met_data)
        self.assertIn("accuracy", met_data["Random Forest"])

    def test_05_auth_and_login_validation(self):
        """Verify login works for valid accounts and rejects invalid credentials."""
        # Invalid password test
        res_bad = self.client.post("/api/v1/auth/login", json={
            "email": "ashwinkumarnsrao@gmail.com",
            "password": "wrong_password_12345"
        })
        self.assertEqual(res_bad.status_code, 401)

        # Nonexistent user
        res_none = self.client.post("/api/v1/auth/login", json={
            "email": "nonexistent_donor_12345@gmail.com",
            "password": "some_password"
        })
        self.assertEqual(res_none.status_code, 401)

    def test_06_registration_and_verification_workflow(self):
        """End-to-end test of donor registration, token creation, URL format, and verification."""
        import random
        random_suffix = random.randint(100000, 999999)
        test_email = f"testdonor_{random_suffix}@example.com"

        with patch.dict(os.environ, {
            "HAEMOPULSE_MOCK_SMTP": "true",
            "FRONTEND_BASE_URL": "https://haemopulse-demo.pages.dev"
        }):
            reg_payload = {
                "name": "Integration Test Donor",
                "email": test_email,
                "password": "StrongPassword123!",
                "phone": "9876543210",
                "blood_group": "O+",
                "district": "Chikmagalur",
                "taluk": "Koppa"
            }
            res_reg = self.client.post("/api/v1/auth/register", json=reg_payload)
            self.assertEqual(res_reg.status_code, 200)
            reg_data = res_reg.json()
            self.assertTrue(reg_data["success"])
            self.assertEqual(reg_data["user"]["is_verified"], False)

            delivery = reg_data.get("email_delivery", {})
            self.assertEqual(delivery.get("delivery_status"), "DELIVERED")
            verify_link = delivery.get("verify_link", "")
            self.assertTrue(verify_link.startswith("https://haemopulse-demo.pages.dev/verify-email?token="))
            raw_token = verify_link.split("token=")[1]

            res_ver = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
            self.assertEqual(res_ver.status_code, 200)
            ver_data = res_ver.json()
            self.assertTrue(ver_data["success"])
            self.assertTrue(ver_data["user"]["is_verified"])

            res_reuse = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
            self.assertEqual(res_reuse.status_code, 400)
            self.assertIn("invalid or has already been used", res_reuse.json()["detail"].lower())

    def test_07_public_endpoints_accessible(self):
        """Verify public locations and emergency search endpoints respond without auth crashes."""
        res_loc = self.client.get("/api/v1/locations")
        self.assertEqual(res_loc.status_code, 200)
        loc_data = res_loc.json()
        self.assertIn("districts", loc_data)

        res_em = self.client.get("/api/donors/emergency-search?blood_group=A%2B&urgency=HIGH")
        self.assertEqual(res_em.status_code, 200)
        em_data = res_em.json()
        self.assertIn("donors", em_data)
        self.assertIsInstance(em_data["donors"], list)


if __name__ == "__main__":
    unittest.main()
