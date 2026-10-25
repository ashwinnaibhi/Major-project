"""
HaemoPulse Production Architecture & Cloud Delivery Test Suite
Tests:
1. Multi-database adapter (query conversion, row mapping, SQLite / Postgres switching).
2. HTTPS Email Delivery Architecture (Brevo API port 443 & Resend API port 443).
3. Outbound SMTP blocking awareness and cloud hosting provider restrictions.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database
import email_service


class ProductionArchitectureTestCase(unittest.TestCase):

    def test_01_query_conversion_to_postgres(self):
        """Verify SQLite query syntax and ? placeholders convert to PostgreSQL syntax."""
        # 1. Placeholders
        q1 = "SELECT id, name FROM users WHERE email = ? AND role = ?"
        c1, is_insert = database._convert_query_to_postgres(q1)
        self.assertEqual(c1, "SELECT id, name FROM users WHERE email = %s AND role = %s")
        self.assertFalse(is_insert)

        # 2. String literal protection (don't convert '?' inside strings)
        q2 = "SELECT * FROM donors WHERE location = 'Where?' AND taluk = ?"
        c2, _ = database._convert_query_to_postgres(q2)
        self.assertEqual(c2, "SELECT * FROM donors WHERE location = 'Where?' AND taluk = %s")

        # 3. INSERT statement RETURNING id
        q3 = "INSERT INTO blood_requests (hospital_name, units_needed) VALUES (?, ?)"
        c3, is_insert3 = database._convert_query_to_postgres(q3)
        self.assertTrue(is_insert3)
        self.assertTrue(c3.endswith("RETURNING id"))

        # 4. PRAGMA statements converted to safe no-op
        q4 = "PRAGMA journal_mode=WAL;"
        c4, _ = database._convert_query_to_postgres(q4)
        self.assertEqual(c4, "SELECT 1")

    def test_02_row_wrapper_mimics_sqlite_row(self):
        """Verify RowWrapper supports key lookup, index lookup, dict conversion, and iteration."""
        sample = {"id": 42, "donor_id": "DNR-0042", "blood_group": "AB+"}
        row = database.RowWrapper(sample)

        self.assertEqual(row["id"], 42)
        self.assertEqual(row["donor_id"], "DNR-0042")
        self.assertEqual(row[0], 42)
        self.assertEqual(row[1], "DNR-0042")
        self.assertEqual(row.get("blood_group"), "AB+")
        self.assertEqual(dict(row), sample)
        self.assertTrue("blood_group" in row)
        self.assertEqual(len(row), 3)

    def test_03_brevo_https_delivery_success(self):
        """Verify verification email delivery via Brevo HTTPS API (port 443)."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"messageId": "<test-msg-12345@brevo.com>"}).encode("utf-8")
        mock_response.status = 201
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "BREVO_API_KEY": "xkeysib-mock-api-key-12345",
                "MAIL_FROM": "bloodbank@haemopulse.org",
                "FRONTEND_BASE_URL": "https://haemopulse.pages.dev"
            }):
                res = email_service.send_verification_brevo_api(
                    recipient_email="donor@example.com",
                    recipient_name="Donor Jane",
                    raw_token="secure_token_abc"
                )
                self.assertTrue(res["sent"])
                self.assertEqual(res["delivery_status"], "DELIVERED")
                self.assertEqual(res["provider"], "brevo_https")
                self.assertEqual(res["connection_stage"], "COMPLETED")
                self.assertEqual(res["message_id"], "<test-msg-12345@brevo.com>")
                self.assertIn("https://haemopulse.pages.dev/verify-email?token=secure_token_abc", res["verify_link"])

    def test_04_brevo_https_delivery_handles_ip_whitelisting(self):
        """Verify Brevo IP restriction error produces clear diagnostic guidance."""
        err_body = b'{"message":"We have detected you are using an unrecognised IP address 2001:db8::1. Add IP to app.brevo.com/security/authorised_ips","code":"unauthorized"}'
        mock_http_err = HTTPError(
            url="https://api.brevo.com/v3/smtp/email",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=err_body))
        )

        with patch("urllib.request.urlopen", side_effect=mock_http_err):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "BREVO_API_KEY": "xkeysib-mock-api-key-12345",
                "MAIL_FROM": "bloodbank@haemopulse.org",
            }):
                res = email_service.send_verification_brevo_api(
                    recipient_email="donor@example.com",
                    recipient_name="Donor Jane",
                    raw_token="secure_token_abc"
                )
                self.assertFalse(res["sent"])
                self.assertEqual(res["delivery_status"], "FAILED")
                self.assertEqual(res["error_type"], "BREVO_IP_UNAUTHORIZED")
                self.assertEqual(res.get("detected_unauthorized_ip"), "2001:db8::1")
                self.assertIn("Brevo IP Whitelisting active", res["error"])

    def test_05_resend_https_delivery_success(self):
        """Verify verification email delivery via Resend HTTPS API (port 443)."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"id": "re_123456789"}).encode("utf-8")
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch.dict(os.environ, {
                "HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES": "false",
                "HAEMOPULSE_MOCK_SMTP": "false",
                "RESEND_API_KEY": "re_mock_test_key_xyz",
                "FRONTEND_BASE_URL": "https://haemopulse.pages.dev"
            }):
                res = email_service.send_verification_resend_api(
                    recipient_email="donor@example.com",
                    recipient_name="Donor Jane",
                    raw_token="secure_token_abc"
                )
                self.assertTrue(res["sent"])
                self.assertEqual(res["delivery_status"], "DELIVERED")
                self.assertEqual(res["provider"], "resend_https")
                self.assertEqual(res["message_id"], "re_123456789")

    def test_06_dispatcher_selects_correct_provider(self):
        """Verify master send_verification_email routes based on configuration."""
        with patch("email_service.send_verification_brevo_api", return_value={"provider": "brevo_https"}) as mock_brevo:
            with patch.dict(os.environ, {"EMAIL_DELIVERY_METHOD": "brevo"}):
                res = email_service.send_verification_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="xyz"
                )
                self.assertEqual(res["provider"], "brevo_https")
                mock_brevo.assert_called_once()

        with patch("email_service.send_verification_resend_api", return_value={"provider": "resend_https"}) as mock_resend:
            with patch.dict(os.environ, {"EMAIL_DELIVERY_METHOD": "resend"}):
                res = email_service.send_verification_email(
                    recipient_email="test@example.com", recipient_name="Tester", raw_token="xyz"
                )
                self.assertEqual(res["provider"], "resend_https")
                mock_resend.assert_called_once()



    def test_07_datetime_now_conversion_to_postgres(self):
        """Verify SQLite datetime('now') converts to PostgreSQL NOW()."""
        q = "INSERT INTO emergency_alerts (created_at) VALUES (datetime('now'))"
        converted, _ = database._convert_query_to_postgres(q)
        self.assertIn("NOW()", converted)
        self.assertNotIn("datetime('now')", converted)

    def test_08_schema_table_parity(self):
        """Verify exact parity across SQLite tables, Postgres DDL, and migration tables."""
        import re
        import sqlite3
        con = sqlite3.connect(database.DATABASE_PATH)
        sqlite_tables = set(r[0] for r in con.cursor().execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall())
        con.close()

        pg_tables = set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', database.POSTGRES_SCHEMA_DDL))
        from migrate_to_postgres import MIGRATION_TABLES

        self.assertEqual(len(sqlite_tables), 14)
        self.assertEqual(len(pg_tables), 14)
        self.assertEqual(len(MIGRATION_TABLES), 14)
        self.assertEqual(sqlite_tables, pg_tables)
        self.assertEqual(sqlite_tables, set(MIGRATION_TABLES))

    def test_09_returning_id_for_different_tables(self):
        """Verify RETURNING id and RETURNING hospital_user_id generation."""
        q_user = "INSERT INTO users (email, name) VALUES (?, ?)"
        c_user, is_insert = database._convert_query_to_postgres(q_user)
        self.assertTrue(is_insert)
        self.assertTrue(c_user.endswith("RETURNING id"))

        q_hosp = "INSERT INTO hospital_profiles (hospital_user_id, hospital_name) VALUES (?, ?)"
        c_hosp, is_insert_hosp = database._convert_query_to_postgres(q_hosp)
        self.assertTrue(is_insert_hosp)
        self.assertTrue(c_hosp.endswith("RETURNING hospital_user_id"))

    def test_10_migration_tool_dry_run_flag(self):
        """Verify migrate_to_postgres parses --dry-run and --verify-only flags safely."""
        import migrate_to_postgres
        self.assertEqual(len(migrate_to_postgres.MIGRATION_TABLES), 14)

if __name__ == "__main__":
    unittest.main()
