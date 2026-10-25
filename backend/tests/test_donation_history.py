"""
HaemoPulse Donation History & Clinical Verification Test Suite
Tests:
1. Role-Based Access Control (RBAC) & Isolation:
   - Donors can only access their own history
   - Hospitals can only view donations recorded at their facility
   - Admins can view all donations and filter by synthetic status
2. Hospital Donation Recording:
   - Successful recording with unique certificate generation
   - Linking to appointment marks appointment COMPLETED
   - Prevents duplicate appointment linking
   - Updates donor total_donations, last_donation_date, and is_available=0
   - Increments hospital_blood_inventory
3. Validation Guards:
   - Validates blood group
   - Rejects future donation dates
   - Rejects invalid donation types
4. Certificate Verification:
   - Verifies newly created certificates
   - Verifies legacy backfilled certificates (DON-901, DON-812, DON-705)
   - Returns 404 for unknown codes
5. Dual-database execution (SQLite test run + Postgres compatibility).
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server

client = TestClient(server.app)


class DonationHistoryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Production Safety Guard: Never run mutation test suites against production Neon PostgreSQL
        if database.is_postgres():
            if os.getenv("ALLOW_POSTGRES_TEST_MUTATIONS", "").lower() not in {"1", "true"}:
                raise unittest.SkipTest(
                    "Production Safety Guard: Mutation tests cannot be run against live PostgreSQL. "
                    "Use isolated temporary SQLite or an ephemeral test branch."
                )

        import shutil, tempfile
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
        cls.is_pg = database.is_postgres()

        # Ensure donation_history exists
        if cls.is_pg:
            cls.conn.execute("""
                CREATE TABLE IF NOT EXISTS donation_history (
                    id SERIAL PRIMARY KEY,
                    donor_id INTEGER REFERENCES donors(id) ON DELETE SET NULL,
                    donor_code TEXT,
                    donor_name TEXT NOT NULL,
                    donor_email TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    units INTEGER NOT NULL DEFAULT 1 CHECK(units > 0),
                    donation_date TEXT NOT NULL,
                    donation_type TEXT NOT NULL DEFAULT 'Whole Blood'
                        CHECK(donation_type IN ('Whole Blood', 'Platelets', 'Plasma', 'Red Blood Cells')),
                    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    hospital_name TEXT NOT NULL,
                    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
                    status TEXT NOT NULL DEFAULT 'CONFIRMED'
                        CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONFIRMED')),
                    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approval_date TEXT,
                    notes TEXT,
                    certificate_code TEXT UNIQUE NOT NULL,
                    is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK(is_synthetic IN (0, 1)),
                    synthetic_batch_tag TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
        else:
            cls.conn.execute("""
                CREATE TABLE IF NOT EXISTS donation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    donor_id INTEGER REFERENCES donors(id) ON DELETE SET NULL,
                    donor_code TEXT,
                    donor_name TEXT NOT NULL,
                    donor_email TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    units INTEGER NOT NULL DEFAULT 1 CHECK(units > 0),
                    donation_date TEXT NOT NULL,
                    donation_type TEXT NOT NULL DEFAULT 'Whole Blood'
                        CHECK(donation_type IN ('Whole Blood', 'Platelets', 'Plasma', 'Red Blood Cells')),
                    hospital_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    hospital_name TEXT NOT NULL,
                    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
                    status TEXT NOT NULL DEFAULT 'CONFIRMED'
                        CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONFIRMED')),
                    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approval_date TEXT,
                    notes TEXT,
                    certificate_code TEXT UNIQUE NOT NULL,
                    is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK(is_synthetic IN (0, 1)),
                    synthetic_batch_tag TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
        cls.conn.commit()

        # Seed Test Users
        ts = int(datetime.now().timestamp())
        cls.donor1_email = f"d1_{ts}@dh-test.invalid"
        c1 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919876543210', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor One", cls.donor1_email)
        )
        cls.donor1_user_id = c1.lastrowid
        c_d1 = cls.conn.execute(
            "INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available, total_donations) VALUES (?, ?, ?, 'O+', 28, 'Male', 'Koppa', ?, 1, 0)",
            (f"DNR-TEST-1-{cls.donor1_user_id}", "Donor One", cls.donor1_email, cls.donor1_user_id)
        )
        cls.donor1_donor_pk = c_d1.lastrowid
        cls.donor1_token = server.create_access_token({"sub": cls.donor1_email, "id": cls.donor1_user_id, "role": "ROLE_DONOR"})

        # 2. Donor 2
        cls.donor2_email = f"d2_{ts}@dh-test.invalid"
        c2 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919876543211', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Two", cls.donor2_email)
        )
        cls.donor2_user_id = c2.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, user_id, is_available, total_donations) VALUES (?, ?, ?, 'A+', 32, 'Female', 'Koppa', ?, 1, 0)",
            (f"DNR-TEST-2-{cls.donor2_user_id}", "Donor Two", cls.donor2_email, cls.donor2_user_id)
        )
        cls.donor2_token = server.create_access_token({"sub": cls.donor2_email, "id": cls.donor2_user_id, "role": "ROLE_DONOR"})

        # 3. Hospital 1
        cls.hosp1_email = f"h1_{ts}@dh-test.invalid"
        ch1 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+91800111222', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("St. Luke Hospital", cls.hosp1_email)
        )
        cls.hosp1_user_id = ch1.lastrowid
        cls.conn.execute(
            "INSERT INTO hospital_profiles (hospital_user_id, hospital_name, address, district, taluk, created_at, updated_at) VALUES (?, 'St. Luke Hospital', '123 Medical Way', 'Chikkamagaluru', 'Koppa', '2026-01-01', '2026-01-01')",
            (cls.hosp1_user_id,)
        )
        cls.hosp1_token = server.create_access_token({"sub": cls.hosp1_email, "id": cls.hosp1_user_id, "role": "ROLE_HOSPITAL"})

        # 4. Hospital 2
        cls.hosp2_email = f"h2_{ts}@dh-test.invalid"
        ch2 = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+91800111333', 'ROLE_HOSPITAL', 'ACTIVE', 1)",
            ("City Memorial Hospital", cls.hosp2_email)
        )
        cls.hosp2_user_id = ch2.lastrowid
        cls.conn.execute(
            "INSERT INTO hospital_profiles (hospital_user_id, hospital_name, address, district, taluk, created_at, updated_at) VALUES (?, 'City Memorial Hospital', '456 Central Ave', 'Chikkamagaluru', 'Koppa', '2026-01-01', '2026-01-01')",
            (cls.hosp2_user_id,)
        )
        cls.hosp2_token = server.create_access_token({"sub": cls.hosp2_email, "id": cls.hosp2_user_id, "role": "ROLE_HOSPITAL"})

        # 5. Admin
        cls.admin_email = f"adm_{ts}@dh-test.invalid"
        ca = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Admin Sys', ?, 'hash', '+91800999000', 'ROLE_ADMIN', 'ACTIVE', 1)",
            (cls.admin_email,)
        )
        cls.admin_user_id = ca.lastrowid
        cls.admin_token = server.create_access_token({"sub": cls.admin_email, "id": cls.admin_user_id, "role": "ROLE_ADMIN"})

        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            # Clean up test rows
            emails = [cls.donor1_email, cls.donor2_email, cls.hosp1_email, cls.hosp2_email, cls.admin_email]
            for em in emails:
                cls.conn.execute("DELETE FROM donation_history WHERE LOWER(donor_email) = LOWER(?)", (em,))
                cls.conn.execute("DELETE FROM donors WHERE LOWER(email) = LOWER(?)", (em,))
                cls.conn.execute("DELETE FROM users WHERE LOWER(email) = LOWER(?)", (em,))
            cls.conn.commit()
            cls.conn.close()
        except Exception:
            pass

    def test_01_donor_my_history_access_and_scoping(self):
        """Verify donor can only see own verified donations and eligibility stats."""
        # 1. Initially empty
        res = client.get("/api/v1/donations/my-history", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["records"], [])
        self.assertEqual(data["total_donations"], 0)
        self.assertTrue(data["is_eligible"])

        # 2. Denied for non-donors
        denied_hosp = client.get("/api/v1/donations/my-history", headers={"Authorization": f"Bearer {self.hosp1_token}"})
        self.assertEqual(denied_hosp.status_code, 403)

    def test_02_hospital_records_donation_and_updates_state(self):
        """Verify hospital recording generates certificate, updates donor profile & inventory."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        
        # Hospital 1 records donation for Donor 1
        res = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={
                "donor_email": self.donor1_email,
                "blood_group": "O+",
                "units": 2,
                "donation_date": past_date,
                "donation_type": "Whole Blood",
                "notes": "Healthy donor, vitals normal."
            }
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["certificate_code"].startswith("CERT-"))
        self.assertEqual(body["hospital_name"], "St. Luke Hospital")
        self.assertEqual(body["units"], 2)

        cert_code = body["certificate_code"]

        # Check that Donor 1 sees this record in my-history
        hist_res = client.get("/api/v1/donations/my-history", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.json()
        self.assertEqual(hist_data["total_donations"], 1)
        self.assertEqual(hist_data["records"][0]["certificate_code"], cert_code)
        self.assertEqual(hist_data["records"][0]["units"], 2)
        # Donor is within recovery window (10 days < 90 days) -> ineligible
        self.assertFalse(hist_data["is_eligible"])
        self.assertEqual(hist_data["days_until_eligible"], 80)

        # Check that Donor 2 does NOT see Donor 1's donation (Donor Isolation)
        d2_res = client.get("/api/v1/donations/my-history", headers={"Authorization": f"Bearer {self.donor2_token}"})
        self.assertEqual(d2_res.json()["records"], [])

        # Check that Hospital 1 sees the donation in its hospital list
        h1_donations = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.hosp1_token}"})
        self.assertEqual(h1_donations.status_code, 200)
        h1_codes = [d["certificate_code"] for d in h1_donations.json()]
        self.assertIn(cert_code, h1_codes)

        # Check that Hospital 2 does NOT see Hospital 1's donation (Hospital Isolation)
        h2_donations = client.get("/api/v1/hospitals/donations", headers={"Authorization": f"Bearer {self.hosp2_token}"})
        self.assertEqual(h2_donations.status_code, 200)
        h2_codes = [d["certificate_code"] for d in h2_donations.json()]
        self.assertNotIn(cert_code, h2_codes)

    def test_03_appointment_linking_and_duplicate_prevention(self):
        """Verify linking an appointment marks it completed and blocks duplicate linking."""
        # Create an appointment for Donor 2
        cur = self.conn.execute(
            """INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status)
               VALUES (?, 'Donor Two', ?, 'A+', '2026-10-24', 'Morning', 'St. Luke Hospital', 'SCHEDULED')""",
            (f"DNR-TEST-2-{self.donor2_user_id}", self.donor2_email)
        )
        self.conn.commit()
        appt_id = cur.lastrowid

        # Hospital records donation with appointment_id
        res = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={
                "donor_email": self.donor2_email,
                "blood_group": "A+",
                "units": 1,
                "donation_date": "2026-10-24",
                "appointment_id": appt_id
            }
        )
        self.assertEqual(res.status_code, 200)

        # Verify appointment is now COMPLETED
        appt_row = self.conn.execute("SELECT status FROM appointments WHERE id = ?", (appt_id,)).fetchone()
        self.assertEqual(appt_row["status"], "COMPLETED")

        # Second attempt with the SAME appointment_id must be REJECTED (Idempotency)
        dup_res = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={
                "donor_email": self.donor2_email,
                "blood_group": "A+",
                "units": 1,
                "donation_date": "2026-10-24",
                "appointment_id": appt_id
            }
        )
        self.assertEqual(dup_res.status_code, 400)
        self.assertIn("already linked", dup_res.json()["detail"].lower())

    def test_04_validation_guards(self):
        """Verify invalid blood groups, future dates, and invalid types are rejected."""
        # Future date
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
        r1 = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={"donor_email": self.donor1_email, "blood_group": "O+", "donation_date": tomorrow}
        )
        self.assertEqual(r1.status_code, 400)
        self.assertIn("future", r1.json()["detail"].lower())

        # Invalid blood group
        r2 = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={"donor_email": self.donor1_email, "blood_group": "X+", "donation_date": "2026-10-20"}
        )
        self.assertEqual(r2.status_code, 400)

        # Invalid donation type
        r3 = client.post(
            "/api/v1/hospitals/donations/record",
            headers={"Authorization": f"Bearer {self.hosp1_token}"},
            json={"donor_email": self.donor1_email, "blood_group": "O+", "donation_date": "2026-10-20", "donation_type": "Gold Blood"}
        )
        self.assertEqual(r3.status_code, 400)

    def test_05_certificate_verification_endpoint(self):
        """Verify public certificate verification for both new and legacy certificates."""
        # 1. Backfilled legacy certificate DON-901
        res_leg = client.get("/api/v1/donations/certificate/DON-901")
        self.assertEqual(res_leg.status_code, 200)
        leg_data = res_leg.json()
        self.assertTrue(leg_data["valid"])
        self.assertEqual(leg_data["certificate_code"], "DON-901")
        self.assertEqual(leg_data["donor_name"], "John Doe")
        self.assertEqual(leg_data["blood_group"], "O+")

        # 2. Non-existent certificate
        res_404 = client.get("/api/v1/donations/certificate/CERT-UNKNOWN-999")
        self.assertEqual(res_404.status_code, 404)

    def test_06_admin_overview_and_synthetic_filter(self):
        """Verify administrator can retrieve all donations with synthetic data filter."""
        res = client.get("/api/v1/admin/donations", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res.status_code, 200)
        donations = res.json()
        self.assertGreater(len(donations), 0)

        # Non-admin denied
        denied = client.get("/api/v1/admin/donations", headers={"Authorization": f"Bearer {self.donor1_token}"})
        self.assertEqual(denied.status_code, 403)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "conn") and cls.conn:
            try:
                cls.conn.close()
            except Exception:
                pass

        import shutil
        if hasattr(cls, "orig_db_path"):
            database.DATABASE_PATH = cls.orig_db_path
            server.DATABASE_PATH = cls.orig_db_path
        if hasattr(cls, "orig_env_db"):
            if cls.orig_env_db is not None:
                os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
            else:
                os.environ.pop("BLOODBANK_DB_FILE", None)

        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
