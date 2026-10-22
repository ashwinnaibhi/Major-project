"""Regression checks run against a disposable SQLite database, never the user database."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = str(Path(tempfile.gettempdir()) / f"haemopulse-regression-{os.getpid()}.sqlite3")
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
    conn = connect()
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
    assert body["delivery_status"] == "DISABLED" and body["delivered"] is False
    duplicate = client.post("/api/v1/donors/send-email-alert", json=payload, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
    conn = connect()
    try:
        rows = conn.execute("SELECT id FROM emergency_alerts WHERE idempotency_key = ?", (payload["idempotency_key"],)).fetchall()
        assert len(rows) == 1
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
