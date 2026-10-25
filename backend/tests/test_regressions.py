"""Regression checks run against a disposable SQLite database, never the user database."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
import shutil
TEST_DB_PATH = str(Path(tempfile.gettempdir()) / f"haemopulse-regression-{os.getpid()}.sqlite3")
ORIGINAL_DB_PATH = BACKEND_DIR / "bloodbank.db"
if ORIGINAL_DB_PATH.exists():
    shutil.copyfile(str(ORIGINAL_DB_PATH), TEST_DB_PATH)
os.environ["BLOODBANK_DB_FILE"] = TEST_DB_PATH
os.environ["JWT_SECRET"] = "test-only-secret-do-not-use-in-production-123456789"
os.environ["HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES"] = "true"
os.environ["HAEMOPULSE_ENABLE_DEMO_SEED"] = "false"
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASS"] = ""
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
sys.path.insert(0, str(BACKEND_DIR))

import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(server.app)


def connect():
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_user(email: str, role: str, *, verified: int = 1, password: str = "Test-password-123") -> tuple[int, str]:
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name,email,password,phone,role,is_verified,status) VALUES (?,?,?,?,?,?, 'ACTIVE')",
            ("Test " + role, email, server.hash_password(password), "+911234567890", role, verified),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()
    token = server.create_access_token({"sub": email, "id": user_id, "role": role})
    return user_id, token


def add_donor(donor_id: str, email: str, *, score: float | None = 85, lat: float | None = 0.0, lon: float | None = 0.03,
              consent: str = "OPTED_IN", blood_group: str = "O+", district: str = "Bengaluru Urban", taluk: str = "Anekal") -> int:
    conn = connect()
    try:
        cursor = conn.execute(
            """INSERT INTO donors
            (donor_id,name,email,blood_group,age,gender,location,distance_km,last_donation_days,
             last_donation_date,total_donations,donation_frequency,previous_response_rate,preferred_time,
             health_score,availability_status,availability_score,is_available,district,taluk,latitude,longitude,consent)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (donor_id, donor_id, email, blood_group, 30, "Male", "Bengaluru", None, 180, None, 1, 1, .8,
             "Morning", 90, "HIGH" if (score or 0) >= 75 else "LOW", score, 1, district, taluk, lat, lon, consent),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


ADMIN_ID, ADMIN_TOKEN = create_user("admin-test@haemopulse.invalid", "ROLE_ADMIN")
HOSPITAL_ID, HOSPITAL_TOKEN = create_user("hospital-test@haemopulse.invalid", "ROLE_HOSPITAL")
DONOR_USER_ID, DONOR_TOKEN = create_user("profile-test@haemopulse.invalid", "ROLE_DONOR", verified=0)



def test_haversine_and_coordinate_validation():
    assert server.haversine_distance_km(0, 0, 0, 0) == 0
    assert abs(server.haversine_distance_km(0, 0, 0, 1) - 111.195) < 0.2
    assert server.valid_coordinates(0, 180)
    assert not server.valid_coordinates(91, 0)
    assert not server.valid_coordinates(float("nan"), 0)


def test_password_hashing_and_legacy_upgrade_support():
    stored = server.hash_password("Strong-password-123")
    assert stored.startswith("pbkdf2_sha256$")
    assert server.verify_password("Strong-password-123", stored) == (True, False)
    assert server.verify_password("Wrong-password", stored) == (False, False)
    import hashlib
    assert server.verify_password("legacy-pass", hashlib.sha256(b"legacy-pass").hexdigest()) == (True, True)


