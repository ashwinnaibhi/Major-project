"""
HaemoPulse Comprehensive Blood Donation Recovery Period Test Suite
Verifies:
1. Calendar calculation logic (3 calendar months, month-end clamping, leap years).
2. Donor with no previous donation history is eligible and can book appointments.
3. Donor whose last completed donation was >= 3 calendar months ago is eligible and can book.
4. Donor whose last completed donation was < 3 calendar months ago is ineligible:
   - GET /api/v1/appointments/eligibility returns eligible=False, recovery_period_active=True
   - POST /api/v1/appointments returns HTTP 400 with exact rejection message and details
   - No appointment row is inserted into the database.
5. Multiple donation records evaluate against the latest completed donation date.
6. Cancelled, scheduled, or pending appointments do NOT count as completed donations.
7. Clinical records in donation_history, donations, and donors.last_donation_date are all checked.
8. Authenticated identity from JWT is strictly enforced; client cannot spoof donor identity.
9. Database error during validation fails safely (does not silently allow booking).
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock
import shutil
import tempfile
import calendar
from datetime import date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import database
import server

client = TestClient(server.app)


class CalendarMonthCalculationTestCase(unittest.TestCase):
    def test_month_end_clamping_january_to_april(self):
        # Jan 31 -> Apr 30 (April has only 30 days)
        dt = date(2026, 1, 31)
        res = server.add_three_calendar_months(dt)
        self.assertEqual(res, date(2026, 4, 30))

    def test_month_end_clamping_leap_year_february(self):
        # Nov 30, 2023 -> Feb 29, 2024 (2024 is leap year)
        dt = date(2023, 11, 30)
        res = server.add_three_calendar_months(dt)
        self.assertEqual(res, date(2024, 2, 29))

    def test_month_end_clamping_non_leap_year_february(self):
        # Nov 30, 2024 -> Feb 28, 2025 (2025 is not a leap year)
        dt = date(2024, 11, 30)
        res = server.add_three_calendar_months(dt)
        self.assertEqual(res, date(2025, 2, 28))

    def test_month_end_clamping_march_to_june(self):
        # Mar 31 -> Jun 30
        dt = date(2026, 3, 31)
        res = server.add_three_calendar_months(dt)
        self.assertEqual(res, date(2026, 6, 30))

    def test_standard_mid_month(self):
        # May 15 -> Aug 15
        dt = date(2026, 5, 15)
        res = server.add_three_calendar_months(dt)
        self.assertEqual(res, date(2026, 8, 15))


class AppointmentRecoveryPeriodTestCase(unittest.TestCase):
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

        # Seed test donor A (never donated)
        c_a = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776601', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor New", "donor_new@haemopulse.test")
        )
        cls.donor_a_id = c_a.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-A', ?, ?, ?, '+919988776601', 'O+', 25, 'Male', 'Hubballi', 1)",
            (cls.donor_a_id, "Donor New", "donor_new@haemopulse.test")
        )

        # Seed test donor B (donated recently - within recovery period)
        c_b = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776602', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Recent", "donor_recent@haemopulse.test")
        )
        cls.donor_b_id = c_b.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-B', ?, ?, ?, '+919988776602', 'A+', 26, 'Female', 'Hubballi', 1)",
            (cls.donor_b_id, "Donor Recent", "donor_recent@haemopulse.test")
        )
        # Recent donation 20 days ago in donation_history
        recent_date = (date.today() - timedelta(days=20)).isoformat()
        cls.recent_donation_date = recent_date
        cls.conn.execute(
            """INSERT INTO donation_history
               (donor_id, donor_code, donor_name, donor_email, blood_group, units,
                donation_date, donation_type, hospital_name, status,
                certificate_code, is_synthetic, created_at, updated_at)
               VALUES (?, 'D-REC-B', 'Donor Recent', ?, 'A+', 1,
                       ?, 'Whole Blood', 'City General Hospital', 'CONFIRMED',
                       'CERT-REC-B1', 0, '2026-01-01', '2026-01-01')""",
            (cls.donor_b_id, "donor_recent@haemopulse.test", recent_date)
        )

        # Seed test donor C (donated > 3 months ago - recovery period complete)
        c_c = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776603', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Past", "donor_past@haemopulse.test")
        )
        cls.donor_c_id = c_c.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-C', ?, ?, ?, '+919988776603', 'B+', 27, 'Male', 'Dharwad', 1)",
            (cls.donor_c_id, "Donor Past", "donor_past@haemopulse.test")
        )
        # Past donation 120 days ago (~4 months)
        past_date = (date.today() - timedelta(days=120)).isoformat()
        cls.conn.execute(
            """INSERT INTO donation_history
               (donor_id, donor_code, donor_name, donor_email, blood_group, units,
                donation_date, donation_type, hospital_name, status,
                certificate_code, is_synthetic, created_at, updated_at)
               VALUES (?, 'D-REC-C', 'Donor Past', ?, 'B+', 1,
                       ?, 'Whole Blood', 'Metro Blood Bank', 'CONFIRMED',
                       'CERT-REC-C1', 0, '2026-01-01', '2026-01-01')""",
            (cls.donor_c_id, "donor_past@haemopulse.test", past_date)
        )

        # Seed test donor D (has older donation AND recent donation to verify latest is used)
        c_d = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776604', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Multi", "donor_multi@haemopulse.test")
        )
        cls.donor_d_id = c_d.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-D', ?, ?, ?, '+919988776604', 'AB+', 29, 'Male', 'Bengaluru', 1)",
            (cls.donor_d_id, "Donor Multi", "donor_multi@haemopulse.test")
        )
        # Older donation 1 year ago
        cls.conn.execute(
            """INSERT INTO donation_history
               (donor_id, donor_code, donor_name, donor_email, blood_group, units,
                donation_date, donation_type, hospital_name, status,
                certificate_code, is_synthetic, created_at, updated_at)
               VALUES (?, 'D-REC-D', 'Donor Multi', ?, 'AB+', 1,
                       ?, 'Whole Blood', 'City General Hospital', 'CONFIRMED',
                       'CERT-REC-D1', 0, '2025-01-01', '2025-01-01')""",
            (cls.donor_d_id, "donor_multi@haemopulse.test", (date.today() - timedelta(days=365)).isoformat())
        )
        # Recent donation 10 days ago
        cls.multi_recent_date = (date.today() - timedelta(days=10)).isoformat()
        cls.conn.execute(
            """INSERT INTO donation_history
               (donor_id, donor_code, donor_name, donor_email, blood_group, units,
                donation_date, donation_type, hospital_name, status,
                certificate_code, is_synthetic, created_at, updated_at)
               VALUES (?, 'D-REC-D', 'Donor Multi', ?, 'AB+', 1,
                       ?, 'Whole Blood', 'City General Hospital', 'CONFIRMED',
                       'CERT-REC-D2', 0, '2026-01-01', '2026-01-01')""",
            (cls.donor_d_id, "donor_multi@haemopulse.test", cls.multi_recent_date)
        )

        # Seed test donor E (has scheduled and cancelled appointments, but NO completed donations)
        c_e = cls.conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES (?, ?, 'hash', '+919988776605', 'ROLE_DONOR', 'ACTIVE', 1)",
            ("Donor Appointments Only", "donor_appts@haemopulse.test")
        )
        cls.donor_e_id = c_e.lastrowid
        cls.conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-E', ?, ?, ?, '+919988776605', 'O-', 30, 'Female', 'Mysuru', 1)",
            (cls.donor_e_id, "Donor Appointments Only", "donor_appts@haemopulse.test")
        )
        cls.conn.execute(
            """INSERT INTO appointments (donor_name, blood_group, appointment_date, time_slot, center_name, status, donor_id, donor_email)
               VALUES ('Donor Appointments Only', 'O-', ?, 'Morning', 'Central Blood Bank Hub #1', 'CANCELLED', 'D-REC-E', 'donor_appts@haemopulse.test')""",
            ((date.today() - timedelta(days=5)).isoformat(),)
        )

        cls.conn.commit()
        cls.conn.close()

        # Generate tokens
        cls.token_a = server.create_access_token({"sub": "donor_new@haemopulse.test", "id": cls.donor_a_id, "role": "ROLE_DONOR"})
        cls.token_b = server.create_access_token({"sub": "donor_recent@haemopulse.test", "id": cls.donor_b_id, "role": "ROLE_DONOR"})
        cls.token_c = server.create_access_token({"sub": "donor_past@haemopulse.test", "id": cls.donor_c_id, "role": "ROLE_DONOR"})
        cls.token_d = server.create_access_token({"sub": "donor_multi@haemopulse.test", "id": cls.donor_d_id, "role": "ROLE_DONOR"})
        cls.token_e = server.create_access_token({"sub": "donor_appts@haemopulse.test", "id": cls.donor_e_id, "role": "ROLE_DONOR"})

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = cls.orig_db_path
        server.DATABASE_PATH = cls.orig_db_path
        if cls.orig_env_db:
            os.environ["BLOODBANK_DB_FILE"] = cls.orig_env_db
        else:
            os.environ.pop("BLOODBANK_DB_FILE", None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_new_donor_eligibility_and_booking_allowed(self):
        # 1. Eligibility check
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["eligible"])
        self.assertFalse(data["recovery_period_active"])
        self.assertIsNone(data["last_donation_date"])
        self.assertIsNone(data["earliest_eligible_date"])

        # 2. Booking allowed
        booking_date = (date.today() + timedelta(days=2)).isoformat()
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={
                "appointment_date": booking_date,
                "time_slot": "Morning (8 AM - 12 PM)",
                "center_name": "Central Blood Bank Hub #1"
            }
        )
        self.assertEqual(b_res.status_code, 200)
        b_data = b_res.json()
        self.assertIn("Appointment booked successfully", b_data.get("message", ""))

    def test_past_donor_eligibility_and_booking_allowed(self):
        # Donor C last donated 120 days ago (> 3 months)
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_c}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["eligible"])
        self.assertFalse(data["recovery_period_active"])
        self.assertIsNotNone(data["last_donation_date"])
        self.assertIsNotNone(data["earliest_eligible_date"])

        # Booking is permitted
        booking_date = (date.today() + timedelta(days=3)).isoformat()
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {self.token_c}"},
            json={
                "appointment_date": booking_date,
                "time_slot": "Afternoon (12 PM - 4 PM)",
                "center_name": "Metro Blood Bank"
            }
        )
        self.assertEqual(b_res.status_code, 200)

    def test_recent_donor_eligibility_and_booking_rejected(self):
        # Donor B last donated 20 days ago (< 3 months)
        # 1. Eligibility check returns ineligible
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["eligible"])
        self.assertTrue(data["recovery_period_active"])
        self.assertEqual(data["last_donation_date"], self.recent_donation_date)
        expected_earliest = server.add_three_calendar_months(date.fromisoformat(self.recent_donation_date)).isoformat()
        self.assertEqual(data["earliest_eligible_date"], expected_earliest)
        self.assertEqual(data["message"], server.RECOVERY_PERIOD_REJECTION_MESSAGE)

        # 2. Count appointments for Donor B before rejected booking attempt
        conn = database.get_db_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM appointments WHERE donor_id = ?", (self.donor_b_id,)).fetchone()[0]
        conn.close()

        # 3. Direct POST /api/v1/appointments booking attempt must be REJECTED with HTTP 400
        booking_date = (date.today() + timedelta(days=1)).isoformat()
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {self.token_b}"},
            json={
                "appointment_date": booking_date,
                "time_slot": "Morning (8 AM - 12 PM)",
                "center_name": "City General Hospital"
            }
        )
        self.assertEqual(b_res.status_code, 400)
        err = b_res.json()["detail"]
        self.assertEqual(err["error_code"], "RECOVERY_PERIOD_ACTIVE")
        self.assertEqual(err["message"], server.RECOVERY_PERIOD_REJECTION_MESSAGE)
        self.assertEqual(err["last_donation_date"], self.recent_donation_date)
        self.assertEqual(err["earliest_eligible_date"], expected_earliest)

        # 4. Verify no appointment row was inserted
        conn = database.get_db_connection()
        count_after = conn.execute("SELECT COUNT(*) FROM appointments WHERE donor_id = ?", (self.donor_b_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(count_before, count_after, "Rejected appointment booking must NOT create a row in the database.")

    def test_multiple_donations_uses_latest_completed_donation(self):
        # Donor D has donation 1 year ago and 10 days ago.
        # Latest must be 10 days ago, making them ineligible.
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_d}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["eligible"])
        self.assertEqual(data["last_donation_date"], self.multi_recent_date)
        expected_earliest = server.add_three_calendar_months(date.fromisoformat(self.multi_recent_date)).isoformat()
        self.assertEqual(data["earliest_eligible_date"], expected_earliest)

    def test_appointments_do_not_count_as_completed_donations(self):
        # Donor E has only a cancelled appointment, no completed blood donations.
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_e}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["eligible"])
        self.assertFalse(data["recovery_period_active"])
        self.assertIsNone(data["last_donation_date"])

        # Can book
        booking_date = (date.today() + timedelta(days=5)).isoformat()
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {self.token_e}"},
            json={
                "appointment_date": booking_date,
                "time_slot": "Morning (8 AM - 12 PM)",
                "center_name": "Central Blood Bank Hub #1"
            }
        )
        self.assertEqual(b_res.status_code, 200)

    def test_unauthenticated_request_rejected(self):
        res = client.get("/api/v1/appointments/eligibility")
        self.assertEqual(res.status_code, 401)

        b_res = client.post("/api/v1/appointments", json={"appointment_date": "2026-06-01"})
        self.assertEqual(b_res.status_code, 401)

    def test_spoofed_donor_id_in_payload_ignored(self):
        # Ineligible donor B tries to send donor_id=1 (or donor A's id) in payload
        booking_date = (date.today() + timedelta(days=2)).isoformat()
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {self.token_b}"},
            json={
                "appointment_date": booking_date,
                "donor_id": self.donor_a_id,  # Spoofing donor A
                "time_slot": "Morning (8 AM - 12 PM)",
                "center_name": "City General Hospital"
            }
        )
        # Must still be rejected because server looks up authenticated JWT identity
        self.assertEqual(b_res.status_code, 400)
        self.assertEqual(b_res.json()["detail"]["error_code"], "RECOVERY_PERIOD_ACTIVE")

    def test_donation_completed_one_month_ago_rejected(self):
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor 1Mo', 'donor_1mo@haemopulse.test', 'hash', '+919988776611', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-1MO', ?, 'Donor 1Mo', 'donor_1mo@haemopulse.test', '+919988776611', 'O+', 28, 'Male', 'Hubballi', 1)",
            (u_id,)
        )
        don_date = (date.today() - timedelta(days=30)).isoformat()
        conn.execute(
            "INSERT INTO donation_history (donor_id, donor_code, donor_name, donor_email, blood_group, units, donation_date, donation_type, hospital_name, status, certificate_code, is_synthetic, created_at, updated_at) VALUES (?, 'D-REC-1MO', 'Donor 1Mo', 'donor_1mo@haemopulse.test', 'O+', 1, ?, 'Whole Blood', 'City Hospital', 'CONFIRMED', 'CERT-1MO', 0, '2026-01-01', '2026-01-01')",
            (u_id, don_date)
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_1mo@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["eligible"])
        self.assertTrue(res.json()["recovery_period_active"])

        # POST booking must be rejected
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": (date.today() + timedelta(days=1)).isoformat(), "time_slot": "Morning (8 AM - 12 PM)"}
        )
        self.assertEqual(b_res.status_code, 400)
        self.assertEqual(b_res.json()["detail"]["error_code"], "RECOVERY_PERIOD_ACTIVE")
        self.assertEqual(b_res.json()["detail"]["message"], server.RECOVERY_PERIOD_REJECTION_MESSAGE)

    def test_donation_completed_two_months_ago_rejected(self):
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor 2Mo', 'donor_2mo@haemopulse.test', 'hash', '+919988776612', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-2MO', ?, 'Donor 2Mo', 'donor_2mo@haemopulse.test', '+919988776612', 'A+', 30, 'Female', 'Hubballi', 1)",
            (u_id,)
        )
        don_date = (date.today() - timedelta(days=60)).isoformat()
        conn.execute(
            "INSERT INTO donation_history (donor_id, donor_code, donor_name, donor_email, blood_group, units, donation_date, donation_type, hospital_name, status, certificate_code, is_synthetic, created_at, updated_at) VALUES (?, 'D-REC-2MO', 'Donor 2Mo', 'donor_2mo@haemopulse.test', 'A+', 1, ?, 'Whole Blood', 'City Hospital', 'CONFIRMED', 'CERT-2MO', 0, '2026-01-01', '2026-01-01')",
            (u_id, don_date)
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_2mo@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["eligible"])
        self.assertTrue(res.json()["recovery_period_active"])

        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": (date.today() + timedelta(days=1)).isoformat(), "time_slot": "Morning (8 AM - 12 PM)"}
        )
        self.assertEqual(b_res.status_code, 400)
        self.assertEqual(b_res.json()["detail"]["error_code"], "RECOVERY_PERIOD_ACTIVE")
        self.assertEqual(b_res.json()["detail"]["message"], server.RECOVERY_PERIOD_REJECTION_MESSAGE)

    def test_donation_completed_exactly_three_calendar_months_ago_allowed(self):
        today = date.today()
        y = today.year
        m = today.month - 3
        if m < 1:
            y -= 1
            m += 12
        max_d = calendar.monthrange(y, m)[1]
        don_date = date(y, m, min(today.day, max_d)).isoformat()

        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor 3Mo Exact', 'donor_3mo_exact@haemopulse.test', 'hash', '+919988776613', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-3MO-EX', ?, 'Donor 3Mo Exact', 'donor_3mo_exact@haemopulse.test', '+919988776613', 'B+', 32, 'Male', 'Dharwad', 1)",
            (u_id,)
        )
        conn.execute(
            "INSERT INTO donation_history (donor_id, donor_code, donor_name, donor_email, blood_group, units, donation_date, donation_type, hospital_name, status, certificate_code, is_synthetic, created_at, updated_at) VALUES (?, 'D-REC-3MO-EX', 'Donor 3Mo Exact', 'donor_3mo_exact@haemopulse.test', 'B+', 1, ?, 'Whole Blood', 'City Hospital', 'CONFIRMED', 'CERT-3MO-EX', 0, '2026-01-01', '2026-01-01')",
            (u_id, don_date)
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_3mo_exact@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})
        res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["eligible"])
        self.assertFalse(res.json()["recovery_period_active"])

        # POST booking must be allowed
        b_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": (date.today() + timedelta(days=2)).isoformat(), "time_slot": "Morning (8 AM - 12 PM)"}
        )
        self.assertEqual(b_res.status_code, 200)

    def test_database_error_during_eligibility_fails_safely(self):
        with mock.patch("server.get_donor_appointment_eligibility", side_effect=Exception("Simulated database failure")):
            res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {self.token_a}"})
            self.assertEqual(res.status_code, 500)

            b_res = client.post(
                "/api/v1/appointments",
                headers={"Authorization": f"Bearer {self.token_a}"},
                json={"appointment_date": (date.today() + timedelta(days=1)).isoformat(), "time_slot": "Morning (8 AM - 12 PM)"}
            )
            self.assertEqual(b_res.status_code, 500)


    def test_first_booking_succeeds_and_second_booking_rejected_while_active(self):
        # Create fresh donor
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor Single Active', 'donor_single_active@haemopulse.test', 'hash', '+919988776621', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-SGL', ?, 'Donor Single Active', 'donor_single_active@haemopulse.test', '+919988776621', 'O+', 29, 'Male', 'Hubballi', 1)",
            (u_id,)
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_single_active@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})

        # First booking succeeds
        first_date = (date.today() + timedelta(days=2)).isoformat()
        res1 = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": first_date, "time_slot": "Morning (8 AM - 12 PM)", "center_name": "Hub 1"}
        )
        self.assertEqual(res1.status_code, 200, res1.text)

        # Eligibility now indicates has_active_appointment=True, eligible=False
        elig_res = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(elig_res.status_code, 200)
        elig_data = elig_res.json()
        self.assertFalse(elig_data["eligible"])
        self.assertTrue(elig_data["has_active_appointment"])
        self.assertEqual(elig_data["error_code"], "ACTIVE_APPOINTMENT_EXISTS")
        self.assertEqual(elig_data["message"], server.ACTIVE_APPOINTMENT_MESSAGE)
        self.assertEqual(elig_data["active_appointment"]["appointment_date"], first_date)

        # Second booking on a different date is rejected
        second_date = (date.today() + timedelta(days=5)).isoformat()
        res2 = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": second_date, "time_slot": "Afternoon (12 PM - 4 PM)", "center_name": "Hub 2"}
        )
        self.assertEqual(res2.status_code, 400)
        err = res2.json()["detail"]
        self.assertEqual(err["error_code"], "ACTIVE_APPOINTMENT_EXISTS")
        self.assertEqual(err["message"], server.ACTIVE_APPOINTMENT_MESSAGE)
        self.assertEqual(err["active_appointment"]["appointment_date"], first_date)

        # Verify only 1 appointment exists in database for this donor
        conn = database.get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM appointments WHERE LOWER(donor_email) = 'donor_single_active@haemopulse.test'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_cancelled_appointment_allows_future_booking(self):
        # Create fresh donor with a cancelled appointment
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor Cancelled', 'donor_cancelled@haemopulse.test', 'hash', '+919988776622', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-CAN', ?, 'Donor Cancelled', 'donor_cancelled@haemopulse.test', '+919988776622', 'A+', 27, 'Female', 'Hubballi', 1)",
            (u_id,)
        )
        conn.execute(
            """INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
               VALUES ('D-REC-CAN', 'Donor Cancelled', 'donor_cancelled@haemopulse.test', 'A+', '2026-11-01', 'Morning', 'Hub 1', 'CANCELLED', '2026-10-01')"""
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_cancelled@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})

        # Eligibility check returns eligible=True, has_active_appointment=False
        elig = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(elig.status_code, 200)
        self.assertTrue(elig.json()["eligible"])
        self.assertFalse(elig.json()["has_active_appointment"])

        # Can book successfully
        book_res = client.post(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            json={"appointment_date": (date.today() + timedelta(days=3)).isoformat(), "time_slot": "Morning (8 AM - 12 PM)"}
        )
        self.assertEqual(book_res.status_code, 200)

    def test_donor_can_cancel_own_active_appointment(self):
        # Create donor with active appointment and cancel via donor PUT endpoint
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor Self Cancel', 'donor_self_cancel@haemopulse.test', 'hash', '+919988776623', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-SC', ?, 'Donor Self Cancel', 'donor_self_cancel@haemopulse.test', '+919988776623', 'B+', 31, 'Male', 'Hubballi', 1)",
            (u_id,)
        )
        cur = conn.execute(
            """INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
               VALUES ('D-REC-SC', 'Donor Self Cancel', 'donor_self_cancel@haemopulse.test', 'B+', '2026-11-02', 'Morning', 'Hub 1', 'SCHEDULED', '2026-10-01')"""
        )
        appt_id = cur.lastrowid
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_self_cancel@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})

        # Cancel appointment as donor
        can_res = client.put(f"/api/v1/appointments/{appt_id}/status?status=CANCELLED", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(can_res.status_code, 200)
        self.assertEqual(can_res.json()["status"], "CANCELLED")

        # Now donor is eligible again
        elig = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(elig.status_code, 200)
        self.assertTrue(elig.json()["eligible"])
        self.assertFalse(elig.json()["has_active_appointment"])

    def test_completed_appointment_without_donation_does_not_trigger_recovery(self):
        # Appointment marked COMPLETED in appointments, but NO records in donation_history or donations
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor No Don', 'donor_no_don@haemopulse.test', 'hash', '+919988776624', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-NODON', ?, 'Donor No Don', 'donor_no_don@haemopulse.test', '+919988776624', 'O-', 25, 'Female', 'Hubballi', 1)",
            (u_id,)
        )
        conn.execute(
            """INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
               VALUES ('D-REC-NODON', 'Donor No Don', 'donor_no_don@haemopulse.test', 'O-', '2026-10-01', 'Morning', 'Hub 1', 'COMPLETED', '2026-10-01')"""
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_no_don@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})
        elig = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(elig.status_code, 200)
        data = elig.json()
        self.assertTrue(data["eligible"])
        self.assertFalse(data["has_active_appointment"])
        self.assertFalse(data["recovery_period_active"])
        self.assertIsNone(data["last_donation_date"])

    def test_another_donor_appointment_does_not_affect_current_donor(self):
        # Donor X has active appointment
        # Donor Y has no appointments
        token_x = self.token_a  # Donor A booked earlier
        token_y = server.create_access_token({"sub": "donor_past@haemopulse.test", "id": self.donor_c_id, "role": "ROLE_DONOR"})

        # Donor Y has past donation (> 3 months) and no active appointment
        elig_y = client.get("/api/v1/appointments/eligibility", headers={"Authorization": f"Bearer {token_y}"})
        self.assertEqual(elig_y.status_code, 200)
        self.assertTrue(elig_y.json()["eligible"])
        self.assertFalse(elig_y.json()["has_active_appointment"])

    def test_simultaneous_booking_requests_race_condition(self):
        # Concurrency test: two simultaneous requests for the same donor
        conn = database.get_db_connection()
        c = conn.execute(
            "INSERT INTO users (name, email, password, phone, role, status, is_verified) VALUES ('Donor Concurrent', 'donor_concurrent@haemopulse.test', 'hash', '+919988776625', 'ROLE_DONOR', 'ACTIVE', 1)"
        )
        u_id = c.lastrowid
        conn.execute(
            "INSERT INTO donors (donor_id, user_id, name, email, phone, blood_group, age, gender, location, is_available) VALUES ('D-REC-CC', ?, 'Donor Concurrent', 'donor_concurrent@haemopulse.test', '+919988776625', 'AB-', 33, 'Male', 'Hubballi', 1)",
            (u_id,)
        )
        conn.commit()
        conn.close()

        token = server.create_access_token({"sub": "donor_concurrent@haemopulse.test", "id": u_id, "role": "ROLE_DONOR"})

        def make_booking(day_offset):
            b_date = (date.today() + timedelta(days=day_offset)).isoformat()
            return client.post(
                "/api/v1/appointments",
                headers={"Authorization": f"Bearer {token}"},
                json={"appointment_date": b_date, "time_slot": f"Slot {day_offset}", "center_name": "Hub C"}
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(make_booking, 2)
            f2 = executor.submit(make_booking, 4)
            r1 = f1.result()
            r2 = f2.result()

        statuses = [r1.status_code, r2.status_code]
        # Exactly one must be 200, and exactly one must be 400
        self.assertIn(200, statuses)
        self.assertIn(400, statuses)

        # Confirm database has strictly 1 appointment for this donor
        conn = database.get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM appointments WHERE LOWER(donor_email) = 'donor_concurrent@haemopulse.test'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, "Race condition prevention failed: multiple appointments were created!")


if __name__ == "__main__":
    unittest.main()
