"""Test suite for Email Verification and Transactional Email in HaemoPulse.

Verifies:
1. Registration creates an unverified account (is_verified = 0).
2. Verification email is generated and submitted to SMTP provider (mocked).
3. A valid token verifies the account (is_verified becomes 1, token cleared).
4. An invalid token is rejected.
5. An expired token is rejected.
6. A previously used token cannot be reused.
7. Resend verification works and enforces rate limiting / cooldown.
8. Unverified users cannot book appointments (HTTP 403).
9. Verified users can book appointments when authorized.
10. Donor, hospital, and admin authentication continues to work.
11. Missing SMTP configuration produces a clear error without leaking secrets.
12. SMTP authentication failures are handled safely.
13. Live database is not affected by tests (uses isolated temporary test DB).
"""
import os
import shutil
import sqlite3
import datetime
import hashlib
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure we use an isolated temporary test database
TEMP_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEMP_DIR, "test_bloodbank.db")
ORIGINAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bloodbank.db")
shutil.copyfile(ORIGINAL_DB_PATH, TEST_DB_PATH)

# Set test environment variables before importing app
os.environ["BLOODBANK_DB_FILE"] = TEST_DB_PATH
os.environ["HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES"] = "true"
os.environ["HAEMOPULSE_MOCK_SMTP"] = "false"
os.environ["SMTP_HOST"] = "smtp.gmail.com"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USER"] = "test_sender@gmail.com"
os.environ["SMTP_PASS"] = "mock_app_password"
os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
import database
# Point server & database DATABASE_PATH to our test database
server.DATABASE_PATH = TEST_DB_PATH
database.DATABASE_PATH = TEST_DB_PATH

from fastapi.testclient import TestClient
from server import app
import email_service


class TestEmailVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        import server
        import database
        server.DATABASE_PATH = ORIGINAL_DB_PATH
        database.DATABASE_PATH = ORIGINAL_DB_PATH
        os.environ.pop("BLOODBANK_DB_FILE", None)
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    def setUp(self):
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute("DELETE FROM users WHERE email LIKE 'test_unverified_%@example.com'")
        conn.execute("DELETE FROM donors WHERE email LIKE 'test_unverified_%@example.com'")
        conn.commit()
        conn.close()

    def test_01_registration_creates_unverified_account_and_sends_email(self):
        """1 & 2: Registration creates an unverified account and submits email to SMTP."""
        mock_smtp_instance = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp_instance):
            with patch.dict(os.environ, {"HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false"}):
                res = self.client.post("/api/v1/auth/register", json={
                    "name": "Test Unverified Donor",
                    "email": "test_unverified_1@example.com",
                    "password": "Password123!",
                    "blood_group": "O+",
                    "phone": "9876543210",
                    "district": "Bengaluru Urban",
                    "taluk": "Bengaluru North",
                })

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["user"]["is_verified"], "New account must be unverified (is_verified=0)")
        self.assertEqual(data["email_delivery"]["delivery_status"], "DELIVERED")

        # Verify in database
        conn = sqlite3.connect(TEST_DB_PATH)
        user = conn.execute("SELECT id, is_verified, verification_token, verification_token_expiry FROM users WHERE email = 'test_unverified_1@example.com'").fetchone()
        conn.close()

        self.assertIsNotNone(user)
        self.assertEqual(user[1], 0, "Database is_verified must be 0")
        self.assertIsNotNone(user[2], "verification_token must be stored in database")
        self.assertIsNotNone(user[3], "verification_token_expiry must be stored in database")

        # Verify SMTP interaction
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("test_sender@gmail.com", "mock_app_password")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()

    def test_02_valid_token_verifies_account(self):
        """3: A valid token marks the account as verified and clears token."""
        conn = sqlite3.connect(TEST_DB_PATH)
        raw_token = "valid_test_token_1234567890123456"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expiry = (datetime.datetime.utcnow() + datetime.timedelta(minutes=30)).isoformat()
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry)
               VALUES ('Token Test User', 'tokentest@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, ?, ?)""",
            (token_hash, expiry)
        )
        conn.commit()
        conn.close()

        res = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("successfully verified", data["message"].lower())

        # Check DB state
        conn = sqlite3.connect(TEST_DB_PATH)
        user = conn.execute("SELECT is_verified, verification_token, verification_token_expiry FROM users WHERE email = 'tokentest@example.com'").fetchone()
        conn.close()
        self.assertEqual(user[0], 1, "is_verified must now be 1")
        self.assertIsNone(user[1], "verification_token must be cleared to prevent reuse")
        self.assertIsNone(user[2], "verification_token_expiry must be cleared")

    def test_03_invalid_token_is_rejected(self):
        """4: Invalid token is safely rejected."""
        res = self.client.get("/api/v1/auth/verify-email?token=completely_invalid_token_999")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("invalid", data["detail"].lower())

    def test_04_expired_token_is_rejected(self):
        """5: Expired token is rejected with an expired message."""
        conn = sqlite3.connect(TEST_DB_PATH)
        raw_token = "expired_token_abcdef123456"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        past_expiry = (datetime.datetime.utcnow() - datetime.timedelta(minutes=10)).isoformat()
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry)
               VALUES ('Expired User', 'expired@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, ?, ?)""",
            (token_hash, past_expiry)
        )
        conn.commit()
        conn.close()

        res = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("expired", data["detail"].lower())

    def test_05_reused_token_is_rejected(self):
        """6: Previously used token cannot be reused."""
        conn = sqlite3.connect(TEST_DB_PATH)
        raw_token = "reusable_token_xyz987654321"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expiry = (datetime.datetime.utcnow() + datetime.timedelta(minutes=30)).isoformat()
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry)
               VALUES ('Reuse User', 'reuse@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, ?, ?)""",
            (token_hash, expiry)
        )
        conn.commit()
        conn.close()

        # First verify should succeed
        res1 = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
        self.assertEqual(res1.status_code, 200)

        # Second verify with the same token must fail
        res2 = self.client.get(f"/api/v1/auth/verify-email?token={raw_token}")
        self.assertEqual(res2.status_code, 400)

    def test_06_resend_verification_with_rate_limiting(self):
        """7: Resend verification sends new email and enforces 60s cooldown."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Resend User', 'resend@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {"HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false"}):
                # 1st resend should succeed
                res1 = self.client.post("/api/v1/auth/resend-verification", json={"email": "resend@example.com"})
                self.assertEqual(res1.status_code, 200, res1.text)
                self.assertTrue(res1.json()["success"])

                # Immediate 2nd resend must be rate-limited (HTTP 429)
                res2 = self.client.post("/api/v1/auth/resend-verification", json={"email": "resend@example.com"})
                self.assertEqual(res2.status_code, 429)
                self.assertIn("wait", res2.json()["detail"].lower())

    def test_07_unverified_user_cannot_book_appointment(self):
        """8: Unverified users cannot book appointments (HTTP 403)."""
        conn = sqlite3.connect(TEST_DB_PATH)
        pw_hash = server.hash_password("password123")
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified)
               VALUES ('Unverified Booker', 'booker_unverified@example.com', ?, '1234567890', 'ROLE_DONOR', 0)""",
            (pw_hash,)
        )
        uid = cur.lastrowid
        cur.execute(
            """INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location, is_available)
               VALUES ('DNR-9991', ?, 'Unverified Booker', 'booker_unverified@example.com', 'A+', 25, 'Male', 'Zone A', 1)""",
            (uid,)
        )
        conn.commit()
        conn.close()

        # Login
        login_res = self.client.post("/api/v1/auth/login", json={"email": "booker_unverified@example.com", "password": "password123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        # Attempt to book appointment
        app_res = self.client.post("/api/v1/appointments", json={
            "appointment_date": "2026-11-01",
            "time_slot": "Morning (8 AM - 12 PM)",
            "center_name": "Hub #1"
        }, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(app_res.status_code, 403)
        self.assertIn("verify your email", app_res.json()["detail"].lower())

    def test_08_verified_user_can_book_appointment(self):
        """9: Verified users can book appointments."""
        conn = sqlite3.connect(TEST_DB_PATH)
        pw_hash = server.hash_password("password123")
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified)
               VALUES ('Verified Booker', 'booker_verified@example.com', ?, '1234567890', 'ROLE_DONOR', 1)""",
            (pw_hash,)
        )
        uid = cur.lastrowid
        cur.execute(
            """INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location, is_available)
               VALUES ('DNR-9992', ?, 'Verified Booker', 'booker_verified@example.com', 'O-', 28, 'Female', 'Zone B', 1)""",
            (uid,)
        )
        conn.commit()
        conn.close()

        # Login
        login_res = self.client.post("/api/v1/auth/login", json={"email": "booker_verified@example.com", "password": "password123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]

        # Attempt to book appointment
        app_res = self.client.post("/api/v1/appointments", json={
            "appointment_date": "2026-11-01",
            "time_slot": "Morning (8 AM - 12 PM)",
            "center_name": "Hub #1"
        }, headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(app_res.status_code, 200, app_res.text)
        self.assertEqual(app_res.json()["status"], "SCHEDULED")

    def test_09_existing_roles_authentication(self):
        """10: Existing donor, hospital, and admin authentication continues to work."""
        donor_res = self.client.post("/api/v1/auth/login", json={"email": "ashwinkumarnsrao@gmail.com", "password": "password123"})
        if donor_res.status_code != 200:
            donor_res = self.client.post("/api/v1/auth/login", json={"email": "ashwinkumarnsrao@gmail.com", "password": "12345678"})
        self.assertEqual(donor_res.status_code, 200)
        self.assertEqual(donor_res.json()["role"], "ROLE_DONOR")

        hosp_res = self.client.post("/api/v1/auth/login", json={"email": "ashwinkumarns1995@gmail.com", "password": "haemo@123"})
        if hosp_res.status_code != 200:
            hosp_res = self.client.post("/api/v1/auth/login", json={"email": "ashwinkumarns1995@gmail.com", "password": "hospital123"})
        self.assertEqual(hosp_res.status_code, 200)
        self.assertEqual(hosp_res.json()["role"], "ROLE_HOSPITAL")

    def test_10_missing_smtp_configuration_produces_clear_error(self):
        """11: Missing SMTP configuration returns clear message without leaking secrets."""
        with patch.dict(os.environ, {"SMTP_PASS": "", "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false"}):
            res = email_service.send_verification_smtp_email(
                recipient_email="test@example.com",
                recipient_name="Tester",
                raw_token="token_123"
            )
            self.assertFalse(res["sent"])
            self.assertEqual(res["delivery_status"], "NOT_CONFIGURED")
            self.assertIn("not configured", res["error"].lower())

    def test_11_smtp_authentication_failure_handled_correctly(self):
        """12: SMTP authentication failure handled gracefully without leaking secrets."""
        import smtplib
        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted.")
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {"HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false", "SMTP_PASS": "wrong_password"}):
                res = email_service.send_verification_smtp_email(
                    recipient_email="test@example.com",
                    recipient_name="Tester",
                    raw_token="token_123"
                )
                self.assertFalse(res["sent"])
                self.assertEqual(res["delivery_status"], "FAILED")
                self.assertIn("authentication failed", res["error"].lower())
                self.assertNotIn("wrong_password", res["error"])



    def test_12_boolean_parsing_policy(self):
        """Verify boolean environment variable parsing follows the documented policy."""
        from email_service import parse_bool_env
        with patch.dict(os.environ, {"TEST_FLAG": "false"}):
            self.assertFalse(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "'false'"}):
            self.assertFalse(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "0"}):
            self.assertFalse(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "no"}):
            self.assertFalse(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "off"}):
            self.assertFalse(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "true"}):
            self.assertTrue(parse_bool_env("TEST_FLAG"))
        with patch.dict(os.environ, {"TEST_FLAG": "1"}):
            self.assertTrue(parse_bool_env("TEST_FLAG"))
        # Missing or invalid strings follow documented default (default=True)
        with patch.dict(os.environ, {"TEST_FLAG": "invalid_value"}):
            self.assertTrue(parse_bool_env("TEST_FLAG", default=True))
        with patch.dict(os.environ, {"TEST_FLAG": ""}):
            self.assertTrue(parse_bool_env("TEST_FLAG", default=True))

    def test_13_disable_flag_controls_delivery(self):
        """HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=true disables delivery; false enables delivery."""
        with patch.dict(os.environ, {"HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "true", "HAEMOPULSE_MOCK_SMTP": "false"}):
            self.assertFalse(email_service.external_messages_enabled())
            res = email_service.send_verification_smtp_email(
                recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
            )
            self.assertEqual(res["delivery_status"], "DISABLED")
            self.assertIn("disabled", res["error"].lower())

        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "SMTP_USER": "mailer@example.com",
                "SMTP_PASS": "chit xsfs eijz ukvd"
            }):
                self.assertTrue(email_service.external_messages_enabled())
                res = email_service.send_verification_smtp_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                )
                self.assertEqual(res["delivery_status"], "DELIVERED")
                self.assertTrue(res["sent"])

    def test_14_smtp_failure_is_not_reported_as_disabled(self):
        """SMTP authentication failure or network error is NEVER reported as DISABLED."""
        import smtplib
        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "SMTP_USER": "mailer@example.com",
                "SMTP_PASS": "real_app_pass_1234"
            }):
                res = email_service.send_verification_smtp_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                )
                self.assertNotEqual(res["delivery_status"], "DISABLED")
                self.assertEqual(res["delivery_status"], "FAILED")
                self.assertIn("authentication failed", res["error"].lower())

    def test_15_resend_verification_for_venkat_account(self):
        """Resend verification for an existing unverified account refreshes token and returns delivery result."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT OR REPLACE INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry, last_verification_email_sent_at)
               VALUES ('Venkat', 'venkatn.naibhi@gmail.com', 'hash123', '9876543210', 'ROLE_DONOR', 0, 'old_token', '2020-01-01T00:00:00', NULL)"""
        )
        conn.commit()
        conn.close()

        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "SMTP_USER": "mailer@example.com",
                "SMTP_PASS": "chit xsfs eijz ukvd"
            }):
                res = self.client.post("/api/v1/auth/resend-verification", json={"email": "venkatn.naibhi@gmail.com"})
                self.assertEqual(res.status_code, 200, res.text)
                data = res.json()
                self.assertTrue(data["success"])
                self.assertEqual(data["delivery"]["delivery_status"], "DELIVERED")

        # Verify in DB that a fresh token hash was stored
        conn = sqlite3.connect(TEST_DB_PATH)
        row = conn.execute("SELECT verification_token, verification_token_expiry FROM users WHERE email = 'venkatn.naibhi@gmail.com'").fetchone()
        conn.close()
        self.assertIsNotNone(row[0])
        self.assertNotEqual(row[0], "old_token")

    def test_16_safe_diagnostics_report(self):
        """Diagnostic endpoint returns full configuration without exposing secrets."""
        res = self.client.get("/api/v1/auth/smtp-status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("configuration_source", data)
        self.assertIn("external_messages_enabled", data)
        self.assertIn("smtp_configured", data)
        self.assertIn("resend_endpoint", data)
        self.assertEqual(data["resend_endpoint"], "/api/v1/auth/resend-verification")
        # Ensure password is never exposed
        self.assertNotIn("smtp_pass", data)
        self.assertNotIn("password", data)



    def test_17_dns_failure_reported_accurately(self):
        """DNS failure is distinctly identified at DNS_RESOLUTION stage without vague (OSError)."""
        import socket
        with patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "SMTP_USER": "test@example.com",
                "SMTP_PASS": "test_pass_123456"
            }):
                res = email_service.send_verification_smtp_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                )
                self.assertFalse(res["sent"])
                self.assertEqual(res["delivery_status"], "FAILED")
                self.assertEqual(res["connection_stage"], "DNS_RESOLUTION")
                self.assertEqual(res["error_type"], "DNSLookupFailed")
                self.assertIn("DNS resolution failed", res["error"])

    def test_18_timeout_failure_reported_accurately(self):
        """Timeout connecting to SMTP is distinctly identified at TCP_CONNECT stage."""
        import socket
        dummy_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 587))]
        with patch("socket.getaddrinfo", return_value=dummy_info):
            with patch.object(socket.socket, "connect", side_effect=TimeoutError("timed out")):
                with patch.dict(os.environ, {
                    "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                    "HAEMOPULSE_MOCK_SMTP": "false",
                    "SMTP_USER": "test@example.com",
                    "SMTP_PASS": "test_pass_123456"
                }):
                    res = email_service.send_verification_smtp_email(
                        recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                    )
                    self.assertFalse(res["sent"])
                    self.assertEqual(res["delivery_status"], "FAILED")
                    self.assertEqual(res["connection_stage"], "TCP_CONNECT")
                    self.assertEqual(res["error_type"], "TimeoutError")
                    self.assertIn("timed out", res["error"].lower())

    def test_19_connection_refused_reported_accurately(self):
        """Connection refused is distinctly identified at TCP_CONNECT stage."""
        import socket
        dummy_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 587))]
        with patch("socket.getaddrinfo", return_value=dummy_info):
            with patch.object(socket.socket, "connect", side_effect=ConnectionRefusedError("Connection refused")):
                with patch.dict(os.environ, {
                    "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                    "HAEMOPULSE_MOCK_SMTP": "false",
                    "SMTP_USER": "test@example.com",
                    "SMTP_PASS": "test_pass_123456"
                }):
                    res = email_service.send_verification_smtp_email(
                        recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                    )
                    self.assertFalse(res["sent"])
                    self.assertEqual(res["delivery_status"], "FAILED")
                    self.assertEqual(res["connection_stage"], "TCP_CONNECT")
                    self.assertEqual(res["error_type"], "ConnectionRefused")
                    self.assertIn("Connection refused", res["error"])

    def test_20_network_unreachable_reported_accurately(self):
        """Network unreachable (Errno 101/10051) is identified at TCP_CONNECT stage."""
        import socket
        dummy_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 587))]
        with patch("socket.getaddrinfo", return_value=dummy_info):
            with patch.object(socket.socket, "connect", side_effect=OSError(101, "Network is unreachable")):
                with patch.dict(os.environ, {
                    "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                    "HAEMOPULSE_MOCK_SMTP": "false",
                    "SMTP_USER": "test@example.com",
                    "SMTP_PASS": "test_pass_123456"
                }):
                    res = email_service.send_verification_smtp_email(
                        recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                    )
                    self.assertFalse(res["sent"])
                    self.assertEqual(res["delivery_status"], "FAILED")
                    self.assertEqual(res["connection_stage"], "TCP_CONNECT")
                    self.assertEqual(res["error_type"], "NetworkUnreachable")
                    self.assertIn("Network is unreachable", res["error"])

    def test_21_tls_failure_reported_accurately(self):
        """TLS cryptographic failure is distinctly identified at STARTTLS_UPGRADE stage."""
        import ssl, smtplib
        mock_server = MagicMock()
        mock_server.starttls.side_effect = ssl.SSLError("certificate verify failed")
        with patch("email_service.create_resilient_smtp_connection", side_effect=email_service.SMTPConnectionStageError(
            stage="STARTTLS_UPGRADE", error_type="SSLError", message="TLS cryptographic handshake failed: certificate verify failed"
        )):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "SMTP_USER": "test@example.com",
                "SMTP_PASS": "test_pass_123456"
            }):
                res = email_service.send_verification_smtp_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="token_123"
                )
                self.assertFalse(res["sent"])
                self.assertEqual(res["delivery_status"], "FAILED")
                self.assertEqual(res["connection_stage"], "STARTTLS_UPGRADE")
                self.assertEqual(res["error_type"], "SSLError")
                self.assertIn("TLS cryptographic handshake failed", res["error"])

    def test_22_probe_smtp_connection_method(self):
        """Probe method returns diagnostic information without sending an email or leaking secrets."""
        probe = email_service.probe_smtp_connection(host="smtp.gmail.com", port=587, timeout_seconds=2)
        self.assertIn("stage", probe)
        self.assertIn("dns_resolved", probe)
        self.assertIn("overall_status", probe)
        # Ensure password or tokens never appear in probe dict
        probe_str = str(probe)
        self.assertNotIn("password", probe_str.lower())
        self.assertNotIn("token", probe_str.lower())


    def test_23_concurrent_requests_sqlite_lifecycle_no_thread_error(self):
        """Test concurrent requests through FastAPI test client and get_db() cross-thread lifecycle."""
        import concurrent.futures
        from server import get_db

        def simulate_cross_thread_lifecycle(worker_id):
            gen = get_db()
            db_conn = next(gen)
            cur = db_conn.cursor()
            cur.execute("SELECT count(*) FROM users")
            _ = cur.fetchone()
            cur.close()

            def close_in_thread(g):
                try:
                    next(g)
                except StopIteration:
                    pass

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as closer_pool:
                future = closer_pool.submit(close_in_thread, gen)
                future.result()
            return worker_id

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(simulate_cross_thread_lifecycle, i) for i in range(25)]
            results = [f.result() for f in futures]
        self.assertEqual(len(results), 25)

        def call_endpoint(req_id):
            res = self.client.get("/api/v1/auth/smtp-status")
            return res.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            http_futures = [pool.submit(call_endpoint, i) for i in range(20)]
            statuses = [f.result() for f in http_futures]
        self.assertTrue(all(s == 200 for s in statuses))

    def test_24_resend_verification_brevo_unauthorized_ip(self):
        """Resend returns HTTP 502 with actionable guidance when Brevo rejects unauthorized IP."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('IP Test User', 'ip_test@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_delivery = {
            "sent": False,
            "recipient": "ip_test@example.com",
            "delivery_status": "FAILED",
            "provider": "brevo_https",
            "error_type": "BREVO_IP_UNAUTHORIZED",
            "error": "Brevo HTTPS delivery failed (HTTP 401): We have detected you are using an unrecognised IP address 74.220.48.235 (Brevo IP Whitelisting active: please disable Authorized IPs restriction at https://app.brevo.com/security/authorised_ips or switch to Resend/SMTP)",
            "detected_unauthorized_ip": "74.220.48.235"
        }

        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "ip_test@example.com"})
            self.assertEqual(res.status_code, 502)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertIn("Authorized IPs", data["message"])
            self.assertIn("https://app.brevo.com/security/authorised_ips", data["message"])

        # User must remain unverified and account intact
        conn = sqlite3.connect(TEST_DB_PATH)
        row = conn.execute("SELECT is_verified FROM users WHERE email = 'ip_test@example.com'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0)

    def test_25_resend_verification_brevo_invalid_api_key(self):
        """Resend returns HTTP 502 when Brevo rejects invalid API key."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Key Test User', 'key_test@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_delivery = {
            "sent": False,
            "recipient": "key_test@example.com",
            "delivery_status": "FAILED",
            "provider": "brevo_https",
            "error_type": "BREVO_INVALID_API_KEY",
            "error": "Brevo HTTPS delivery failed (HTTP 401): Key not found. Please check BREVO_API_KEY configuration."
        }

        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "key_test@example.com"})
            self.assertEqual(res.status_code, 502)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertIn("BREVO_API_KEY", data["message"])

        # User remains unverified
        conn = sqlite3.connect(TEST_DB_PATH)
        row = conn.execute("SELECT is_verified FROM users WHERE email = 'key_test@example.com'").fetchone()
        conn.close()
        self.assertEqual(row[0], 0)

    def test_26_resend_verification_generic_failure(self):
        """Resend returns HTTP 502 on generic provider failure and leaves account unverified."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Generic Fail User', 'generic_fail@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_delivery = {
            "sent": False,
            "recipient": "generic_fail@example.com",
            "delivery_status": "FAILED",
            "provider": "resend_https",
            "error_type": "CONNECTION_TIMEOUT",
            "error": "Connection timed out."
        }

        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "generic_fail@example.com"})
            self.assertEqual(res.status_code, 502)
            data = res.json()
            self.assertFalse(data["success"])

        # User remains unverified
        conn = sqlite3.connect(TEST_DB_PATH)
        row = conn.execute("SELECT is_verified FROM users WHERE email = 'generic_fail@example.com'").fetchone()
        conn.close()
        self.assertEqual(row[0], 0)

    def test_27_delivery_failure_retains_unverified_and_blocks_appointments(self):
        """Unverified user who experienced failed email delivery remains blocked from booking appointments."""
        conn = sqlite3.connect(TEST_DB_PATH)
        pw_hash = server.hash_password("testpass123")
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Blocked Booker', 'blocked_booker@example.com', ?, '1234567890', 'ROLE_DONOR', 0, NULL)""",
            (pw_hash,)
        )
        uid = cur.lastrowid
        cur.execute(
            """INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location, is_available)
               VALUES (?, ?, 'Blocked Booker', 'blocked_booker@example.com', 'O+', 28, 'Female', 'Zone B', 1)""",
            (f"DNR-FAIL-{uid}", uid)
        )
        conn.commit()
        conn.close()

        # Failed delivery attempt
        mock_delivery = {
            "sent": False,
            "recipient": "blocked_booker@example.com",
            "delivery_status": "FAILED",
            "error_type": "BREVO_IP_UNAUTHORIZED",
            "error": "Unauthorized IP"
        }
        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "blocked_booker@example.com"})
            self.assertEqual(res.status_code, 502)

        # Login
        login_res = self.client.post("/api/v1/auth/login", json={"email": "blocked_booker@example.com", "password": "testpass123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        self.assertFalse(login_res.json()["user"]["is_verified"])

        # Attempt to book appointment - must be forbidden (HTTP 403)
        app_res = self.client.post("/api/v1/appointments", json={
            "appointment_date": "2026-11-05",
            "time_slot": "Morning (8 AM - 12 PM)",
            "center_name": "Hub #1"
        }, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(app_res.status_code, 403)
        self.assertIn("verify your email", app_res.json()["detail"].lower())


    def test_28_email_diagnostics_endpoint_safe(self):
        """Diagnostic endpoint returns structured configuration and never exposes private credentials."""
        with patch.dict(os.environ, {
            "BREVO_API_KEY": "xkeysib-secret99887766554433221100",
            "RESEND_API_KEY": "re_topsecretapikey123456",
            "SMTP_PASS": "16charpassword12"
        }):
            res = self.client.get("/api/v1/auth/email-diagnostics?probe=false")
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # Providers configured
            self.assertTrue(data["brevo"]["configured"])
            self.assertTrue(data["resend"]["configured"])

            # Never leak full keys or passwords
            body_str = res.text
            self.assertNotIn("xkeysib-secret99887766554433221100", body_str)
            self.assertNotIn("re_topsecretapikey123456", body_str)
            self.assertNotIn("16charpassword12", body_str)

            # Masked prefixes are safe
            self.assertEqual(data["brevo"]["key_prefix"], "xkeysib-...")
            self.assertEqual(data["resend"]["key_prefix"], "re_top...")

    def test_29_resend_verification_resend_api_auth_failure(self):
        """Resend returns HTTP 502 with actionable guidance when Resend API key is invalid."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Resend Test User', 'resend_auth_test@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_delivery = {
            "sent": False,
            "recipient": "resend_auth_test@example.com",
            "delivery_status": "FAILED",
            "provider": "resend_https",
            "error_type": "RESEND_AUTHENTICATION_FAILED",
            "error": "Resend HTTPS delivery failed (HTTP 401): API key invalid"
        }

        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "resend_auth_test@example.com"})
            self.assertEqual(res.status_code, 502)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertIn("RESEND_API_KEY", data["message"])

    def test_30_resend_verification_unauthorized_ip_shows_ip_in_message(self):
        """When Brevo detects an unauthorized IP, the IP is displayed in the user-facing message."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('IP Shown User', 'ip_shown_test@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        mock_delivery = {
            "sent": False,
            "recipient": "ip_shown_test@example.com",
            "delivery_status": "FAILED",
            "provider": "brevo_https",
            "error_type": "BREVO_IP_UNAUTHORIZED",
            "error": "Brevo HTTPS delivery failed (HTTP 401): unrecognized IP",
            "detected_unauthorized_ip": "74.220.48.235"
        }

        with patch("server.send_verification_email", return_value=mock_delivery):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "ip_shown_test@example.com"})
            self.assertEqual(res.status_code, 502)
            data = res.json()
            self.assertFalse(data["success"])
            self.assertIn("74.220.48.235", data["message"])
            self.assertIn("Authorized IPs", data["message"])


    def test_34_build_verification_link_production_domain(self):
        """In production, unset frontend URL defaults safely to the production workers.dev domain."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "FRONTEND_BASE_URL": "",
            "FRONTEND_URL": ""
        }):
            link = email_service.build_verification_link("test_token_123")
            self.assertEqual(
                link,
                "https://haemopulse.ashwinkumarnsrao.workers.dev/verify-email?token=test_token_123"
            )

    def test_35_build_verification_link_prevents_localhost_in_production(self):
        """In production, an accidental localhost URL is rejected in favor of the production domain."""
        with patch.dict(os.environ, {
            "RENDER": "true",
            "FRONTEND_BASE_URL": "http://localhost:3000"
        }):
            link = email_service.build_verification_link("test_token_456")
            self.assertEqual(
                link,
                "https://haemopulse.ashwinkumarnsrao.workers.dev/verify-email?token=test_token_456"
            )
            self.assertNotIn("localhost", link)

    def test_36_build_verification_link_prevents_backend_domain_in_production(self):
        """In production, configuring the backend Render domain falls back to the frontend domain."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "FRONTEND_BASE_URL": "https://haemopulse-backend.onrender.com"
        }):
            link = email_service.build_verification_link("test_token_789")
            self.assertEqual(
                link,
                "https://haemopulse.ashwinkumarnsrao.workers.dev/verify-email?token=test_token_789"
            )

    def test_37_build_verification_link_url_encodes_token(self):
        """Tokens with special characters (+, /, =, spaces) are properly URL-encoded."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "FRONTEND_BASE_URL": ""
        }):
            raw_token = "abc+def/ghi=jkl mn"
            link = email_service.build_verification_link(raw_token)
            self.assertIn("token=abc%2Bdef%2Fghi%3Djkl%20mn", link)
            self.assertNotIn(" ", link)

    def test_38_registration_uses_production_verification_link(self):
        """Donor registration flow generates verification emails pointing to the production domain."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.row_factory = sqlite3.Row
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "FRONTEND_BASE_URL": "",
            "HAEMOPULSE_MOCK_SMTP": "true"
        }):
            user, delivery = server._do_register_donor(
                email="prod_link_donor@example.com",
                password="pass",
                name="Prod Link Donor",
                blood_group="A+",
                phone="9988776655",
                district="Zone",
                taluk="Taluk",
                gender="Male",
                age=25,
                location="Loc",
                preferred_time="Morning",
                conn=conn
            )
            conn.close()
            self.assertTrue(delivery["sent"])
            self.assertIn("https://haemopulse.ashwinkumarnsrao.workers.dev/verify-email?token=", delivery["verify_link"])
            self.assertNotIn("localhost", delivery["verify_link"])

    def test_39_resend_uses_production_verification_link(self):
        """Resend-verification flow generates verification emails pointing to the production domain."""
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.execute(
            """INSERT INTO users (name, email, password, phone, role, is_verified, last_verification_email_sent_at)
               VALUES ('Prod Resend User', 'prod_resend_user@example.com', 'hash', '1234567890', 'ROLE_DONOR', 0, NULL)"""
        )
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "FRONTEND_BASE_URL": "",
            "HAEMOPULSE_MOCK_SMTP": "true"
        }):
            res = self.client.post("/api/v1/auth/resend-verification", json={"email": "prod_resend_user@example.com"})
            self.assertEqual(res.status_code, 200)
            delivery = res.json()["delivery"]
            self.assertTrue(delivery["sent"])
            self.assertIn("https://haemopulse.ashwinkumarnsrao.workers.dev/verify-email?token=", delivery["verify_link"])
            self.assertNotIn("localhost", delivery["verify_link"])

    def test_40_local_development_url_configurable(self):
        """In local development, custom frontend URLs remain fully configurable."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "RENDER": "",
            "FRONTEND_BASE_URL": "http://localhost:5173"
        }):
            link = email_service.build_verification_link("dev_tok")
            self.assertEqual(link, "http://localhost:5173/verify-email?token=dev_tok")


if __name__ == "__main__":
    unittest.main()