def test_registration_forces_donor_role_and_does_not_invent_score():
    response = client.post("/api/v1/auth/register", json={
        "name": "Regression Donor", "email": "new-donor@haemopulse.invalid", "password": "strong-pass-123",
        "phone": "+919876543210", "blood_group": "O+", "age": 29, "gender": "Male",
        "location": "Anekal, Bengaluru Urban", "district": "Bengaluru Urban", "taluk": "Anekal",
        "role": "ROLE_ADMIN", "consent_to_emergency_alerts": False,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["role"] == "ROLE_DONOR"
    assert body["email_delivery"]["delivery_status"] == "DISABLED"
    assert "token" in body and body["token"]
    assert "password" not in body["user"]
    assert body["donor"]["availability_score"] is None
    assert body["donor"]["consent"] == "PENDING"

    conn = connect()
    try:
        row = conn.execute("SELECT password, role FROM users WHERE email = ?", ("new-donor@haemopulse.invalid",)).fetchone()
        assert row["role"] == "ROLE_DONOR"
        assert row["password"].startswith("pbkdf2_sha256$")
        assert row["password"] != "strong-pass-123"
    finally:
        conn.close()

    valid_login = client.post("/api/v1/auth/login", json={"email": "new-donor@haemopulse.invalid", "password": "strong-pass-123"})
    assert valid_login.status_code == 200, valid_login.text
    assert valid_login.json()["user"]["role"] == "ROLE_DONOR"
    assert "password" not in valid_login.json()["user"]
    invalid_login = client.post("/api/v1/auth/login", json={"email": "new-donor@haemopulse.invalid", "password": "wrong-password"})
    assert invalid_login.status_code == 401

    duplicate = client.post("/api/v1/auth/register", json={
        "name": "Regression Donor", "email": "new-donor@haemopulse.invalid", "password": "strong-pass-123",
        "phone": "+919876543210", "blood_group": "O+", "age": 29, "location": "Anekal",
        "district": "Bengaluru Urban", "taluk": "Anekal",
    })
    assert duplicate.status_code == 400

    wrong_taluk = client.post("/api/v1/auth/register", json={
        "name": "Other Donor", "email": "bad-location@haemopulse.invalid", "password": "strong-pass-123",
        "phone": "+919876543210", "blood_group": "O+", "age": 29, "location": "Anekal",
        "district": "Bengaluru Urban", "taluk": "Not a taluk",
    })
    assert wrong_taluk.status_code == 422


def test_donor_profile_is_authenticated_and_own_identity_only():
    registration = client.post("/api/v1/auth/register", json={
        "name": "Profile Owner", "email": "profile-owner@haemopulse.invalid", "password": "strong-pass-456",
        "phone": "+919123456789", "blood_group": "A+", "age": 31, "location": "Anekal",
    })
    assert registration.status_code == 200, registration.text
    token = registration.json()["token"]
    profile = client.get("/api/v1/donors/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200, profile.text
    assert profile.json()["donor"]["email"] == "profile-owner@haemopulse.invalid"
    assert profile.json()["donor"]["availability_score"] is None
    assert client.get("/api/v1/donors/me").status_code == 401
    assert client.get("/api/v1/donors", headers={"Authorization": f"Bearer {DONOR_TOKEN}"}).status_code == 403


def test_availability_score_and_radius_filters_use_actual_coordinates():
    add_donor("DNR-IN", "inside@haemopulse.invalid", score=90, lat=0, lon=0.03)
    add_donor("DNR-OUT", "outside@haemopulse.invalid", score=90, lat=0, lon=0.20)
    add_donor("DNR-NOCOORD", "missing-coord@haemopulse.invalid", score=90, lat=None, lon=None)
    add_donor("DNR-MED", "medium@haemopulse.invalid", score=55, lat=0, lon=0.01)
    add_donor("DNR-LOW", "low-score@haemopulse.invalid", score=20, lat=0, lon=0.02)
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    response = client.get("/api/v1/donors", params={
        "blood_group": "O+", "district": "Bengaluru Urban", "taluk": "Anekal",
        "availability_level": "HIGH", "eligible_only": "true", "radius_km": 5,
        "destination_latitude": 0, "destination_longitude": 0,
    }, headers=headers)
    assert response.status_code == 200, response.text
    ids = {row["donor_id"] for row in response.json()}
    assert "DNR-IN" in ids
    assert "DNR-OUT" not in ids
    assert "DNR-NOCOORD" not in ids
    assert "DNR-MED" not in ids
    assert "DNR-LOW" not in ids
    inside = next(row for row in response.json() if row["donor_id"] == "DNR-IN")
    assert 3.2 < inside["distance_km"] < 3.5
    assert "latitude" not in inside and "longitude" not in inside
    assert inside.get("email") == "inside@haemopulse.invalid"  # Admin directory can manage contact details.

    hospital_results = client.get("/api/v1/donors", params={
        "blood_group": "O+", "district": "Bengaluru Urban", "taluk": "Anekal",
        "eligible_only": "true"
    }, headers={"Authorization": f"Bearer {HOSPITAL_TOKEN}"})
    assert hospital_results.status_code == 200, hospital_results.text
    hospital_donor = next(row for row in hospital_results.json() if row["donor_id"] == "DNR-IN")
    assert "email" not in hospital_donor and "phone" not in hospital_donor

    medium_filter = client.get("/api/v1/donors", params={"blood_group": "O+", "availability_level": "MEDIUM"}, headers=headers)
    low_filter = client.get("/api/v1/donors", params={"blood_group": "O+", "availability_level": "LOW"}, headers=headers)
    assert medium_filter.status_code == 200 and {row["donor_id"] for row in medium_filter.json()} == {"DNR-MED"}
    assert low_filter.status_code == 200 and {row["donor_id"] for row in low_filter.json()} == {"DNR-LOW"}

    missing_coordinates = client.get("/api/v1/donors", params={"radius_km": 5}, headers=headers)
    assert missing_coordinates.status_code == 422
    bad_location = client.get("/api/v1/donors", params={"district": "Made Up District"}, headers=headers)
    assert bad_location.status_code == 422


def test_inventory_add_is_persisted_and_idempotent():
    conn = connect()
    try:
        conn.execute("INSERT INTO blood_inventory (blood_group,component_type,units_available,expiry_date,status) VALUES ('O+','Whole Blood',4,'2027-12-31','LOW_STOCK')")
        conn.commit()
    finally:
        conn.close()
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    payload = {"blood_group": "O+", "units_available": 3, "component_type": "Whole Blood", "idempotency_key": "inventory-add-test-0001"}
    first = client.post("/api/v1/inventory", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["persisted"] is True
    assert first.json()["item"]["units_available"] == 7
    second = client.post("/api/v1/inventory", json=payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["item"]["units_available"] == 7
    invalid_qty = client.post("/api/v1/inventory", json={**payload, "units_available": -1, "idempotency_key": "inventory-add-test-0002"}, headers=headers)
    assert invalid_qty.status_code == 422
    invalid_unit = client.post("/api/v1/inventory", json={**payload, "component_type": "Platelets", "idempotency_key": "inventory-add-test-0003"}, headers=headers)
    assert invalid_unit.status_code == 422
    assert client.get("/api/v1/inventory").status_code == 401
    conn = connect()
    try:
        row = conn.execute("SELECT units_available FROM blood_inventory WHERE blood_group = 'O+'").fetchone()
        assert row["units_available"] == 7
    finally:
        conn.close()


def test_emergency_alert_requires_role_and_persists_without_sending_real_email():
    donor_row_id = add_donor("DNR-ALERT", "alert-donor@haemopulse.invalid", score=88, lat=12, lon=77, consent="OPTED_IN")
    linked_user_id, _ = create_user("alert-donor@haemopulse.invalid", "ROLE_DONOR", verified=1)
    conn = connect()
    conn.execute("UPDATE donors SET user_id = ? WHERE id = ?", (linked_user_id, donor_row_id))
    conn.commit()
    try:
        cursor = conn.execute("""INSERT INTO blood_requests
          (hospital_name,hospital_address,contact_phone,blood_group,units_needed,urgency_level,patient_name,status,request_date,created_by_user_id,destination_latitude,destination_longitude)
          VALUES ('Test Hospital','Test Address','+911234567890','O+',1,'EMERGENCY','Test Ward','PENDING',datetime('now'),?,12,77)""", (HOSPITAL_ID,))
        conn.commit(); request_id = cursor.lastrowid
        donor_key = conn.execute("SELECT donor_id FROM donors WHERE id = ?", (donor_row_id,)).fetchone()["donor_id"]
    finally:
        conn.close()
    payload = {"donor_id": donor_key, "blood_group": "O+", "request_id": request_id, "idempotency_key": "emergency-alert-test-0001"}
    assert client.post("/api/v1/donors/send-email-alert", json=payload).status_code == 401
    response = client.post("/api/v1/donors/send-email-alert", json=payload, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] is True and body["persisted"] is True
    assert body["delivery_status"] == "PENDING" and body["delivered"] is False and body["queued"] is True
    duplicate = client.post("/api/v1/donors/send-email-alert", json=payload, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
    conn = connect()
    try:
        rows = conn.execute("SELECT id FROM emergency_alerts WHERE idempotency_key = ?", (payload["idempotency_key"],)).fetchall()
        outbox = conn.execute("SELECT id, status FROM notification_outbox WHERE event_key = ?", (f"manual-alert:{payload['idempotency_key']}",)).fetchall()
        assert len(rows) == 1 and len(outbox) == 1 and outbox[0]["status"] == "PENDING"
    finally:
        conn.close()



def test_hospital_request_persists_valid_destination_coordinates():
    payload = {
        "hospital_name": "Coordinates Test Hospital", "hospital_address": "10 Test Road, Bengaluru",
        "contact_phone": "+911234567890", "blood_group": "O+", "units_needed": 2,
        "urgency_level": "EMERGENCY", "patient_name": "Test Ward",
        "destination_latitude": 12.9716, "destination_longitude": 77.5946,
    }
    headers = {"Authorization": f"Bearer {HOSPITAL_TOKEN}"}
    response = client.post("/api/v1/requests", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"]
    assert saved["destination_latitude"] == 12.9716
    assert saved["destination_longitude"] == 77.5946
    invalid = client.post("/api/v1/requests", json={**payload, "destination_longitude": None}, headers=headers)
    assert invalid.status_code == 422

    conn = connect()
    try:
        row = conn.execute("SELECT destination_latitude, destination_longitude FROM blood_requests WHERE id = ?", (saved["id"],)).fetchone()
        assert row["destination_latitude"] == 12.9716 and row["destination_longitude"] == 77.5946
    finally:
        conn.close()


def test_appointment_status_update_is_role_protected_and_persisted():
    conn = connect()
    try:
        cursor = conn.execute("INSERT INTO appointments (donor_id,donor_name,donor_email,blood_group,appointment_date,time_slot,status) VALUES ('DNR-1','Test Donor','appt@haemopulse.invalid','O+','2027-01-10','Morning','SCHEDULED')")
        conn.commit(); appointment_id = cursor.lastrowid
    finally:
        conn.close()
    denied = client.put(f"/api/v1/appointments/{appointment_id}/status?status=COMPLETED", headers={"Authorization": f"Bearer {DONOR_TOKEN}"})
    assert denied.status_code == 403
    ok = client.put(f"/api/v1/appointments/{appointment_id}/status?status=COMPLETED", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert ok.status_code == 200 and ok.json()["status"] == "COMPLETED"
    conn = connect()
    try:
        row = conn.execute("SELECT status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        assert row["status"] == "COMPLETED"
    finally:
        conn.close()


def test_donor_appointments_are_scoped_to_authenticated_donor():
    own_email = "appointments-own@haemopulse.invalid"
    other_email = "appointments-other@haemopulse.invalid"
    own_user_id, own_token = create_user(own_email, "ROLE_DONOR")
    other_user_id, _ = create_user(other_email, "ROLE_DONOR")
    add_donor("DNR-APPOINTMENT-OWN", own_email, score=None)
    add_donor("DNR-APPOINTMENT-OTHER", other_email, score=None, blood_group="A+")
    conn = connect()
    try:
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (own_user_id, "DNR-APPOINTMENT-OWN"))
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (other_user_id, "DNR-APPOINTMENT-OTHER"))
        own_appointment = conn.execute(
            "INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status) VALUES (?,?,?,?,?,?,?,?)",
            ("DNR-APPOINTMENT-OWN", "Own Donor", own_email, "O+", "2026-10-25", "Evening (4 PM - 8 PM)", "Own Center", "SCHEDULED"),
        ).lastrowid
        conn.execute(
            "INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status) VALUES (?,?,?,?,?,?,?,?)",
            ("DNR-APPOINTMENT-OTHER", "Other Donor", other_email, "A+", "2026-10-24", "Morning (8 AM - 12 PM)", "Other Center", "SCHEDULED"),
        )
        conn.commit()
    finally:
        conn.close()

    headers = {"Authorization": f"Bearer {own_token}"}
    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["id"] for row in rows] == [own_appointment]
    assert all(row["donor_email"].lower() == own_email for row in rows)

    profile = client.get("/api/v1/donors/me", headers=headers)
    assert profile.status_code == 200, profile.text
    assert [row["id"] for row in profile.json()["appointments"]] == [own_appointment]


def test_personalized_score_requires_three_verified_donations_and_model_inputs():
    email = "score-threshold@haemopulse.invalid"
    user_id, token = create_user(email, "ROLE_DONOR")
    add_donor("DNR-SCORE-THRESHOLD", email, score=99)
    headers = {"Authorization": f"Bearer {token}"}
    missing_history = client.get("/api/v1/donors/me/availability-score", headers=headers)
    assert missing_history.status_code == 200
    assert missing_history.json()["reason"] == "MISSING_DONATION_HISTORY"
    assert missing_history.json()["completed_donations"] is None
    conn = connect()
    try:
        # Scheduled appointments are not donation records and must not count.
        conn.execute("INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, status) VALUES (?,?,?,?,?,?,?)", ("DNR-SCORE-THRESHOLD", "Score Donor", email, "O+", "2026-12-01", "Morning", "SCHEDULED"))
        for i in range(2):
            conn.execute("INSERT INTO donations (donation_code, donor_email, donor_name, blood_group, units, donation_date, center_name, status) VALUES (?,?,?,?,?,?,?,?)", (f"SCORE-DON-{i}", email, "Score Donor", "O+", 1, f"2025-0{i+1}-01", "Test Center", "Verified"))
        conn.commit()
    finally:
        conn.close()
    response = client.get("/api/v1/donors/me/availability-score", headers=headers)
    assert response.status_code == 200
    assert response.json()["eligible"] is False
    assert response.json()["completed_donations"] == 2
    assert "availability_score" not in response.json()
    conn = connect()
    try:
        conn.execute("INSERT INTO donations (donation_code, donor_email, donor_name, blood_group, units, donation_date, center_name, status) VALUES (?,?,?,?,?,?,?,?)", ("SCORE-DON-3", email, "Score Donor", "O+", 1, "2025-03-01", "Test Center", "Verified"))
        conn.commit()
    finally:
        conn.close()
    response = client.get("/api/v1/donors/me/availability-score", headers=headers)
    assert response.status_code == 200
    assert response.json()["eligible"] is False
    assert response.json()["reason"] == "MISSING_MODEL_INPUTS"
    assert "response_time_hrs" in response.json()["missing_fields"]


def test_emergency_response_is_persisted_per_donor_and_duplicate_is_rejected():
    email = "request-responder@haemopulse.invalid"
    user_id, token = create_user(email, "ROLE_DONOR")
    add_donor("DNR-RESPONDER", email, score=None, blood_group="O+")
    conn = connect()
    try:
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (user_id, "DNR-RESPONDER"))
        cursor = conn.execute("INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)", ("Test Hospital", "O+", 2, "EMERGENCY", "Test Patient", "PENDING", "2026-10-22"))
        request_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    headers = {"Authorization": f"Bearer {token}"}
    unauthenticated = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"})
    assert unauthenticated.status_code == 401
    accepted = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"}, headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["response"] == "ACCEPTED"
    duplicate = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "REJECT"}, headers=headers)
    assert duplicate.status_code == 409
    conn = connect()
    try:
        rows = conn.execute("SELECT donor_id, response FROM emergency_request_responses WHERE request_id = ?", (request_id,)).fetchall()
        assert len(rows) == 1 and rows[0]["donor_id"] == "DNR-RESPONDER" and rows[0]["response"] == "ACCEPTED"
        # One donor response must not mutate the global request status.
        status = conn.execute("SELECT status FROM blood_requests WHERE id = ?", (request_id,)).fetchone()["status"]
        assert status == "PENDING"
        reject_cursor = conn.execute("INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)", ("Second Test Hospital", "O+", 1, "HIGH", "Second Test Patient", "PENDING", "2026-10-22"))
        reject_request_id = reject_cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    rejected = client.post(f"/api/v1/requests/{reject_request_id}/response", json={"action": "REJECT"}, headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["response"] == "REJECTED"
    conn = connect()
    try:
        saved = conn.execute("SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?", (reject_request_id, "DNR-RESPONDER")).fetchone()
        assert saved["response"] == "REJECTED"
    finally:
        conn.close()


def test_emergency_response_requires_verified_donor_and_open_request():
    email = "unverified-responder@haemopulse.invalid"
    user_id, token = create_user(email, "ROLE_DONOR", verified=0)
    add_donor("DNR-UNVERIFIED-RESPONDER", email, score=None, blood_group="O+")
    conn = connect()
    try:
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (user_id, "DNR-UNVERIFIED-RESPONDER"))
        cursor = conn.execute(
            "INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)",
            ("Verification Test Hospital", "O+", 1, "EMERGENCY", "Private Test Reference", "PENDING", "2026-10-22"),
        )
        request_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    headers = {"Authorization": f"Bearer {token}"}
    blocked = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"}, headers=headers)
    assert blocked.status_code == 403
    assert "Verify your email" in blocked.json()["detail"]

    conn = connect()
    try:
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
        conn.execute("UPDATE blood_requests SET status = 'CANCELLED' WHERE id = ?", (request_id,))
        conn.commit()
    finally:
        conn.close()
    closed = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"}, headers=headers)
    assert closed.status_code == 409
    conn = connect()
    try:
        persisted = conn.execute(
            "SELECT COUNT(*) FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (request_id, "DNR-UNVERIFIED-RESPONDER"),
        ).fetchone()[0]
        assert persisted == 0
    finally:
        conn.close()


def test_donor_role_alias_receives_only_matching_emergency_requests():
    email = "role-alias-donor@haemopulse.invalid"
    user_id, token = create_user(email, "DONOR")
    add_donor("DNR-ROLE-ALIAS", email, score=None, blood_group="O+")
    conn = connect()
    try:
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (user_id, "DNR-ROLE-ALIAS"))
        conn.execute(
            "INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)",
            ("Compatible Hospital", "O+", 1, "EMERGENCY", "Reference A", "PENDING", "2026-10-22"),
        )
        conn.execute(
            "INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)",
            ("Other Blood Group Hospital", "A+", 1, "EMERGENCY", "Reference B", "PENDING", "2026-10-22"),
        )
        conn.commit()
    finally:
        conn.close()
    response = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert any(row["hospital_name"] == "Compatible Hospital" for row in rows)
    assert not any(row["hospital_name"] == "Other Blood Group Hospital" for row in rows)
    assert all(row["blood_group"] == "O+" for row in rows)



def test_donor_with_nonmatching_blood_group_cannot_respond():
    donor_email = "wrong-blood-group@haemopulse.invalid"
    donor_user_id, donor_token = create_user(donor_email, "ROLE_DONOR")
    add_donor("DNR-WRONG-BLOOD", donor_email, score=None, blood_group="A+")
    conn = connect()
    try:
        conn.execute("UPDATE donors SET user_id = ? WHERE donor_id = ?", (donor_user_id, "DNR-WRONG-BLOOD"))
        cursor = conn.execute(
            "INSERT INTO blood_requests (hospital_name, blood_group, units_needed, urgency_level, patient_name, status, request_date) VALUES (?,?,?,?,?,?,?)",
            ("O Positive Test Hospital", "O+", 1, "EMERGENCY", "Reference Only", "PENDING", "2026-10-22"),
        )
        request_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    response = client.post(
        f"/api/v1/requests/{request_id}/response",
        json={"action": "ACCEPT"},
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert response.status_code == 403
    conn = connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM emergency_request_responses WHERE request_id = ?",
            (request_id,),
        ).fetchone()[0]
        assert count == 0
    finally:
        conn.close()



def _linked_donor(donor_id: str, email: str, *, verified: int = 1, status: str = "ACTIVE", consent: str = "OPTED_IN", blood_group: str = "O+"):
    donor_row_id = add_donor(donor_id, email, consent=consent, blood_group=blood_group)
    user_id, token = create_user(email, "ROLE_DONOR", verified=verified)
    conn = connect()
    try:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
        conn.execute("UPDATE donors SET user_id = ? WHERE id = ?", (user_id, donor_row_id))
        conn.commit()
    finally:
        conn.close()
    return donor_row_id, user_id, token


def _insert_request(*, urgency="EMERGENCY", hospital_user_id=None, assigned_admin_user_id=None, creator_id=None):
    conn = connect()
    try:
        cursor = conn.execute("""
            INSERT INTO blood_requests
            (hospital_name,hospital_address,contact_phone,blood_group,units_needed,urgency_level,patient_name,status,request_date,created_by_user_id,hospital_user_id,assigned_admin_user_id)
            VALUES ('Explicit Test Hospital','10 Example Road','+911234567890','O+',2,?,'Private Patient Reference','PENDING',datetime('now'),?,?,?)
        """, (urgency, creator_id or HOSPITAL_ID, hospital_user_id, assigned_admin_user_id))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _clear_outbox():
    conn = connect()
    try:
        conn.execute("DELETE FROM notification_provider_events")
        conn.execute("DELETE FROM notification_outbox")
        conn.commit()
    finally:
        conn.close()


def test_emergency_request_creation_enqueues_only_eligible_linked_verified_opted_in_donors():
    _clear_outbox()
    _, good_user_id, _ = _linked_donor("DNR-EMAIL-GOOD", "outbox-good@haemopulse.invalid", blood_group="AB-")
    _, unverified_user_id, _ = _linked_donor("DNR-EMAIL-UNVERIFIED", "outbox-unverified@haemopulse.invalid", verified=0, blood_group="AB-")
    _, inactive_user_id, _ = _linked_donor("DNR-EMAIL-INACTIVE", "outbox-inactive@haemopulse.invalid", status="SUSPENDED", blood_group="AB-")
    _linked_donor("DNR-EMAIL-CONSENT", "outbox-consent@haemopulse.invalid", consent="PENDING", blood_group="AB-")
    add_donor("DNR-EMAIL-UNLINKED", "outbox-unlinked@haemopulse.invalid", consent="OPTED_IN", blood_group="AB-")

    payload = {
        "hospital_name": "Explicit Test Hospital", "hospital_address": "10 Example Road", "contact_phone": "+911234567890",
        "blood_group": "AB-", "units_needed": 2, "urgency_level": "EMERGENCY", "patient_name": "Sensitive patient data",
        "destination_latitude": None, "destination_longitude": None,
    }
    response = client.post("/api/v1/requests", json=payload, headers={"Authorization": f"Bearer {HOSPITAL_TOKEN}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["notification_summary"]["eligible_donors"] == 1
    assert body["notification_summary"]["status"] == "QUEUED"
    assert body["hospital_user_id"] == HOSPITAL_ID
    conn = connect()
    try:
        events = conn.execute("SELECT * FROM notification_outbox WHERE request_id = ?", (body["id"],)).fetchall()
        assert len(events) == 1
        assert events[0]["recipient_user_id"] == good_user_id
        assert events[0]["recipient_email"] == "outbox-good@haemopulse.invalid"
        assert events[0]["status"] == "PENDING"
        assert "Sensitive patient data" not in str(dict(events[0]))
    finally:
        conn.close()


def test_non_emergency_request_does_not_enqueue_automatic_donor_fanout():
    _clear_outbox()
    _linked_donor("DNR-NORMAL-NOTIFY", "normal-notify@haemopulse.invalid")
    payload = {"hospital_name": "Regular Hospital", "hospital_address": "10 Example Road", "blood_group": "O+",
               "units_needed": 1, "urgency_level": "HIGH", "patient_name": "Ward reference"}
    response = client.post("/api/v1/requests", json=payload, headers={"Authorization": f"Bearer {HOSPITAL_TOKEN}"})
    assert response.status_code == 200, response.text
    assert response.json()["notification_summary"]["status"] == "NOT_APPLICABLE"
    conn = connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE request_id=?", (response.json()["id"],)).fetchone()[0] == 0
    finally:
        conn.close()


def test_admin_emergency_request_requires_explicit_active_hospital_assignment():
    payload = {"hospital_name": "Admin Test Hospital", "hospital_address": "10 Example Road", "blood_group": "O+",
               "units_needed": 1, "urgency_level": "EMERGENCY", "patient_name": "Ward reference"}
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    missing = client.post("/api/v1/requests", json=payload, headers=headers)
    assert missing.status_code == 422
    invalid = client.post("/api/v1/requests", json={**payload, "hospital_user_id": ADMIN_ID}, headers=headers)
    assert invalid.status_code == 422
    valid = client.post("/api/v1/requests", json={**payload, "hospital_user_id": HOSPITAL_ID, "assigned_admin_user_id": ADMIN_ID}, headers=headers)
    assert valid.status_code == 200, valid.text
    assert valid.json()["hospital_user_id"] == HOSPITAL_ID
    assert valid.json()["assigned_admin_user_id"] == ADMIN_ID


def test_acceptance_routes_only_to_explicit_hospital_and_assigned_admin_and_rejection_is_silent():
    _clear_outbox()
    donor_row_id, donor_user_id, donor_token = _linked_donor("DNR-ROUTED-ACCEPT", "routed-accept@haemopulse.invalid")
    other_hospital_id, _ = create_user("unrelated-hospital@haemopulse.invalid", "ROLE_HOSPITAL")
    other_admin_id, _ = create_user("unrelated-admin@haemopulse.invalid", "ROLE_ADMIN")
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    response = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"},
                           headers={"Authorization": f"Bearer {donor_token}"})
    assert response.status_code == 200, response.text
    assert response.json()["response"] == "ACCEPTED"
    conn = connect()
    try:
        rows = conn.execute("SELECT event_type,recipient_user_id,status FROM notification_outbox WHERE request_id=?", (request_id,)).fetchall()
        mapping = {row["event_type"]: (row["recipient_user_id"], row["status"]) for row in rows}
        assert mapping["DONOR_ACCEPTANCE_HOSPITAL"] == (HOSPITAL_ID, "PENDING")
        assert mapping["DONOR_ACCEPTANCE_ADMIN"] == (ADMIN_ID, "PENDING")
        assert all(row["recipient_user_id"] not in {other_hospital_id, other_admin_id} for row in rows)
        assert conn.execute("SELECT response FROM emergency_request_responses WHERE request_id=?", (request_id,)).fetchone()[0] == "ACCEPTED"
    finally:
        conn.close()

    # A different donor rejecting a request must not generate any notification events.
    _clear_outbox()
    _, _, reject_token = _linked_donor("DNR-ROUTED-REJECT", "routed-reject@haemopulse.invalid")
    rejected_request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    rejected = client.post(f"/api/v1/requests/{rejected_request_id}/response", json={"action": "REJECT"},
                           headers={"Authorization": f"Bearer {reject_token}"})
    assert rejected.status_code == 200 and rejected.json()["response"] == "REJECTED"
    conn = connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE request_id=?", (rejected_request_id,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_acceptance_remains_persisted_when_recipient_assignments_are_missing():
    _clear_outbox()
    _, _, donor_token = _linked_donor("DNR-MISSING-ASSIGN", "missing-assignment@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=None, assigned_admin_user_id=None)
    response = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"},
                           headers={"Authorization": f"Bearer {donor_token}"})
    assert response.status_code == 200, response.text
    assert response.json()["notifications_queued"] == 0
    assert response.json()["notifications_needing_review"] == 2
    conn = connect()
    try:
        assert conn.execute("SELECT response FROM emergency_request_responses WHERE request_id=?", (request_id,)).fetchone()[0] == "ACCEPTED"
        statuses = [r[0] for r in conn.execute("SELECT status FROM notification_outbox WHERE request_id=?", (request_id,)).fetchall()]
        assert statuses == ["NEEDS_REVIEW", "NEEDS_REVIEW"]
        assert all(r[0] is None for r in conn.execute("SELECT recipient_email FROM notification_outbox WHERE request_id=?", (request_id,)).fetchall())
    finally:
        conn.close()


def test_request_and_acceptance_outbox_events_roll_back_atomically(monkeypatch):
    _clear_outbox()
    payload = {"hospital_name": "Atomic Hospital", "hospital_address": "10 Example Road", "blood_group": "O+",
               "units_needed": 1, "urgency_level": "EMERGENCY", "patient_name": "Ward reference"}
    before = None
    conn = connect()
    try:
        before = conn.execute("SELECT COUNT(*) FROM blood_requests").fetchone()[0]
    finally:
        conn.close()
    def fail_fanout(*args, **kwargs):
        raise sqlite3.IntegrityError("simulated outbox failure")
    monkeypatch.setattr(server, "_enqueue_emergency_request_notifications", fail_fanout)
    response = client.post("/api/v1/requests", json=payload, headers={"Authorization": f"Bearer {HOSPITAL_TOKEN}"})
    assert response.status_code == 409
    conn = connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM blood_requests").fetchone()[0] == before
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox").fetchone()[0] == 0
    finally:
        conn.close()
    monkeypatch.undo()

    _clear_outbox()
    _, _, donor_token = _linked_donor("DNR-ATOMIC-ACCEPT", "atomic-accept@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    monkeypatch.setattr(server, "_enqueue_acceptance_notifications", fail_fanout)
    response = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"},
                           headers={"Authorization": f"Bearer {donor_token}"})
    assert response.status_code == 409
    conn = connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM emergency_request_responses WHERE request_id=?", (request_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE request_id=?", (request_id,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_worker_submission_and_retry_limit_are_persistent_and_bounded(monkeypatch):
    _clear_outbox()
    _, donor_user_id, _ = _linked_donor("DNR-WORKER-RETRY", "worker-retry@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    conn = connect()
    try:
        conn.execute("""INSERT INTO notification_outbox(event_key,event_type,request_id,donor_id,recipient_user_id,recipient_email,status,attempt_count,next_retry_at,created_at,updated_at)
            VALUES ('worker-retry-event','DONOR_EMERGENCY_REQUEST',?,?,?,?,'PENDING',5,datetime('now'),'2026-10-23T00:00:00+00:00','2026-10-23T00:00:00+00:00')""",
            (request_id, "DNR-WORKER-RETRY", donor_user_id, "worker-retry@haemopulse.invalid"))
        conn.commit()
        event_id = conn.execute("SELECT id FROM notification_outbox WHERE event_key='worker-retry-event'").fetchone()[0]
    finally:
        conn.close()

    monkeypatch.setattr(server, "EXTERNAL_MESSAGES_ENABLED", True)
    called = []
    def fake_sender(**kwargs):
        called.append(kwargs)
        return server.SubmissionResult("RETRY", error_code="HTTP_429", http_status=429)
    assert server.process_notification_batch(sender=fake_sender, limit=1) == 1
    assert len(called) == 1
    conn = connect()
    try:
        row = conn.execute("SELECT status,attempt_count,last_error_code,claimed_by,provider_message_id FROM notification_outbox WHERE id=?", (event_id,)).fetchone()
        assert row["status"] == "FAILED" and row["attempt_count"] == server.NOTIFICATION_MAX_ATTEMPTS
        assert row["last_error_code"] == "HTTP_429" and row["claimed_by"] is None and row["provider_message_id"] is None
    finally:
        conn.close()
    retried = client.post(f"/api/v1/notifications/{event_id}/retry", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert retried.status_code == 200, retried.text
    conn = connect()
    try:
        row = conn.execute("SELECT status,attempt_count FROM notification_outbox WHERE id=?", (event_id,)).fetchone()
        assert row["status"] == "PENDING" and row["attempt_count"] == 0
    finally:
        conn.close()
    monkeypatch.setattr(server, "EXTERNAL_MESSAGES_ENABLED", False)


def test_expired_worker_lease_requires_review_not_a_blind_duplicate_send():
    _clear_outbox()
    conn = connect()
    try:
        conn.execute("""INSERT INTO notification_outbox(event_key,event_type,status,claimed_by,claimed_at,claim_expires_at,created_at,updated_at)
            VALUES ('stale-lease-test','DONOR_EMERGENCY_REQUEST','PROCESSING','dead-worker','2026-10-23T00:00:00+00:00','2026-10-23T00:00:01+00:00','2026-10-23T00:00:00+00:00','2026-10-23T00:00:00+00:00')""")
        conn.commit()
    finally:
        conn.close()
    claimed = server._claim_next_notification()
    assert claimed is None
    conn = connect()
    try:
        row = conn.execute("SELECT status,last_error_code,claimed_by FROM notification_outbox WHERE event_key='stale-lease-test'").fetchone()
        assert row["status"] == "NEEDS_REVIEW"
        assert row["last_error_code"] == "STALE_CLAIM_REQUIRES_RECONCILIATION"
        assert row["claimed_by"] is None
    finally:
        conn.close()


def test_brevo_webhook_auth_deduplication_and_out_of_order_events(monkeypatch):
    _clear_outbox()
    monkeypatch.setenv("BREVO_WEBHOOK_BEARER_TOKEN", "test-webhook-bearer-token")
    conn = connect()
    try:
        conn.execute("""INSERT INTO notification_outbox(event_key,event_type,status,provider_message_id,last_provider_event_at,created_at,updated_at)
            VALUES ('webhook-msg','DONOR_EMERGENCY_REQUEST','SUBMITTED','<brevo-test-message>','2026-10-23T10:00:00+00:00','2026-10-23T09:00:00+00:00','2026-10-23T10:00:00+00:00')""")
        conn.commit()
    finally:
        conn.close()
    headers = {"Authorization": "Bearer test-webhook-bearer-token"}
    recent_epoch = int(datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc).timestamp())
    delivered = {"event": "delivered", "message-id": "<brevo-test-message>", "ts_event": recent_epoch, "id": 101}
    unauthorized = client.post("/api/v1/webhooks/brevo/transactional", json=delivered)
    assert unauthorized.status_code == 401
    first = client.post("/api/v1/webhooks/brevo/transactional", json=delivered, headers=headers)
    assert first.status_code == 200 and first.json()["matched"] is True
    duplicate = client.post("/api/v1/webhooks/brevo/transactional", json=delivered, headers=headers)
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
    older_epoch = int(datetime(2026, 10, 23, 9, 30, tzinfo=timezone.utc).timestamp())
    older = client.post("/api/v1/webhooks/brevo/transactional", json={"event": "sent", "message-id": "<brevo-test-message>", "ts_event": older_epoch, "id": 102}, headers=headers)
    assert older.status_code == 200
    # Even a later-arriving bounce or timestamp-less event must not downgrade DELIVERED.
    newer_bounce_epoch = int(datetime(2026, 10, 23, 11, 30, tzinfo=timezone.utc).timestamp())
    newer_bounce = client.post("/api/v1/webhooks/brevo/transactional", json={"event": "hardBounce", "message-id": "<brevo-test-message>", "ts_event": newer_bounce_epoch, "id": 103}, headers=headers)
    assert newer_bounce.status_code == 200
    no_timestamp = client.post("/api/v1/webhooks/brevo/transactional", json={"event": "sent", "message-id": "<brevo-test-message>", "id": 104}, headers=headers)
    assert no_timestamp.status_code == 200
    conn = connect()
    try:
        row = conn.execute("SELECT status,delivered_at FROM notification_outbox WHERE event_key='webhook-msg'").fetchone()
        events_count = conn.execute("SELECT COUNT(*) FROM notification_provider_events WHERE provider_message_id='<brevo-test-message>'").fetchone()[0]
        assert row["status"] == "DELIVERED" and row["delivered_at"] is not None
        assert events_count == 4  # Duplicate was idempotent; distinct out-of-order events were recorded without status regression.
    finally:
        conn.close()


def test_notification_status_and_retry_are_role_scoped():
    _clear_outbox()
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    conn = connect()
    try:
        conn.execute("""INSERT INTO notification_outbox(event_key,event_type,request_id,status,created_at,updated_at)
            VALUES ('scope-status','DONOR_EMERGENCY_REQUEST',?,'FAILED','2026-10-23T00:00:00+00:00','2026-10-23T00:00:00+00:00')""", (request_id,))
        conn.commit()
    finally:
        conn.close()
    # Another hospital account cannot inspect this request or retry its events.
    other_hospital_id, other_hospital_token = create_user("scope-other-hospital@haemopulse.invalid", "ROLE_HOSPITAL")
    allowed = client.get(f"/api/v1/notifications/requests/{request_id}", headers={"Authorization": f"Bearer {HOSPITAL_TOKEN}"})
    denied = client.get(f"/api/v1/notifications/requests/{request_id}", headers={"Authorization": f"Bearer {other_hospital_token}"})
    assert allowed.status_code == 200 and allowed.json()["counts"]["FAILED"] == 1
    assert denied.status_code == 403


def test_brevo_adapter_success_uses_verified_sender_and_returns_message_id(monkeypatch):
    import email_service

    monkeypatch.setattr(email_service, "external_messages_enabled", lambda: True)
    monkeypatch.setenv("BREVO_API_KEY", "test-only-api-key")
    monkeypatch.setenv("MAIL_FROM", "HaemoPulse Verified <sender@example.invalid>")
    monkeypatch.setenv("MAIL_FROM_NAME", "HaemoPulse Test")

    class FakeResponse:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, n=-1): return b'{"messageId":"<mock-provider-id>"}'

    captured = {}
    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()
    monkeypatch.setattr(email_service.urllib.request, "urlopen", fake_urlopen)
    result = email_service.send_transactional_email(
        recipient_email="recipient@example.invalid", recipient_name="Donor", subject="Emergency #123",
        text_content="safe text", html_content="<p>safe</p>", timeout_seconds=7,
    )
    assert result.status == "SUBMITTED" and result.provider_message_id == "<mock-provider-id>"
    assert captured["timeout"] == 7
    import json
    payload = json.loads(captured["request"].data.decode())
    assert payload["sender"] == {"email": "sender@example.invalid", "name": "HaemoPulse Test"}
    assert captured["request"].get_header("Api-key") == "test-only-api-key"


def test_brevo_adapter_classifies_quota_permanent_error_and_ambiguous_timeout(monkeypatch):
    import io
    import urllib.error
    import email_service

    monkeypatch.setattr(email_service, "external_messages_enabled", lambda: True)
    monkeypatch.setenv("BREVO_API_KEY", "test-only-api-key")
    monkeypatch.setenv("MAIL_FROM", "sender@example.invalid")

    def send(**kwargs):
        return email_service.send_transactional_email(recipient_email="r@example.invalid", recipient_name="R",
            subject="s", text_content="t", html_content="h", **kwargs)

    monkeypatch.setattr(email_service.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(
        urllib.error.HTTPError("https://api.brevo.com", 429, "quota", {}, io.BytesIO(b"private response"))))
    assert send(timeout_seconds=3).status == "RETRY"
    monkeypatch.setattr(email_service.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(
        urllib.error.HTTPError("https://api.brevo.com", 429, "quota", {"Retry-After": "3600"}, io.BytesIO(b"private response"))))
    assert send(timeout_seconds=3).retry_after_seconds == 3600
    monkeypatch.setattr(email_service.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(
        urllib.error.HTTPError("https://api.brevo.com", 401, "unauthorized", {}, io.BytesIO(b"secret"))))
    permanent = send(timeout_seconds=3)
    assert permanent.status == "FAILED" and permanent.error_code == "HTTP_401"
    monkeypatch.setattr(email_service.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("ambiguous")))
    ambiguous = send(timeout_seconds=3)
    assert ambiguous.status == "NEEDS_REVIEW" and ambiguous.error_code == "AMBIGUOUS_TIMEOUT"


def test_brevo_adapter_missing_configuration_does_not_attempt_external_call(monkeypatch):
    import email_service
    monkeypatch.setattr(email_service, "external_messages_enabled", lambda: True)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    result = email_service.send_transactional_email(recipient_email="r@example.invalid", recipient_name="R",
        subject="s", text_content="t", html_content="h")
    assert result.status == "FAILED" and result.error_code == "PROVIDER_NOT_CONFIGURED"


def test_donor_template_escapes_html_and_excludes_patient_information_and_ml_claims():
    from email_service import render_donor_emergency_email
    subject, text_body, html_body = render_donor_emergency_email({
        "id": 42, "blood_group": "O+", "urgency_level": "EMERGENCY", "units_needed": 3,
        "hospital_name": "Hospital <script>alert(1)</script>", "hospital_address": "10 <b>Main</b>",
        "patient_name": "Sensitive Patient 123",
    }, "Donor <Admin>")
    combined = subject + text_body + html_body
    assert "Sensitive Patient 123" not in combined
    assert "Machine Learning" not in combined and "high-priority donor" not in combined
    assert "&lt;script&gt;" in html_body and "&lt;Admin&gt;" in html_body
    assert "CRLF" not in subject


def test_manual_alert_and_request_acceptance_events_are_idempotent_at_database_level():
    _clear_outbox()
    donor_id, donor_user_id, donor_token = _linked_donor("DNR-IDEMPOTENT-ACCEPT", "idempotent-accept@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    headers = {"Authorization": f"Bearer {donor_token}"}
    first = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"}, headers=headers)
    duplicate = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"}, headers=headers)
    assert first.status_code == 200 and duplicate.status_code == 409
    conn = connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE request_id=? AND event_type LIKE 'DONOR_ACCEPTANCE_%'", (request_id,)).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM notification_outbox WHERE event_key LIKE ?", (f"acceptance:{request_id}:donor:%",)).fetchone()[0] == 2
    finally:
        conn.close()


def test_assignment_repair_requeues_only_missing_recipient_events():
    _clear_outbox()
    _, _, donor_token = _linked_donor("DNR-REPAIR-ASSIGN", "repair-assignment@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=None, assigned_admin_user_id=None)
    accepted = client.post(f"/api/v1/requests/{request_id}/response", json={"action": "ACCEPT"},
                           headers={"Authorization": f"Bearer {donor_token}"})
    assert accepted.status_code == 200 and accepted.json()["notifications_needing_review"] == 2
    repaired = client.put(f"/api/v1/requests/{request_id}/notification-assignments",
                          json={"hospital_user_id": HOSPITAL_ID, "assigned_admin_user_id": ADMIN_ID},
                          headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert repaired.status_code == 200, repaired.text
    conn = connect()
    try:
        statuses = {(r["event_type"], r["status"], r["recipient_user_id"]) for r in conn.execute(
            "SELECT event_type,status,recipient_user_id FROM notification_outbox WHERE request_id=?", (request_id,)).fetchall()}
        assert ("DONOR_ACCEPTANCE_HOSPITAL", "PENDING", HOSPITAL_ID) in statuses
        assert ("DONOR_ACCEPTANCE_ADMIN", "PENDING", ADMIN_ID) in statuses
        assert any(status == "FAILED" and recipient is None for _, status, recipient in statuses)
    finally:
        conn.close()


def test_two_workers_cannot_claim_the_same_notification(monkeypatch):
    import concurrent.futures
    _clear_outbox()
    _, donor_user_id, _ = _linked_donor("DNR-CONCURRENT-CLAIM", "concurrent-claim@haemopulse.invalid")
    request_id = _insert_request(hospital_user_id=HOSPITAL_ID, assigned_admin_user_id=ADMIN_ID)
    conn = connect()
    try:
        conn.execute("""INSERT INTO notification_outbox(event_key,event_type,request_id,donor_id,recipient_user_id,recipient_email,status,next_retry_at,created_at,updated_at)
            VALUES ('concurrent-claim','DONOR_EMERGENCY_REQUEST',?,?,?,?,'PENDING',datetime('now'),'2026-10-23T00:00:00+00:00','2026-10-23T00:00:00+00:00')""",
            (request_id, "DNR-CONCURRENT-CLAIM", donor_user_id, "concurrent-claim@haemopulse.invalid"))
        conn.commit()
    finally:
        conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: server._claim_next_notification(), range(2)))
    claimed = [row for row in results if row is not None and row["event_key"] == "concurrent-claim"]
    assert len(claimed) == 1
    conn = connect()
    try:
        row = conn.execute("SELECT status,attempt_count FROM notification_outbox WHERE event_key='concurrent-claim'").fetchone()
        assert row["status"] == "PROCESSING" and row["attempt_count"] == 1
    finally:
        conn.close()
