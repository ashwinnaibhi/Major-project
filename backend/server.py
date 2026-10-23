# import os
# import json
# import sqlite3
# import smtplib
# import secrets
# import hashlib
# import hmac
# import math
# import re
# from datetime import datetime, timedelta
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from typing import List, Optional
#
# from dotenv import load_dotenv
# import jwt
# from fastapi import FastAPI, HTTPException, Depends, Header, Query
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field
#
# # Load environment variables
# load_dotenv()
#
# DB_FILE = os.getenv("BLOODBANK_DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bloodbank.db"))
# FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
# _configured_jwt_secret = (os.getenv("JWT_SECRET") or "").strip()
# _jwt_secret_is_placeholder = (
#     len(_configured_jwt_secret) < 32
#     or "change_me" in _configured_jwt_secret.lower()
#     or "change-me" in _configured_jwt_secret.lower()
#     or "replace-with" in _configured_jwt_secret.lower()
#     or "your_secret" in _configured_jwt_secret.lower()
# )
# JWT_SECRET_CONFIGURED = not _jwt_secret_is_placeholder
# JWT_SECRET = _configured_jwt_secret if JWT_SECRET_CONFIGURED else secrets.token_urlsafe(48)
# JWT_ALGORITHM = "HS256"
# EXTERNAL_MESSAGES_ENABLED = os.getenv("HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES", "true").strip().lower() not in {"1", "true", "yes"}
# VALID_BLOOD_GROUPS = {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
# SUPPORTED_COMPONENT_TYPES = {"Whole Blood"}
# LOCATION_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "location_catalog.json")
#
#
# def get_location_catalog_data(conn=None) -> dict:
#     """Return one shared catalog, retaining valid selectable places even when no donor is registered there."""
#     catalogue = {"districts": [], "taluks_by_district": {}}
#     try:
#         with open(LOCATION_CATALOG_PATH, "r", encoding="utf-8") as catalog_file:
#             loaded = json.load(catalog_file)
#         districts = loaded.get("districts", [])
#         taluks_by_district = loaded.get("taluks_by_district", {})
#         if isinstance(districts, list) and isinstance(taluks_by_district, dict):
#             catalogue = {
#                 "districts": [str(value).strip() for value in districts if str(value).strip()],
#                 "taluks_by_district": {
#                     str(key).strip(): [str(value).strip() for value in values if str(value).strip()]
#                     for key, values in taluks_by_district.items() if isinstance(values, list) and str(key).strip()
#                 },
#             }
#     except (OSError, ValueError, TypeError):
#         pass
#
#     owned_connection = conn is None
#     active_conn = conn or get_db_connection()
#     try:
#         pairs = active_conn.execute("""
#             SELECT DISTINCT TRIM(district) AS district, TRIM(taluk) AS taluk
#             FROM donors WHERE district IS NOT NULL AND TRIM(district) != ''
#             ORDER BY district COLLATE NOCASE, taluk COLLATE NOCASE
#         """).fetchall()
#     finally:
#         if owned_connection:
#             active_conn.close()
#
#     mapping = catalogue["taluks_by_district"]
#     district_lookup = {str(name).casefold(): name for name in catalogue["districts"]}
#     for row in pairs:
#         district, taluk = row["district"], row["taluk"]
#         if not district:
#             continue
#         canonical_district = district_lookup.get(district.casefold())
#         if canonical_district is None:
#             canonical_district = district
#             catalogue["districts"].append(canonical_district)
#             district_lookup[canonical_district.casefold()] = canonical_district
#         mapping.setdefault(canonical_district, [])
#         if taluk and taluk.casefold() not in {value.casefold() for value in mapping[canonical_district]}:
#             mapping[canonical_district].append(taluk)
#
#     catalogue["districts"] = sorted(set(catalogue["districts"]), key=str.casefold)
#     for district in list(mapping):
#         mapping[district] = sorted(set(mapping[district]), key=str.casefold)
#     return catalogue
#
# if not JWT_SECRET_CONFIGURED:
#     print("[SECURITY NOTICE] JWT_SECRET is missing, too short, or still a template placeholder; using an ephemeral development secret. Set a unique random secret of at least 32 characters to preserve sessions across restarts.")
#
# SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
# SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
# SMTP_USER = os.getenv("SMTP_USER", "")
# SMTP_PASS = os.getenv("SMTP_PASS", "")
# MAIL_FROM = os.getenv("MAIL_FROM", f"HaemoPulse Blood Bank <{SMTP_USER}>" if SMTP_USER else "HaemoPulse <no-reply@haemopulse.org>")
#
# def get_db_connection():
#     conn = sqlite3.connect(DB_FILE)
#     conn.row_factory = sqlite3.Row
#     return conn
#
# def hash_password(password: str) -> str:
#     """Hash new passwords with salted PBKDF2; supports stdlib-only deployments."""
#     salt = secrets.token_bytes(16)
#     iterations = 310_000
#     digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
#     return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
#
#
# def verify_password(password: str, stored_value: str) -> tuple[bool, bool]:
#     """Return (valid, needs_rehash), including legacy SHA-256/plain formats."""
#     if not stored_value:
#         return False, False
#     if stored_value.startswith("pbkdf2_sha256$"):
#         try:
#             _, iterations, salt_hex, digest_hex = stored_value.split("$", 3)
#             candidate = hashlib.pbkdf2_hmac(
#                 "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
#             ).hex()
#             valid = hmac.compare_digest(candidate, digest_hex)
#             return valid, bool(valid and int(iterations) < 310_000)
#         except (ValueError, TypeError):
#             return False, False
#     # Keep older accounts usable and transparently upgrade their password hashes after login.
#     legacy_sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
#     if hmac.compare_digest(legacy_sha, stored_value):
#         return True, True
#     if hmac.compare_digest(password, stored_value):
#         return True, True
#     return False, False
#
#
# def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
#     """Great-circle distance in kilometres. Inputs must be validated first."""
#     radius = 6371.0088
#     phi1, phi2 = math.radians(lat1), math.radians(lat2)
#     d_phi = math.radians(lat2 - lat1)
#     d_lam = math.radians(lon2 - lon1)
#     a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
#     a = min(1.0, max(0.0, a))
#     return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#
#
# def valid_coordinates(latitude: Optional[float], longitude: Optional[float]) -> bool:
#     return (
#         latitude is not None and longitude is not None
#         and math.isfinite(latitude) and math.isfinite(longitude)
#         and -90 <= latitude <= 90 and -180 <= longitude <= 180
#     )
#
# def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
#     to_encode = data.copy()
#     expire = datetime.utcnow() + expires_delta
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
#
# def decode_access_token(token: str) -> Optional[dict]:
#     try:
#         payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#         return payload
#     except Exception:
#         return None
#
# def init_sqlite_db():
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     # 1. Users Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS users (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT NOT NULL,
#         email TEXT UNIQUE NOT NULL,
#         password TEXT NOT NULL,
#         phone TEXT NOT NULL,
#         role TEXT NOT NULL,
#         is_verified INTEGER DEFAULT 0,
#         verification_token TEXT,
#         verification_token_expiry TEXT,
#         last_verification_email_sent_at TEXT,
#         status TEXT DEFAULT 'ACTIVE'
#     );
#     """)
#
#     # 2. Donors Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS donors (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         donor_id TEXT UNIQUE NOT NULL,
#         user_id INTEGER,
#         name TEXT NOT NULL,
#         email TEXT UNIQUE NOT NULL,
#         blood_group TEXT NOT NULL,
#         age INTEGER NOT NULL,
#         gender TEXT DEFAULT 'Male',
#         location TEXT NOT NULL,
#         distance_km REAL DEFAULT 5.0,
#         last_donation_days INTEGER DEFAULT 180,
#         last_donation_date TEXT,
#         total_donations INTEGER DEFAULT 0,
#         donation_frequency INTEGER DEFAULT 2,
#         previous_response_rate REAL DEFAULT 0.90,
#         preferred_time TEXT DEFAULT 'Morning',
#         health_score INTEGER DEFAULT 95,
#         availability_status TEXT DEFAULT 'HIGH',
#         availability_score REAL DEFAULT 91.5,
#         is_available INTEGER DEFAULT 1
#     );
#     """)
#
#     # 3. Blood Inventory Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS blood_inventory (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         blood_group TEXT UNIQUE NOT NULL,
#         component_type TEXT DEFAULT 'Whole Blood',
#         units_available INTEGER DEFAULT 0,
#         expiry_date TEXT NOT NULL,
#         status TEXT DEFAULT 'AVAILABLE'
#     );
#     """)
#
#     # 4. Blood Requests Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS blood_requests (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         hospital_name TEXT NOT NULL,
#         hospital_address TEXT,
#         contact_phone TEXT,
#         blood_group TEXT NOT NULL,
#         units_needed INTEGER NOT NULL,
#         urgency_level TEXT NOT NULL,
#         patient_name TEXT NOT NULL,
#         status TEXT DEFAULT 'PENDING',
#         request_date TEXT NOT NULL,
#         created_by_user_id INTEGER
#     );
#     """)
#
#     # 5. Appointments Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS appointments (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         donor_id TEXT,
#         donor_name TEXT NOT NULL,
#         donor_email TEXT,
#         blood_group TEXT NOT NULL,
#         appointment_date TEXT NOT NULL,
#         time_slot TEXT NOT NULL,
#         center_name TEXT DEFAULT 'Central Blood Bank Hub #1',
#         status TEXT DEFAULT 'SCHEDULED',
#         created_at TEXT
#     );
#     """)
#
#     # 6. Past Donations History Table
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS donations (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         donation_code TEXT UNIQUE,
#         donor_email TEXT NOT NULL,
#         donor_name TEXT NOT NULL,
#         blood_group TEXT NOT NULL,
#         units INTEGER DEFAULT 1,
#         donation_date TEXT NOT NULL,
#         center_name TEXT NOT NULL,
#         status TEXT DEFAULT 'Verified'
#     );
#     """)
#
#     # Minimal additive audit tables for idempotent stock additions and emergency alert outcomes.
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS inventory_additions (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         idempotency_key TEXT NOT NULL UNIQUE,
#         inventory_id INTEGER,
#         blood_group TEXT NOT NULL,
#         component_type TEXT NOT NULL,
#         quantity INTEGER NOT NULL CHECK(quantity > 0),
#         created_by_user_id INTEGER,
#         created_at TEXT NOT NULL
#     );
#     """)
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS emergency_alerts (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         idempotency_key TEXT NOT NULL UNIQUE,
#         request_id INTEGER,
#         requested_by_user_id INTEGER NOT NULL,
#         donor_id TEXT NOT NULL,
#         blood_group TEXT NOT NULL,
#         hospital_name TEXT NOT NULL,
#         urgency_level TEXT NOT NULL,
#         patient_reference TEXT,
#         delivery_status TEXT NOT NULL,
#         email_configured INTEGER NOT NULL DEFAULT 0,
#         delivered INTEGER NOT NULL DEFAULT 0,
#         created_at TEXT NOT NULL
#     );
#     """)
#     conn.commit()
#
#     # Database Schema Migrations for existing DB files (add missing columns safely)
#     def add_col_if_missing(table, col, col_def):
#         cursor.execute(f"PRAGMA table_info({table});")
#         cols = [c[1] for c in cursor.fetchall()]
#         if col not in cols:
#             cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def};")
#
#     add_col_if_missing("users", "is_verified", "INTEGER DEFAULT 0")
#     add_col_if_missing("users", "verification_token", "TEXT")
#     add_col_if_missing("users", "verification_token_expiry", "TEXT")
#     add_col_if_missing("users", "last_verification_email_sent_at", "TEXT")
#
#     add_col_if_missing("donors", "user_id", "INTEGER")
#     add_col_if_missing("donors", "gender", "TEXT DEFAULT 'Male'")
#     add_col_if_missing("donors", "last_donation_date", "TEXT")
#     add_col_if_missing("donors", "is_available", "INTEGER DEFAULT 1")
#     add_col_if_missing("donors", "dob", "TEXT")
#     add_col_if_missing("donors", "phone", "TEXT")
#     add_col_if_missing("donors", "district", "TEXT")
#     add_col_if_missing("donors", "taluk", "TEXT")
#     add_col_if_missing("donors", "fictional_address", "TEXT")
#     add_col_if_missing("donors", "latitude", "REAL")
#     add_col_if_missing("donors", "longitude", "REAL")
#     add_col_if_missing("donors", "consent", "TEXT")
#
#     add_col_if_missing("blood_requests", "hospital_address", "TEXT")
#     add_col_if_missing("blood_requests", "contact_phone", "TEXT")
#     add_col_if_missing("blood_requests", "created_by_user_id", "INTEGER")
#     add_col_if_missing("blood_requests", "destination_latitude", "REAL")
#     add_col_if_missing("blood_requests", "destination_longitude", "REAL")
#
#     add_col_if_missing("appointments", "donor_id", "TEXT")
#     add_col_if_missing("appointments", "donor_email", "TEXT")
#     add_col_if_missing("appointments", "center_name", "TEXT DEFAULT 'Central Blood Bank Hub #1'")
#     add_col_if_missing("appointments", "created_at", "TEXT")
#     conn.commit()
#
#     # Optional demo fixtures; never inject fictional records into a normal/production database.
#     if os.getenv("HAEMOPULSE_ENABLE_DEMO_SEED", "false").strip().lower() in {"1", "true", "yes"}:
#         cursor.execute("SELECT COUNT(*) FROM donors;")
#         if cursor.fetchone()[0] == 0:
#             cursor.executemany("""
#             INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, distance_km, last_donation_days, last_donation_date, total_donations, donation_frequency, previous_response_rate, preferred_time, health_score, availability_status, availability_score, is_available)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
#             """, [
#                 ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', 29, 'Male', 'Zone A (Central)', 3.5, 150, '2026-03-15', 4, 3, 0.95, 'Morning', 98, 'HIGH', 94.5),
#                 ('DNR-1002', 'Sarah Jenkins', 'sarah.j@email.com', 'A-', 34, 'Female', 'Zone B (North)', 6.2, 125, '2026-04-10', 6, 4, 0.88, 'Afternoon', 95, 'HIGH', 89.0),
#                 ('DNR-1003', 'Michael Brown', 'mbrown@email.com', 'B+', 42, 'Male', 'Zone A (Central)', 8.0, 24, '2026-07-20', 2, 1, 0.40, 'Evening', 85, 'LOW', 35.0),
#                 ('DNR-1004', 'Emily Davis', 'emily.d@email.com', 'AB+', 25, 'Female', 'Zone C (South)', 12.5, 215, '2026-01-12', 3, 2, 0.75, 'Morning', 92, 'MEDIUM', 68.5)
#             ])
#             conn.commit()
#
#         # Demo-data mode deliberately does not seed login accounts or default credentials.
#         # Provision management access with backend/create_role_user.py instead.
#
#         cursor.execute("SELECT COUNT(*) FROM blood_inventory;")
#         if cursor.fetchone()[0] == 0:
#             cursor.executemany("""
#             INSERT INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status)
#             VALUES (?, ?, ?, ?, ?);
#             """, [
#                 ('O+', 'Whole Blood', 45, '2026-09-15', 'AVAILABLE'),
#                 ('O-', 'Whole Blood', 8, '2026-09-01', 'LOW_STOCK'),
#                 ('A+', 'Whole Blood', 32, '2026-09-20', 'AVAILABLE'),
#                 ('A-', 'Whole Blood', 12, '2026-08-30', 'AVAILABLE'),
#                 ('B+', 'Whole Blood', 28, '2026-09-10', 'AVAILABLE'),
#                 ('B-', 'Whole Blood', 5, '2026-08-25', 'LOW_STOCK'),
#                 ('AB+', 'Whole Blood', 18, '2026-09-25', 'AVAILABLE'),
#                 ('AB-', 'Whole Blood', 4, '2026-08-28', 'LOW_STOCK')
#             ])
#             conn.commit()
#
#         cursor.execute("SELECT COUNT(*) FROM blood_requests;")
#         if cursor.fetchone()[0] == 0:
#             cursor.executemany("""
#             INSERT INTO blood_requests (hospital_name, hospital_address, contact_phone, blood_group, units_needed, urgency_level, patient_name, status, request_date)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
#             """, [
#                 ('City General Hospital', '100 Healthcare Blvd, Suite 400', '+1-800-555-0101', 'O-', 4, 'EMERGENCY', 'Trauma Unit Patient #402', 'PENDING', '2026-08-13 08:30:00'),
#                 ('St. Jude Emergency Center', '450 Trauma Way, East Wing', '+1-800-555-0102', 'B-', 2, 'HIGH', 'Surgical Patient #109', 'APPROVED', '2026-08-12 14:15:00')
#             ])
#             conn.commit()
#
#         cursor.execute("SELECT COUNT(*) FROM donations;")
#         if cursor.fetchone()[0] == 0:
#             cursor.executemany("""
#             INSERT INTO donations (donation_code, donor_email, donor_name, blood_group, units, donation_date, center_name, status)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?);
#             """, [
#                 ('DON-901', 'john.doe@email.com', 'John Doe', 'O+', 1, '2026-03-15', 'Central Blood Bank Hub #1', 'Verified'),
#                 ('DON-812', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-10-18', 'City General Blood Center', 'Verified'),
#                 ('DON-705', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-06-04', 'St. Jude Mobile Drive', 'Verified')
#             ])
#             conn.commit()
#
#         cursor.execute("SELECT COUNT(*) FROM appointments;")
#         if cursor.fetchone()[0] == 0:
#             cursor.executemany("""
#             INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
#             """, [
#                 ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', '2026-10-20', 'Morning (8 AM - 12 PM)', 'Central Blood Bank Hub #1', 'SCHEDULED', '2026-10-10 10:00:00')
#             ])
#             conn.commit()
#
#     conn.close()
#
# # Initialize DB
# init_sqlite_db()
#
# app = FastAPI(
#     title="HaemoPulse Blood Bank API",
#     description="Enterprise REST API with Real SMTP Email Verification, JWT Authentication, and ML Optimization",
#     version="3.5.0"
# )
#
# _cors_origins = [origin.strip() for origin in os.getenv(
#     "CORS_ORIGINS", f"{FRONTEND_URL},http://127.0.0.1:3000"
# ).split(",") if origin.strip()]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=_cors_origins,
#     allow_credentials=False,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
# )
#
# # --- REAL SMTP EMAIL SERVICE ---
# def send_real_verification_email(to_email: str, recipient_name: str, token: str) -> dict:
#     verify_link = f"{FRONTEND_URL}/verify-email?token={token}"
#     subject = "Verify Your HaemoPulse Donor Account"
#
#     html_content = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#       <meta charset="utf-8">
#       <style>
#         body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 0; }}
#         .container {{ max-width: 580px; margin: 30px auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; }}
#         .header {{ background: linear-gradient(135deg, #991b1b, #dc2626); padding: 32px 24px; text-align: center; }}
#         .title {{ color: #ffffff; font-size: 24px; font-weight: 800; margin: 8px 0 0; }}
#         .subtitle {{ color: #fecaca; font-size: 13px; margin: 4px 0 0; }}
#         .content {{ padding: 32px 28px; line-height: 1.6; color: #cbd5e1; font-size: 14px; }}
#         .btn {{ display: inline-block; background: #dc2626; color: #ffffff !important; font-weight: 700; font-size: 14px; text-decoration: none; padding: 14px 28px; border-radius: 10px; margin: 20px 0; text-align: center; }}
#         .footer {{ padding: 20px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; background: #090d16; }}
#         .card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin: 16px 0; font-size: 12px; color: #94a3b8; }}
#       </style>
#     </head>
#     <body>
#       <div class="container">
#         <div class="header">
#           <div style="font-size: 36px;">🩸</div>
#           <h1 class="title">HaemoPulse</h1>
#           <p class="subtitle">Online Blood Bank & ML Availability Engine</p>
#         </div>
#         <div class="content">
#           <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Welcome, {recipient_name}!</h2>
#           <p>Thank you for registering as a blood donor. Every donation helps save lives during critical medical emergencies.</p>
#           <p>Please click the button below to verify your email address and activate all features of your Donor Portal:</p>
#           <div style="text-align: center;">
#             <a href="{verify_link}" class="btn">Verify My Email Address</a>
#           </div>
#           <div class="card">
#             <strong>Link not working?</strong> Copy and paste this URL into your browser:<br>
#             <a href="{verify_link}" style="color: #f87171; word-break: break-all;">{verify_link}</a>
#           </div>
#           <p style="font-size: 12px; color: #64748b;">This verification link will expire in 24 hours. If you did not create this account, please ignore this email.</p>
#         </div>
#         <div class="footer">
#           &copy; 2026 HaemoPulse Blood Bank Management System. All rights reserved.
#         </div>
#       </div>
#     </body>
#     </html>
#     """
#
#     email_sent = False
#     error_msg = None
#
#     # External messages are opt-in; do not send mail in test or controlled environments.
#     if EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS:
#         try:
#             msg = MIMEMultipart("alternative")
#             msg["Subject"] = subject
#             msg["From"] = SMTP_MAIL_FROM
#             msg["To"] = to_email
#
#             part = MIMEText(html_content, "html")
#             msg.attach(part)
#
#             server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
#             server.ehlo()
#             server.starttls()
#             server.ehlo()
#             server.login(SMTP_USER, SMTP_PASS)
#             server.send_message(msg)
#             server.quit()
#             email_sent = True
#         except Exception as e:
#             error_msg = str(e)
#             print(f"[SMTP ERROR] Failed to send email via {SMTP_HOST}:{SMTP_PORT}: {e}")
#     # Never print or return the raw verification token/link. The UI must report actual delivery state.
#     return {
#         "sent": email_sent,
#         "recipient": to_email,
#         "delivery_status": "DELIVERED" if email_sent else ("DISABLED" if not EXTERNAL_MESSAGES_ENABLED else ("NOT_CONFIGURED" if not (SMTP_USER and SMTP_PASS) else "FAILED")),
#         "error": "Email delivery failed. Check SMTP configuration." if error_msg else None
#     }
#
# def send_emergency_alert_email(to_email: str, recipient_name: str, blood_group: str, hospital_name: str, urgency: str, patient: str) -> dict:
#     subject = f"URGENT {blood_group} Blood Emergency Alert - {hospital_name}"
#     html_content = f"""
#     <!DOCTYPE html>
#     <html>
#     <body style="font-family: sans-serif; background: #020617; color: #f8fafc; padding: 20px;">
#       <div style="max-width: 540px; margin: auto; background: #0f172a; border: 1px solid #991b1b; border-radius: 12px; padding: 24px;">
#         <h2 style="color: #ef4444; margin-top: 0;">🚨 CRITICAL EMERGENCY BLOOD REQUEST</h2>
#         <p>Dear <strong>{recipient_name}</strong>,</p>
#         <p><strong>{hospital_name}</strong> has issued an urgent emergency requisition for blood group <strong>{blood_group}</strong>.</p>
#         <div style="background: #1e293b; padding: 14px; border-radius: 8px; margin: 16px 0; font-size: 13px;">
#           <p style="margin: 4px 0;"><strong>Blood Group Needed:</strong> <span style="color:#ef4444; font-size: 16px; font-weight:bold;">{blood_group}</span></p>
#           <p style="margin: 4px 0;"><strong>Urgency Level:</strong> {urgency}</p>
#           <p style="margin: 4px 0;"><strong>Hospital:</strong> {hospital_name}</p>
#         </div>
#         <p>Please sign in to HaemoPulse to review the request and decide whether you can respond. This notification does not guarantee eligibility or availability.</p>
#         <div style="text-align: center; margin-top: 20px;">
#           <a href="{FRONTEND_URL}" style="background: #dc2626; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold;">Open HaemoPulse Dashboard</a>
#         </div>
#       </div>
#     </body>
#     </html>
#     """
#
#     email_sent = False
#     if EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS:
#         try:
#             msg = MIMEMultipart("alternative")
#             msg["Subject"] = subject
#             msg["From"] = MAIL_FROM
#             msg["To"] = to_email
#             msg.attach(MIMEText(html_content, "html"))
#
#             server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
#             server.ehlo()
#             server.starttls()
#             server.login(SMTP_USER, SMTP_PASS)
#             server.send_message(msg)
#             server.quit()
#             email_sent = True
#         except Exception as e:
#             print(f"[SMTP ALERT ERROR] {e}")
#
#     return {
#         "sent": email_sent,
#         "to": to_email,
#         "delivery_status": "DELIVERED" if email_sent else ("DISABLED" if not EXTERNAL_MESSAGES_ENABLED else ("NOT_CONFIGURED" if not (SMTP_USER and SMTP_PASS) else "FAILED")),
#     }
#
# # --- PYDANTIC SCHEMAS ---
# class RegisterDonorRequest(BaseModel):
#     name: str = Field(..., min_length=2, max_length=120)
#     email: str = Field(..., min_length=5, max_length=254)
#     password: str = Field(..., min_length=8, max_length=256)
#     phone: str = Field(..., min_length=6, max_length=32)
#     blood_group: str
#     age: int = Field(..., ge=18, le=65)
#     gender: Optional[str] = "Male"
#     location: str = Field(..., min_length=2, max_length=160)
#     district: Optional[str] = None
#     taluk: Optional[str] = None
#     preferred_time: Optional[str] = "Morning"
#     consent_to_emergency_alerts: bool = False
#
# class LoginRequest(BaseModel):
#     email: str
#     password: str
#
# class UpdateDonorProfileRequest(BaseModel):
#     name: Optional[str] = None
#     phone: Optional[str] = None
#     age: Optional[int] = None
#     gender: Optional[str] = None
#     blood_group: Optional[str] = None
#     location: Optional[str] = None
#     preferred_time: Optional[str] = None
#
# class AvailabilityToggleRequest(BaseModel):
#     is_available: bool
#
# class BookAppointmentRequest(BaseModel):
#     donor_id: Optional[str] = None
#     donor_name: Optional[str] = None
#     donor_email: Optional[str] = None
#     blood_group: str
#     appointment_date: str
#     time_slot: str
#     center_name: Optional[str] = "Central Blood Bank Hub #1"
#
# class RequestCreateRequest(BaseModel):
#     hospital_name: str = Field(..., min_length=2, max_length=160)
#     hospital_address: str = Field(..., min_length=4, max_length=300)
#     contact_phone: Optional[str] = Field("", max_length=32)
#     blood_group: str
#     units_needed: int = Field(..., ge=1, le=1000)
#     urgency_level: str
#     patient_name: str = Field(..., min_length=1, max_length=160)
#     destination_latitude: Optional[float] = Field(None, ge=-90, le=90)
#     destination_longitude: Optional[float] = Field(None, ge=-180, le=180)
#
# class InventoryCreateRequest(BaseModel):
#     blood_group: str
#     units_available: int = Field(..., ge=1, le=10000)
#     component_type: Optional[str] = "Whole Blood"
#     expiry_date: Optional[str] = None
#     idempotency_key: str = Field(..., min_length=8, max_length=128)
#
# class ResendVerificationRequest(BaseModel):
#     email: str
#
# # Dependency to extract optional/required token user
# def get_current_user_from_header(authorization: Optional[str] = Header(None)) -> Optional[dict]:
#     if not authorization or not authorization.startswith("Bearer "):
#         return None
#     parts = authorization.split()
#     if len(parts) != 2:
#         return None
#     return decode_access_token(parts[1])
#
#
# def require_roles(user_payload: Optional[dict], allowed_roles: set[str]) -> dict:
#     if not user_payload or not user_payload.get("id"):
#         raise HTTPException(status_code=401, detail="A valid authentication token is required.")
#     conn = get_db_connection()
#     try:
#         row = conn.execute("SELECT id, role, status FROM users WHERE id = ?", (user_payload["id"],)).fetchone()
#     finally:
#         conn.close()
#     if not row or (row["status"] or "ACTIVE").upper() != "ACTIVE":
#         raise HTTPException(status_code=401, detail="The authenticated account is unavailable.")
#     role = str(row["role"] or "").upper()
#     if role not in allowed_roles or str(user_payload.get("role", "")).upper() != role:
#         raise HTTPException(status_code=403, detail="Your account is not authorized to perform this action.")
#     return {**user_payload, "role": role}
#
# @app.get("/")
# def home():
#     return {
#         "service": "HaemoPulse REST API Engine",
#         "database": "SQLite Relational Database (bloodbank.db)",
#         "smtp_configured": bool(EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS),
#         "external_messages_enabled": EXTERNAL_MESSAGES_ENABLED,
#         "status": "ONLINE"
#     }
#
# # ========================================================
# # 1. AUTHENTICATION & EMAIL VERIFICATION
# # ========================================================
#
# @app.post("/api/v1/auth/register")
# def register_donor(req: RegisterDonorRequest):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     req_email = req.email.strip().lower()
#     if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", req_email):
#         conn.close()
#         raise HTTPException(status_code=422, detail="Enter a valid email address.")
#     if req.blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
#         conn.close()
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#     if req.gender and req.gender not in {"Male", "Female", "Other"}:
#         conn.close()
#         raise HTTPException(status_code=422, detail="Unsupported gender value.")
#     cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
#     existing_user = cursor.fetchone()
#
#     if existing_user:
#         conn.close()
#         raise HTTPException(status_code=400, detail="An account with this email address already exists. Please log in.")
#
#     # Generate 32-byte secure token for 24-hour verification
#     raw_token = secrets.token_urlsafe(32)
#     expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
#     now_iso = datetime.utcnow().isoformat()
#     hashed_pwd = hash_password(req.password)
#
#     # Public registration always creates a donor; submitted role fields are intentionally ignored.
#     safe_name = req.name.strip()
#     safe_phone = req.phone.strip()
#     safe_location = req.location.strip()
#     if not safe_name or not safe_phone or not safe_location:
#         conn.close()
#         raise HTTPException(status_code=422, detail="Name, phone, and location are required.")
#     # District/taluk values are checked against the same catalogue returned by the location API.
#     catalogue = get_location_catalog_data(conn)
#     district_values = {str(value).casefold(): value for value in catalogue["districts"]}
#     selected_district = district_values.get((req.district or "").strip().casefold()) if req.district else None
#     if req.district and not selected_district:
#         conn.close()
#         raise HTTPException(status_code=422, detail="Select a valid district from the location catalog.")
#     if req.taluk:
#         valid_taluks = catalogue["taluks_by_district"].get(selected_district, []) if selected_district else []
#         selected_taluk = {str(value).casefold(): value for value in valid_taluks}.get(req.taluk.strip().casefold())
#         if not selected_taluk:
#             conn.close()
#             raise HTTPException(status_code=422, detail="Select a taluk belonging to the chosen district.")
#
#     # Insert user with is_verified = 0
#     cursor.execute("""
#     INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry, last_verification_email_sent_at)
#     VALUES (?, ?, ?, ?, 'ROLE_DONOR', 0, ?, ?, ?);
#     """, (safe_name, req_email, hashed_pwd, safe_phone, raw_token, expiry, now_iso))
#
#     user_id = cursor.lastrowid
#     donor_id = f"DNR-{1000 + user_id}"
#
#     # Insert donor profile
#     cursor.execute("""
#     INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location,
#                         distance_km, last_donation_days, last_donation_date, total_donations,
#                         donation_frequency, previous_response_rate, preferred_time, health_score,
#                         availability_status, availability_score, is_available)
#     VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, 0, NULL, ?, NULL, NULL, NULL, 1);
#     """, (donor_id, user_id, safe_name, req_email, req.blood_group.strip().upper(), req.age,
#           req.gender or "Male", safe_location, req.preferred_time or "Morning"))
#     cursor.execute("UPDATE donors SET district = ?, taluk = ?, phone = ?, consent = ? WHERE user_id = ?", (req.district.strip() if req.district else None, req.taluk.strip() if req.taluk else None, safe_phone, "OPTED_IN" if req.consent_to_emergency_alerts else "PENDING", user_id))
#
#     conn.commit()
#
#     cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
#     new_user = dict(cursor.fetchone())
#     for secret_field in ("password", "verification_token", "verification_token_expiry", "last_verification_email_sent_at"):
#         new_user.pop(secret_field, None)
#
#     cursor.execute("SELECT * FROM donors WHERE user_id = ?;", (user_id,))
#     new_donor = dict(cursor.fetchone())
#     conn.close()
#
#     # Send real email verification
#     mail_result = send_real_verification_email(req_email, safe_name, raw_token)
#
#     # Create JWT session token; role comes from the server, never from the request body.
#     jwt_token = create_access_token({"sub": req_email, "id": user_id, "role": "ROLE_DONOR"})
#
#     return {
#         "message": "Registration successful. " + ("Verification email was delivered." if mail_result["sent"] else f"Verification email status: {mail_result['delivery_status']}.") ,
#         "token": jwt_token,
#         "user": {
#             **new_user,
#             "donor_id": donor_id,
#             "blood_group": req.blood_group,
#             "is_verified": False,
#             "role": "ROLE_DONOR"
#         },
#         "donor": new_donor,
#         "email_delivery": mail_result
#     }
#
# @app.post("/api/v1/auth/login")
# def login(req: LoginRequest):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     req_email = req.email.strip().lower()
#
#     cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
#     user = cursor.fetchone()
#     valid_password, needs_rehash = verify_password(req.password, user["password"] if user else "")
#
#     if not user or not valid_password or (user["status"] or "ACTIVE").upper() != "ACTIVE":
#         conn.close()
#         raise HTTPException(status_code=401, detail="Invalid email or password.")
#     if needs_rehash:
#         cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(req.password), user["id"]))
#         conn.commit()
#         cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
#         user = cursor.fetchone()
#
#     user_dict = dict(user)
#     for secret_field in ("password", "verification_token", "verification_token_expiry", "last_verification_email_sent_at"):
#         user_dict.pop(secret_field, None)
#
#     # Attach donor profile if donor
#     donor_profile = None
#     if user_dict["role"] in ["ROLE_DONOR", "DONOR"]:
#         cursor.execute("SELECT * FROM donors WHERE LOWER(email) = ? OR user_id = ?;", (req_email, user_dict["id"]))
#         donor_row = cursor.fetchone()
#         if donor_row:
#             donor_profile = dict(donor_row)
#             user_dict["donor_id"] = donor_profile["donor_id"]
#             user_dict["blood_group"] = donor_profile["blood_group"]
#             user_dict["is_available"] = bool(donor_profile.get("is_available", 1))
#
#     conn.close()
#
#     jwt_token = create_access_token({
#         "sub": req_email,
#         "id": user_dict["id"],
#         "role": user_dict["role"]
#     })
#
#     return {
#         "message": "Login successful",
#         "token": jwt_token,
#         "user": user_dict,
#         "donor": donor_profile
#     }
#
# @app.get("/api/v1/auth/me")
# def get_current_user_profile(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     if not user_payload:
#         raise HTTPException(status_code=401, detail="Authentication token required or expired.")
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM users WHERE id = ?;", (user_payload["id"],))
#     user = cursor.fetchone()
#
#     if not user:
#         conn.close()
#         raise HTTPException(status_code=404, detail="User not found.")
#
#     user_dict = dict(user)
#     for secret_field in ("password", "verification_token", "verification_token_expiry", "last_verification_email_sent_at"):
#         user_dict.pop(secret_field, None)
#
#     donor_profile = None
#     if user_dict["role"] in ["ROLE_DONOR", "DONOR"]:
#         cursor.execute("SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1;", (user_dict["id"], user_dict["email"].lower(), user_dict["id"]))
#         d = cursor.fetchone()
#         if d:
#             donor_profile = dict(d)
#             user_dict["donor_id"] = donor_profile["donor_id"]
#             user_dict["blood_group"] = donor_profile["blood_group"]
#             user_dict["is_available"] = bool(donor_profile.get("is_available", 1))
#
#     conn.close()
#     return {"user": user_dict, "donor": donor_profile}
#
# @app.get("/api/v1/auth/verify-email")
# @app.post("/api/v1/auth/verify-email")
# def verify_email(token: str = Query(...)):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     cursor.execute("SELECT * FROM users WHERE verification_token = ?;", (token,))
#     user = cursor.fetchone()
#
#     if not user:
#         conn.close()
#         raise HTTPException(status_code=400, detail="Invalid verification token. It may have already been used.")
#
#     user_dict = dict(user)
#     expiry_str = user_dict.get("verification_token_expiry")
#     if expiry_str:
#         try:
#             exp_dt = datetime.fromisoformat(expiry_str)
#         except ValueError:
#             conn.close()
#             raise HTTPException(status_code=400, detail="Verification token is invalid.")
#         if datetime.utcnow() > exp_dt:
#             conn.close()
#             raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
#
#     # Mark as verified and invalidate token
#     cursor.execute("""
#     UPDATE users
#     SET is_verified = 1, verification_token = NULL, verification_token_expiry = NULL
#     WHERE id = ?;
#     """, (user_dict["id"],))
#     conn.commit()
#     conn.close()
#
#     return {
#         "success": True,
#         "message": "Your email has been successfully verified! All donor portal features are now unlocked.",
#         "email": user_dict["email"]
#     }
#
# @app.post("/api/v1/auth/resend-verification")
# def resend_verification_email(req: ResendVerificationRequest):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     req_email = req.email.strip().lower()
#     cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
#     user = cursor.fetchone()
#
#     if not user:
#         conn.close()
#         raise HTTPException(status_code=404, detail="No account found with this email.")
#
#     if user["is_verified"] == 1:
#         conn.close()
#         return {"message": "This email address is already verified.", "already_verified": True}
#
#     # 60 seconds rate limit check
#     last_sent = user["last_verification_email_sent_at"]
#     if last_sent:
#         try:
#             last_dt = datetime.fromisoformat(last_sent)
#             seconds_diff = (datetime.utcnow() - last_dt).total_seconds()
#             if seconds_diff < 60:
#                 conn.close()
#                 wait_left = int(60 - seconds_diff)
#                 raise HTTPException(status_code=429, detail=f"Please wait {wait_left} seconds before requesting another email.")
#         except HTTPException:
#             raise
#         except Exception:
#             pass
#
#     new_token = secrets.token_urlsafe(32)
#     new_expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
#     now_iso = datetime.utcnow().isoformat()
#
#     cursor.execute("""
#     UPDATE users
#     SET verification_token = ?, verification_token_expiry = ?, last_verification_email_sent_at = ?
#     WHERE id = ?;
#     """, (new_token, new_expiry, now_iso, user["id"]))
#     conn.commit()
#     conn.close()
#
#     res = send_real_verification_email(req_email, user["name"], new_token)
#     return {
#         "success": bool(res["sent"]),
#         "message": (f"Verification email delivered to {req_email}." if res["sent"] else f"Verification email was not delivered ({res['delivery_status']})."),
#         "delivery": {"sent": res["sent"], "delivery_status": res["delivery_status"]}
#     }
#
# # ========================================================
# # 2. DONOR DASHBOARD & PROFILE MANAGEMENT
# # ========================================================
#
# @app.get("/api/v1/donors/me")
# def get_my_donor_dashboard(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     cursor.execute("SELECT * FROM users WHERE id = ?;", (user_payload["id"],))
#     user_row = cursor.fetchone()
#     if not user_row:
#         conn.close()
#         raise HTTPException(status_code=404, detail="User not found.")
#
#     user = dict(user_row)
#     if str(user.get("role", "")).upper() not in {"ROLE_DONOR", "DONOR"}:
#         conn.close()
#         raise HTTPException(status_code=403, detail="A donor account is required to view this profile.")
#     cursor.execute("SELECT * FROM donors WHERE user_id = ? ORDER BY id LIMIT 1;", (user["id"],))
#     donor_row = cursor.fetchone()
#     if not donor_row:
#         cursor.execute("SELECT * FROM donors WHERE user_id IS NULL AND LOWER(email) = ? ORDER BY id LIMIT 1;", (user["email"].lower(),))
#         donor_row = cursor.fetchone()
#     if not donor_row:
#         conn.close()
#         raise HTTPException(status_code=404, detail="Donor profile not found.")
#
#     donor = dict(donor_row)
#
#     # Fetch past donations
#     cursor.execute("SELECT * FROM donations WHERE LOWER(donor_email) = ? ORDER BY donation_date DESC;", (user["email"].lower(),))
#     donations = [dict(r) for r in cursor.fetchall()]
#
#     # Fetch donor appointments
#     cursor.execute("SELECT * FROM appointments WHERE LOWER(donor_email) = ? OR donor_id = ? ORDER BY appointment_date DESC;", (user["email"].lower(), donor["donor_id"]))
#     appointments = [dict(r) for r in cursor.fetchall()]
#
#     # Fetch matching emergency requests for notifications
#     cursor.execute("""
#         SELECT id, blood_group, units_needed, urgency_level, status, request_date,
#                hospital_name, 'Emergency blood request' AS patient_name
#         FROM blood_requests WHERE UPPER(blood_group) = UPPER(?) AND status = 'PENDING'
#         ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC
#     """, (donor["blood_group"],))
#     notifications = [dict(r) for r in cursor.fetchall()]
#
#     conn.close()
#
#     # Calculate eligibility (Male: 90 days, Female: 120 days)
#     last_days = donor.get("last_donation_days")
#     gender = donor.get("gender") or "Unknown"
#     required_gap = 120 if str(gender).lower() == "female" else 90
#     is_eligible = last_days is not None and int(last_days) >= required_gap
#     days_until_eligible = max(0, required_gap - int(last_days)) if last_days is not None else None
#
#     return {
#         "donor": donor,
#         "user": {
#             "name": user["name"],
#             "email": user["email"],
#             "phone": user["phone"],
#             "is_verified": bool(user["is_verified"])
#         },
#         "stats": {
#             "total_donations": donor.get("total_donations") if donor.get("total_donations") is not None else len(donations),
#             "last_donation_days": last_days,
#             "last_donation_date": donor.get("last_donation_date"),
#             "is_eligible": is_eligible,
#             "required_gap": required_gap,
#             "days_until_eligible": days_until_eligible,
#             "availability_score": donor.get("availability_score"),
#             "availability_status": donor.get("availability_status"),
#             "is_available": bool(donor.get("is_available", 1))
#         },
#         "donations": donations,
#         "appointments": appointments,
#         "emergency_notifications": notifications
#     }
#
# @app.put("/api/v1/donors/me/availability")
# def toggle_donor_availability(req: AvailabilityToggleRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     new_avail = 1 if req.is_available else 0
#
#     cursor.execute("""
#     UPDATE donors
#     SET is_available = ?
#     WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?);
#     """, (new_avail, user_payload["id"], user_payload["sub"].lower()))
#     conn.commit()
#     conn.close()
#
#     return {"success": True, "is_available": req.is_available, "message": "Availability status updated."}
#
# @app.put("/api/v1/donors/me/profile")
# def update_donor_profile(req: UpdateDonorProfileRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     # Update Users table
#     if req.name or req.phone:
#         updates = []
#         vals = []
#         if req.name:
#             updates.append("name = ?")
#             vals.append(req.name)
#         if req.phone:
#             updates.append("phone = ?")
#             vals.append(req.phone)
#         vals.append(user_payload["id"])
#         cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?;", tuple(vals))
#
#     # Update Donors table
#     d_updates = []
#     d_vals = []
#     if req.name:
#         d_updates.append("name = ?")
#         d_vals.append(req.name)
#     if req.age is not None:
#         d_updates.append("age = ?")
#         d_vals.append(req.age)
#     if req.gender:
#         d_updates.append("gender = ?")
#         d_vals.append(req.gender)
#     if req.blood_group:
#         d_updates.append("blood_group = ?")
#         d_vals.append(req.blood_group)
#     if req.location:
#         d_updates.append("location = ?")
#         d_vals.append(req.location)
#     if req.preferred_time:
#         d_updates.append("preferred_time = ?")
#         d_vals.append(req.preferred_time)
#     if req.phone:
#         d_updates.append("phone = ?")
#         d_vals.append(req.phone.strip())
#
#     if d_updates:
#         d_vals.extend([user_payload["id"], user_payload.get("sub", "").lower()])
#         cursor.execute(f"UPDATE donors SET {', '.join(d_updates)} WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?);", tuple(d_vals))
#
#     conn.commit()
#     cursor.execute("SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?) ORDER BY id LIMIT 1;", (user_payload["id"], user_payload.get("sub", "").lower()))
#     updated_row = cursor.fetchone()
#     if not updated_row:
#         conn.close()
#         raise HTTPException(status_code=404, detail="Donor profile not found.")
#     updated_donor = dict(updated_row)
#     conn.close()
#
#     return {"success": True, "message": "Profile updated successfully.", "donor": updated_donor}
#
# # ========================================================
# # 3. APPOINTMENTS (Booking & Verification)
# # ========================================================
#
# @app.get("/api/v1/appointments")
# def get_all_appointments(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF", "ROLE_DONOR"})
#     conn = get_db_connection()
#     try:
#         if user["role"] in {"ROLE_DONOR", "DONOR"}:
#             rows = conn.execute("SELECT * FROM appointments WHERE LOWER(donor_email) = LOWER(?) ORDER BY appointment_date ASC", (user.get("sub", ""),)).fetchall()
#         else:
#             rows = conn.execute("SELECT * FROM appointments ORDER BY appointment_date ASC").fetchall()
#         return [dict(row) for row in rows]
#     finally:
#         conn.close()
#
# @app.post("/api/v1/appointments")
# def book_appointment(req: BookAppointmentRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
#     conn = get_db_connection()
#     try:
#         user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
#         if not user_row or (user_row["status"] or "ACTIVE").upper() != "ACTIVE":
#             raise HTTPException(status_code=401, detail="The authenticated account is unavailable.")
#         if not bool(user_row["is_verified"]):
#             raise HTTPException(status_code=403, detail="Please verify your email address to book blood donation appointments.")
#         donor = conn.execute("SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1", (user["id"], user.get("sub", ""), user["id"])).fetchone()
#         if not donor:
#             raise HTTPException(status_code=404, detail="Donor profile not found.")
#         try:
#             appointment_date = datetime.strptime(req.appointment_date, "%Y-%m-%d").date()
#             if appointment_date < datetime.now().date():
#                 raise HTTPException(status_code=422, detail="Appointment date cannot be in the past.")
#         except ValueError:
#             raise HTTPException(status_code=422, detail="Appointment date must use YYYY-MM-DD format.")
#         if not req.time_slot.strip() or len(req.time_slot) > 80:
#             raise HTTPException(status_code=422, detail="Enter a valid appointment time slot.")
#         now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         cursor = conn.execute("""
#           INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
#           VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
#         """, (donor["donor_id"], donor["name"], user_row["email"].lower(), donor["blood_group"], req.appointment_date, req.time_slot.strip(), (req.center_name or "Central Blood Bank Hub #1").strip(), now_str))
#         conn.commit()
#         return {"success": True, "id": cursor.lastrowid, "message": f"Appointment booked for {req.appointment_date} ({req.time_slot})."}
#     except HTTPException:
#         conn.rollback()
#         raise
#     finally:
#         conn.close()
#
# @app.put("/api/v1/appointments/{appointment_id}/status")
# def update_appointment_status(appointment_id: int, status: str = Query(...), user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
#     clean_status = status.strip().upper()
#     if clean_status not in {"SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"}:
#         raise HTTPException(status_code=422, detail="Status must be SCHEDULED, COMPLETED, CANCELLED, or NO_SHOW.")
#     conn = get_db_connection()
#     try:
#         cursor = conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (clean_status, appointment_id))
#         conn.commit()
#         if not cursor.rowcount:
#             raise HTTPException(status_code=404, detail="Appointment not found.")
#         row = conn.execute("SELECT id, status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
#         return {"success": True, "id": row["id"], "status": row["status"], "message": "Appointment status was persisted."}
#     finally:
#         conn.close()
#
# # ========================================================
# # 4. HOSPITAL BLOOD REQUISITIONS & STAFF SYNC
# # ========================================================
#
# @app.get("/api/v1/requests")
# def get_requests(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF", "ROLE_DONOR"})
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     if user["role"] == "ROLE_DONOR":
#         donor = cursor.execute("SELECT blood_group FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY id LIMIT 1", (user["id"], user.get("sub", ""))).fetchone()
#         if not donor:
#             conn.close()
#             return []
#         cursor.execute("""
#             SELECT id, blood_group, units_needed, urgency_level, status, request_date,
#                    hospital_name, 'Emergency blood request' AS patient_name,
#                    NULL AS hospital_address, NULL AS contact_phone,
#                    destination_latitude, destination_longitude
#             FROM blood_requests WHERE UPPER(blood_group) = UPPER(?) AND status = 'PENDING'
#             ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC;
#         """, (donor["blood_group"],))
#     else:
#         cursor.execute("""
#         SELECT * FROM blood_requests
#         ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC;
#         """)
#     rows = [dict(r) for r in cursor.fetchall()]
#     conn.close()
#     return rows
#
# @app.post("/api/v1/requests")
# def create_hospital_request(req: RequestCreateRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
#     if req.blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#     if req.urgency_level.strip().upper() not in {"EMERGENCY", "HIGH", "NORMAL"}:
#         raise HTTPException(status_code=422, detail="Unsupported urgency level.")
#     if (req.destination_latitude is None) != (req.destination_longitude is None):
#         raise HTTPException(status_code=422, detail="Provide both destination latitude and longitude, or leave both blank.")
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     req_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#
#     cursor.execute("""
#     INSERT INTO blood_requests (hospital_name, hospital_address, contact_phone, blood_group, units_needed, urgency_level, patient_name, status, request_date, created_by_user_id, destination_latitude, destination_longitude)
#     VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?);
#     """, (req.hospital_name.strip(), req.hospital_address.strip(), (req.contact_phone or "").strip(), req.blood_group.strip().upper(), req.units_needed, req.urgency_level.strip().upper(), req.patient_name.strip(), req_date, user["id"], req.destination_latitude, req.destination_longitude))
#
#     conn.commit()
#     new_id = cursor.lastrowid
#     row = dict(cursor.execute("SELECT * FROM blood_requests WHERE id = ?", (new_id,)).fetchone())
#     conn.close()
#     # Creating a request never sends notifications automatically; dispatch is an explicit, audited action.
#     return row
#
# @app.put("/api/v1/requests/{request_id}/status")
# def update_request_status(request_id: int, status: str = Query(...), user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
#     allowed_statuses = ["PENDING", "APPROVED", "ALLOCATED", "FULFILLED", "REJECTED"]
#     clean_status = status.strip().upper()
#     if clean_status not in allowed_statuses:
#         raise HTTPException(status_code=400, detail=f"Status must be one of {allowed_statuses}")
#
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("UPDATE blood_requests SET status = ? WHERE id = ?;", (clean_status, request_id))
#     conn.commit()
#     found = cursor.rowcount
#     conn.close()
#     if not found:
#         raise HTTPException(status_code=404, detail="Blood request not found.")
#
#     return {"success": True, "message": f"Requisition #{request_id} status updated to {clean_status}."}
#
# @app.delete("/api/v1/requests/{request_id}")
# def delete_request(request_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN"})
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("DELETE FROM blood_requests WHERE id = ?;", (request_id,))
#     conn.commit()
#     conn.close()
#     return {"success": True, "message": f"Requisition #{request_id} deleted."}
#
# # ========================================================
# # 5. INVENTORY & DONORS GENERAL
# # ========================================================
#
# class DonorAlertEmailRequest(BaseModel):
#     donor_id: str = Field(..., min_length=1, max_length=80)
#     blood_group: str
#     request_id: int
#     idempotency_key: str = Field(..., min_length=8, max_length=128)
#     # Legacy fields are accepted for API transition but never trusted for recipient identity.
#     donor_email: Optional[str] = None
#     donor_name: Optional[str] = None
#     hospital_name: Optional[str] = None
#     urgency: Optional[str] = "EMERGENCY"
#     patient: Optional[str] = None
#
# @app.post("/api/v1/donors/send-email-alert")
# def send_donor_alert(req: DonorAlertEmailRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
#     blood_group = req.blood_group.strip().upper()
#     if blood_group not in VALID_BLOOD_GROUPS:
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#
#     conn = get_db_connection()
#     try:
#         conn.execute("BEGIN IMMEDIATE")
#         previous = conn.execute("SELECT * FROM emergency_alerts WHERE idempotency_key = ?", (req.idempotency_key,)).fetchone()
#         if previous:
#             conn.commit()
#             return {
#                 "accepted": True, "persisted": True, "queued": False,
#                 "delivered": bool(previous["delivered"]), "delivery_status": previous["delivery_status"],
#                 "duplicate": True, "alert_id": previous["id"], "donor_id": previous["donor_id"],
#                 "message": "This alert request was already processed; no second email was attempted."
#             }
#
#         blood_request = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req.request_id,)).fetchone()
#         if not blood_request:
#             raise HTTPException(status_code=404, detail="Selected blood request was not found.")
#         if str(blood_request["status"]).upper() != "PENDING":
#             raise HTTPException(status_code=409, detail="Only pending blood requests can receive emergency alerts.")
#         if str(blood_request["urgency_level"]).upper() != "EMERGENCY":
#             raise HTTPException(status_code=422, detail="Select an emergency-level blood request before dispatching an alert.")
#         if str(blood_request["blood_group"]).upper() != blood_group:
#             raise HTTPException(status_code=422, detail="Alert blood group must match the selected blood request.")
#
#         donor = conn.execute(
#             "SELECT * FROM donors WHERE CAST(id AS TEXT) = ? OR donor_id = ? ORDER BY id LIMIT 1",
#             (req.donor_id, req.donor_id)
#         ).fetchone()
#         if not donor:
#             raise HTTPException(status_code=404, detail="Selected donor was not found.")
#         if str(donor["blood_group"]).upper() != blood_group:
#             raise HTTPException(status_code=422, detail="Selected donor blood group does not match the request.")
#         if not bool(donor["is_available"]):
#             raise HTTPException(status_code=409, detail="Selected donor is not currently marked available.")
#         required_gap = 120 if str(donor["gender"] or "").lower() == "female" else 90
#         if int(donor["age"] or 0) < 18 or int(donor["age"] or 0) > 65 or int(donor["last_donation_days"] or 0) < required_gap or int(donor["health_score"] or 0) < 60:
#             raise HTTPException(status_code=409, detail="Selected donor does not meet the stored eligibility criteria.")
#         if str(donor["consent"] or "").strip().upper() not in {"OPTED_IN", "TRUE", "YES", "1"}:
#             raise HTTPException(status_code=409, detail="This donor has not explicitly opted in to emergency email alerts.")
#
#         delivery_status = "PENDING"
#         email_configured = bool(EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS)
#         cursor = conn.execute("""
#             INSERT INTO emergency_alerts
#               (idempotency_key, request_id, requested_by_user_id, donor_id, blood_group, hospital_name,
#                urgency_level, patient_reference, delivery_status, email_configured, delivered, created_at)
#             VALUES (?, ?, ?, ?, ?, ?, 'EMERGENCY', ?, ?, ?, 0, ?)
#         """, (req.idempotency_key, req.request_id, requester["id"], donor["donor_id"], blood_group,
#               blood_request["hospital_name"], str(blood_request["patient_name"] or "")[:160], delivery_status,
#               1 if email_configured else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
#         alert_id = cursor.lastrowid
#         conn.commit()
#     except HTTPException:
#         conn.rollback()
#         raise
#     except sqlite3.IntegrityError:
#         conn.rollback()
#         previous = conn.execute("SELECT * FROM emergency_alerts WHERE idempotency_key = ?", (req.idempotency_key,)).fetchone()
#         if previous:
#             return {
#                 "accepted": True, "persisted": True, "queued": False, "delivered": bool(previous["delivered"]),
#                 "delivery_status": previous["delivery_status"], "duplicate": True, "alert_id": previous["id"],
#                 "donor_id": previous["donor_id"], "message": "This alert request was already processed; no second email was attempted."
#             }
#         raise HTTPException(status_code=409, detail="Alert request conflicts with an existing operation.")
#     finally:
#         conn.close()
#
#     # Send only after an authorized, eligible, opted-in recipient is durably recorded.
#     delivery = send_emergency_alert_email(
#         donor["email"], donor["name"], blood_group, blood_request["hospital_name"],
#         "EMERGENCY", blood_request["patient_name"]
#     )
#     delivery_status = delivery.get("delivery_status", "FAILED")
#     update_conn = get_db_connection()
#     try:
#         update_conn.execute(
#             "UPDATE emergency_alerts SET delivery_status = ?, delivered = ? WHERE id = ?",
#             (delivery_status, 1 if delivery.get("sent") else 0, alert_id)
#         )
#         update_conn.commit()
#     finally:
#         update_conn.close()
#
#     delivered = bool(delivery.get("sent"))
#     message = ("Emergency email was delivered." if delivered else
#                "Alert request was saved, but no email was delivered. " + {
#                    "NOT_CONFIGURED": "SMTP credentials are not configured.",
#                    "DISABLED": "External messages are disabled in this environment.",
#                    "FAILED": "The configured email provider did not confirm delivery."
#                }.get(delivery_status, "Check the delivery status."))
#     return {
#         "accepted": True, "persisted": True, "queued": False, "delivered": delivered,
#         "delivery_status": delivery_status, "duplicate": False, "alert_id": alert_id,
#         "donor_id": donor["donor_id"], "message": message
#     }
#
#
# @app.get("/api/v1/locations")
# def get_location_catalog():
#     return get_location_catalog_data()
#
#
# @app.get("/api/v1/availability/summary")
# def get_location_availability_summary(
#     district: Optional[str] = None,
#     taluk: Optional[str] = None,
#     blood_group: Optional[str] = None
# ):
#     if blood_group and blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#     conn = get_db_connection()
#     try:
#         catalogue = get_location_catalog_data(conn)
#         district_values = {str(value).casefold(): value for value in catalogue["districts"]}
#         selected_district = district_values.get((district or "").strip().casefold()) if district and district.lower() != "all" else None
#         if district and district.lower() != "all" and not selected_district:
#             raise HTTPException(status_code=422, detail="Unknown district; choose a value from the location catalog.")
#         if taluk and taluk.lower() != "all":
#             if not selected_district:
#                 raise HTTPException(status_code=422, detail="Choose a district before selecting a taluk.")
#             valid_taluks = catalogue["taluks_by_district"].get(selected_district, [])
#             if taluk.strip().casefold() not in {str(value).casefold() for value in valid_taluks}:
#                 raise HTTPException(status_code=422, detail="The selected taluk does not belong to the selected district.")
#         clauses = ["1=1"]
#         params = []
#         if district and district.lower() != "all":
#             clauses.append("LOWER(TRIM(district)) = LOWER(TRIM(?))")
#             params.append(district)
#         if taluk and taluk.lower() != "all":
#             clauses.append("LOWER(TRIM(taluk)) = LOWER(TRIM(?))")
#             params.append(taluk)
#         if blood_group:
#             clauses.append("UPPER(blood_group) = UPPER(?)")
#             params.append(blood_group)
#         where = " AND ".join(clauses)
#         row = conn.execute(f"""
#             SELECT COUNT(*) AS total_records,
#               SUM(CASE WHEN COALESCE(is_available, 0) = 1
#                         AND COALESCE(age, 0) BETWEEN 18 AND 65
#                         AND COALESCE(health_score, 0) >= 60
#                         AND COALESCE(last_donation_days, 0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END
#                        THEN 1 ELSE 0 END) AS eligible_available,
#               SUM(CASE WHEN COALESCE(is_available, 0) = 1
#                         AND COALESCE(age, 0) BETWEEN 18 AND 65
#                         AND COALESCE(health_score, 0) >= 60
#                         AND COALESCE(last_donation_days, 0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END
#                         AND UPPER(COALESCE(consent,'')) IN ('OPTED_IN','TRUE','YES','1')
#                        THEN 1 ELSE 0 END) AS eligible_contactable
#             FROM donors WHERE {where}
#         """, tuple(params)).fetchone()
#         return {
#             "district": district or "All",
#             "taluk": taluk or "All",
#             "blood_group": blood_group.upper() if blood_group else "All",
#             "source": "database",
#             "total_records": int(row["total_records"] or 0),
#             "eligible_available_donors": int(row["eligible_available"] or 0),
#             "eligible_contactable_donors": int(row["eligible_contactable"] or 0)
#         }
#     finally:
#         conn.close()
#
#
# @app.get("/api/v1/donors")
# def get_donors(
#     blood_group: Optional[str] = None,
#     district: Optional[str] = None,
#     taluk: Optional[str] = None,
#     availability_level: Optional[str] = None,
#     eligible_only: bool = False,
#     radius_km: Optional[float] = Query(None, gt=0, le=500),
#     destination_latitude: Optional[float] = Query(None, ge=-90, le=90),
#     destination_longitude: Optional[float] = Query(None, ge=-180, le=180),
#     user_payload: Optional[dict] = Depends(get_current_user_from_header)
# ):
#     requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF"})
#     if blood_group and blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#     if availability_level and availability_level.upper() not in {"ALL", "HIGH", "MEDIUM", "LOW"}:
#         raise HTTPException(status_code=422, detail="Availability level must be All, High, Medium, or Low.")
#     if (destination_latitude is None) != (destination_longitude is None):
#         raise HTTPException(status_code=422, detail="Provide both destination coordinates.")
#     if radius_km is not None and not valid_coordinates(destination_latitude, destination_longitude):
#         raise HTTPException(status_code=422, detail="A radius filter requires valid destination coordinates.")
#
#     conn = get_db_connection()
#     try:
#         catalogue = get_location_catalog_data(conn)
#         district_values = {str(value).casefold(): value for value in catalogue["districts"]}
#         selected_district = district_values.get((district or "").strip().casefold()) if district and district.lower() != "all" else None
#         if district and district.lower() != "all" and not selected_district:
#             raise HTTPException(status_code=422, detail="Unknown district; choose a value from the location catalog.")
#         if taluk and taluk.lower() != "all":
#             if not selected_district or taluk.strip().casefold() not in {str(value).casefold() for value in catalogue["taluks_by_district"].get(selected_district, [])}:
#                 raise HTTPException(status_code=422, detail="The selected taluk does not belong to the selected district.")
#         clauses = ["1=1"]
#         params = []
#         if eligible_only:
#             clauses.extend([
#                 "COALESCE(is_available,0) = 1", "COALESCE(age,0) BETWEEN 18 AND 65", "COALESCE(health_score,0) >= 60",
#                 "COALESCE(last_donation_days,0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END",
#                 "UPPER(COALESCE(consent,'')) IN ('OPTED_IN','TRUE','YES','1')"
#             ])
#         if blood_group:
#             clauses.append("UPPER(blood_group) = UPPER(?)")
#             params.append(blood_group)
#         if district and district.lower() != "all":
#             clauses.append("LOWER(TRIM(district)) = LOWER(TRIM(?))")
#             params.append(district)
#         if taluk and taluk.lower() != "all":
#             clauses.append("LOWER(TRIM(taluk)) = LOWER(TRIM(?))")
#             params.append(taluk)
#         if availability_level and availability_level.upper() != "ALL":
#             if availability_level.upper() == "HIGH":
#                 clauses.append("availability_score IS NOT NULL AND availability_score >= 75")
#             elif availability_level.upper() == "MEDIUM":
#                 clauses.append("availability_score IS NOT NULL AND availability_score >= 40 AND availability_score < 75")
#             else:
#                 clauses.append("availability_score IS NOT NULL AND availability_score < 40")
#         rows = [dict(row) for row in conn.execute("SELECT * FROM donors WHERE " + " AND ".join(clauses), tuple(params)).fetchall()]
#     finally:
#         conn.close()
#
#     results = []
#     for donor in rows:
#         lat, lon = donor.get("latitude"), donor.get("longitude")
#         distance = None
#         if valid_coordinates(lat, lon) and valid_coordinates(destination_latitude, destination_longitude):
#             distance = round(haversine_distance_km(float(lat), float(lon), float(destination_latitude), float(destination_longitude)), 2)
#         if radius_km is not None and (distance is None or distance > radius_km):
#             continue
#         # Return only fields needed for dispatch. Precise coordinates and private address fields stay server-side.
#         result = {
#             "id": donor["id"], "donor_id": donor["donor_id"], "name": donor["name"],
#             "blood_group": donor["blood_group"], "age": donor["age"], "gender": donor.get("gender"),
#             "location": donor.get("location"), "district": donor.get("district"), "taluk": donor.get("taluk"),
#             "availability_status": donor.get("availability_status"), "availability_score": donor.get("availability_score"),
#             "last_donation_date": donor.get("last_donation_date"), "last_donation_days": donor.get("last_donation_days"),
#             "total_donations": donor.get("total_donations"), "donation_frequency": donor.get("donation_frequency"),
#             "previous_response_rate": donor.get("previous_response_rate"), "health_score": donor.get("health_score"),
#             "distance_km": distance, "distance_available": distance is not None, "is_available": bool(donor.get("is_available"))
#         }
#         # Admin donor directory needs contact details; hospital/staff matching views do not.
#         # Emergency alerts are sent server-side, so these roles need no donor email or phone.
#         if requester["role"] == "ROLE_ADMIN":
#             result["email"] = donor["email"]
#             result["phone"] = donor.get("phone")
#         results.append(result)
#     if valid_coordinates(destination_latitude, destination_longitude):
#         results.sort(key=lambda item: (item["distance_km"] is None, item["distance_km"] if item["distance_km"] is not None else float("inf"), -(item["availability_score"] or 0)))
#     else:
#         results.sort(key=lambda item: (-(item["availability_score"] or 0), item["donor_id"]))
#     return results
#
# @app.delete("/api/v1/donors/{donor_id}")
# def delete_donor(donor_id: str, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN"})
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("DELETE FROM donors WHERE id = ? OR donor_id = ? OR email = ?;", (donor_id, donor_id, donor_id))
#     conn.commit()
#     count = cursor.rowcount
#     conn.close()
#     if count == 0:
#         raise HTTPException(status_code=404, detail="Donor not found.")
#     return {"success": True, "message": f"Donor {donor_id} deleted."}
#
# @app.get("/api/v1/inventory")
# def get_inventory(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF"})
#     conn = get_db_connection()
#     try:
#         rows = [dict(r) for r in conn.execute("SELECT * FROM blood_inventory ORDER BY id ASC").fetchall()]
#         return rows
#     finally:
#         conn.close()
#
#
# @app.post("/api/v1/inventory")
# def add_inventory(req: InventoryCreateRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
#     blood_group = req.blood_group.strip().upper()
#     component_type = (req.component_type or "Whole Blood").strip()
#     if blood_group not in VALID_BLOOD_GROUPS:
#         raise HTTPException(status_code=422, detail="Unsupported blood group.")
#     if component_type not in SUPPORTED_COMPONENT_TYPES:
#         raise HTTPException(status_code=422, detail="Unsupported inventory component type.")
#     if req.units_available <= 0:
#         raise HTTPException(status_code=422, detail="Units to add must be greater than zero.")
#     if req.expiry_date:
#         try:
#             parsed_expiry = datetime.strptime(req.expiry_date, "%Y-%m-%d").date()
#         except ValueError:
#             raise HTTPException(status_code=422, detail="Expiry date must use YYYY-MM-DD format.")
#         if parsed_expiry < datetime.now().date():
#             raise HTTPException(status_code=422, detail="New stock expiry date cannot be in the past.")
#
#     conn = get_db_connection()
#     try:
#         conn.execute("BEGIN IMMEDIATE")
#         duplicate = conn.execute("SELECT * FROM inventory_additions WHERE idempotency_key = ?", (req.idempotency_key,)).fetchone()
#         if duplicate:
#             item = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (duplicate["blood_group"],)).fetchone()
#             conn.commit()
#             return {"success": True, "persisted": True, "duplicate": True, "message": "This stock addition was already applied.", "item": dict(item) if item else None}
#
#         existing = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (blood_group,)).fetchone()
#         if existing:
#             inventory_id = existing["id"]
#             conn.execute("""
#                 UPDATE blood_inventory
#                 SET units_available = units_available + ?,
#                     component_type = ?,
#                     status = CASE WHEN units_available + ? > 10 THEN 'AVAILABLE' ELSE 'LOW_STOCK' END
#                 WHERE id = ?
#             """, (req.units_available, component_type, req.units_available, inventory_id))
#         else:
#             if not req.expiry_date:
#                 raise HTTPException(status_code=422, detail="Expiry date is required when creating a new inventory blood-group record.")
#             status = "AVAILABLE" if req.units_available > 10 else "LOW_STOCK"
#             cursor = conn.execute("""
#                 INSERT INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status)
#                 VALUES (?, ?, ?, ?, ?)
#             """, (blood_group, component_type, req.units_available, req.expiry_date, status))
#             inventory_id = cursor.lastrowid
#         conn.execute("""
#             INSERT INTO inventory_additions (idempotency_key, inventory_id, blood_group, component_type, quantity, created_by_user_id, created_at)
#             VALUES (?, ?, ?, ?, ?, ?, ?)
#         """, (req.idempotency_key, inventory_id, blood_group, component_type, req.units_available, requester["id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
#         item = conn.execute("SELECT * FROM blood_inventory WHERE id = ?", (inventory_id,)).fetchone()
#         conn.commit()
#         return {"success": True, "persisted": True, "duplicate": False, "message": f"Stock updated for {blood_group}.", "item": dict(item)}
#     except HTTPException:
#         conn.rollback()
#         raise
#     except sqlite3.IntegrityError:
#         conn.rollback()
#         previous = conn.execute("SELECT * FROM inventory_additions WHERE idempotency_key = ?", (req.idempotency_key,)).fetchone()
#         if previous:
#             item = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (previous["blood_group"],)).fetchone()
#             return {"success": True, "persisted": True, "duplicate": True, "message": "This stock addition was already applied.", "item": dict(item) if item else None}
#         raise HTTPException(status_code=409, detail="Stock addition conflicted with another operation; refresh and retry with a new request key.")
#     finally:
#         conn.close()
#
#
# @app.delete("/api/v1/inventory/{item_id}")
# def delete_inventory(item_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
#     require_roles(user_payload, {"ROLE_ADMIN"})
#     conn = get_db_connection()
#     try:
#         cursor = conn.execute("DELETE FROM blood_inventory WHERE id = ?", (item_id,))
#         conn.commit()
#         if not cursor.rowcount:
#             raise HTTPException(status_code=404, detail="Inventory item not found.")
#         return {"success": True, "message": f"Inventory item {item_id} deleted."}
#     finally:
#         conn.close()
#
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)

import os
import json
import sqlite3
import smtplib
import secrets
import hashlib
import hmac
import math
import re
import shutil
import urllib.request
import urllib.error
import threading
from contextlib import asynccontextmanager
import time
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from dotenv import load_dotenv
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from email_service import (
    send_transactional_email, render_donor_emergency_email, render_acceptance_email,
    SubmissionResult, external_messages_enabled,
)
from migrations.email_notifications_20261023 import migrate as migrate_email_notification_schema

# Load environment variables
load_dotenv()

DB_FILE = os.getenv("BLOODBANK_DB_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bloodbank.db"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
_configured_jwt_secret = (os.getenv("JWT_SECRET") or "").strip()
_jwt_secret_is_placeholder = (
        len(_configured_jwt_secret) < 32
        or "change_me" in _configured_jwt_secret.lower()
        or "change-me" in _configured_jwt_secret.lower()
        or "replace-with" in _configured_jwt_secret.lower()
        or "your_secret" in _configured_jwt_secret.lower()
)
JWT_SECRET_CONFIGURED = not _jwt_secret_is_placeholder
JWT_SECRET = _configured_jwt_secret if JWT_SECRET_CONFIGURED else secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
EXTERNAL_MESSAGES_ENABLED = os.getenv("HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES", "true").strip().lower() not in {"1",
                                                                                                              "true",
                                                                                                              "yes"}
VALID_BLOOD_GROUPS = {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
SUPPORTED_COMPONENT_TYPES = {"Whole Blood"}
LOCATION_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "location_catalog.json")


def get_location_catalog_data(conn=None) -> dict:
    """Return one shared catalog, retaining valid selectable places even when no donor is registered there."""
    catalogue = {"districts": [], "taluks_by_district": {}}
    try:
        with open(LOCATION_CATALOG_PATH, "r", encoding="utf-8") as catalog_file:
            loaded = json.load(catalog_file)
        districts = loaded.get("districts", [])
        taluks_by_district = loaded.get("taluks_by_district", {})
        if isinstance(districts, list) and isinstance(taluks_by_district, dict):
            catalogue = {
                "districts": [str(value).strip() for value in districts if str(value).strip()],
                "taluks_by_district": {
                    str(key).strip(): [str(value).strip() for value in values if str(value).strip()]
                    for key, values in taluks_by_district.items() if isinstance(values, list) and str(key).strip()
                },
            }
    except (OSError, ValueError, TypeError):
        pass

    owned_connection = conn is None
    active_conn = conn or get_db_connection()
    try:
        pairs = active_conn.execute("""
            SELECT DISTINCT TRIM(district) AS district, TRIM(taluk) AS taluk
            FROM donors WHERE district IS NOT NULL AND TRIM(district) != ''
            ORDER BY district COLLATE NOCASE, taluk COLLATE NOCASE
        """).fetchall()
    finally:
        if owned_connection:
            active_conn.close()

    mapping = catalogue["taluks_by_district"]
    district_lookup = {str(name).casefold(): name for name in catalogue["districts"]}
    for row in pairs:
        district, taluk = row["district"], row["taluk"]
        if not district:
            continue
        canonical_district = district_lookup.get(district.casefold())
        if canonical_district is None:
            canonical_district = district
            catalogue["districts"].append(canonical_district)
            district_lookup[canonical_district.casefold()] = canonical_district
        mapping.setdefault(canonical_district, [])
        if taluk and taluk.casefold() not in {value.casefold() for value in mapping[canonical_district]}:
            mapping[canonical_district].append(taluk)

    catalogue["districts"] = sorted(set(catalogue["districts"]), key=str.casefold)
    for district in list(mapping):
        mapping[district] = sorted(set(mapping[district]), key=str.casefold)
    return catalogue


if not JWT_SECRET_CONFIGURED:
    print(
        "[SECURITY NOTICE] JWT_SECRET is missing, too short, or still a template placeholder; using an ephemeral development secret. Set a unique random secret of at least 32 characters to preserve sessions across restarts.")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_FROM = os.getenv("MAIL_FROM",
                      f"HaemoPulse Blood Bank <{SMTP_USER}>" if SMTP_USER else "HaemoPulse <no-reply@haemopulse.org>")
# Keep legacy SMTP verification sender separate from the Brevo transactional sender.
# Falling back to MAIL_FROM preserves compatibility with existing deployments that used one sender variable.
SMTP_MAIL_FROM = os.getenv("SMTP_MAIL_FROM", MAIL_FROM)


def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def hash_password(password: str) -> str:
    """Hash new passwords with salted PBKDF2; supports stdlib-only deployments."""
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_value: str) -> tuple[bool, bool]:
    """Return (valid, needs_rehash), including legacy SHA-256/plain formats."""
    if not stored_value:
        return False, False
    if stored_value.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_hex, digest_hex = stored_value.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            ).hex()
            valid = hmac.compare_digest(candidate, digest_hex)
            return valid, bool(valid and int(iterations) < 310_000)
        except (ValueError, TypeError):
            return False, False
    # Keep older accounts usable and transparently upgrade their password hashes after login.
    legacy_sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(legacy_sha, stored_value):
        return True, True
    if hmac.compare_digest(password, stored_value):
        return True, True
    return False, False


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres. Inputs must be validated first."""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    a = min(1.0, max(0.0, a))
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def valid_coordinates(latitude: Optional[float], longitude: Optional[float]) -> bool:
    return (
            latitude is not None and longitude is not None
            and math.isfinite(latitude) and math.isfinite(longitude)
            and -90 <= latitude <= 90 and -180 <= longitude <= 180
    )


def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def init_sqlite_db():
    # Back up an existing database before the donor-feature schema migration.
    if os.path.isfile(DB_FILE) and os.path.getsize(DB_FILE) > 0:
        needs_backup = False
        try:
            probe = sqlite3.connect(DB_FILE)
            table_names = {row[0] for row in
                           probe.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "donors" in table_names:
                donor_columns = {row[1] for row in probe.execute("PRAGMA table_info(donors)").fetchall()}
                needs_backup = "response_time_hrs" not in donor_columns
            if "emergency_request_responses" not in table_names:
                needs_backup = True
            probe.close()
        except sqlite3.Error:
            needs_backup = False
        if needs_backup:
            backup_path = DB_FILE + ".pre_donor_features_backup.sqlite3"
            if not os.path.exists(backup_path):
                shutil.copy2(DB_FILE, backup_path)
        # Take a dedicated backup before the email-notification schema migration.
        try:
            probe = sqlite3.connect(DB_FILE)
            table_names = {row[0] for row in probe.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            request_columns = {row[1] for row in probe.execute("PRAGMA table_info(blood_requests)").fetchall()} if "blood_requests" in table_names else set()
            notification_migration_needed = (
                "hospital_user_id" not in request_columns
                or "assigned_admin_user_id" not in request_columns
                or "notification_outbox" not in table_names
                or "notification_provider_events" not in table_names
            )
            probe.close()
            if notification_migration_needed:
                backup_path = DB_FILE + ".pre_email_notifications_backup.sqlite3"
                if os.path.exists(backup_path):
                    backup_path = (DB_FILE + ".pre_email_notifications_backup."
                                   + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(4) + ".sqlite3")
                source_db = sqlite3.connect(DB_FILE, timeout=10)
                try:
                    backup_db = sqlite3.connect(backup_path, timeout=10)
                    try:
                        # SQLite's online backup API includes committed/WAL content and is safer than copying a live DB file.
                        source_db.backup(backup_db)
                        backup_check = backup_db.execute("PRAGMA integrity_check").fetchone()[0]
                        if backup_check != "ok":
                            raise sqlite3.DatabaseError("The notification-migration backup failed integrity_check.")
                    finally:
                        backup_db.close()
                finally:
                    source_db.close()
                if not os.path.isfile(backup_path) or os.path.getsize(backup_path) == 0:
                    raise sqlite3.DatabaseError("The notification-migration backup file is missing or empty.")
        except sqlite3.Error as exc:
            # Fail closed: never apply the schema migration if a safe backup cannot be verified.
            raise RuntimeError(
                "Could not verify the SQLite backup required for the email-notification migration; "
                "database migration was aborted."
            ) from exc
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT NOT NULL,
        role TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0,
        verification_token TEXT,
        verification_token_expiry TEXT,
        last_verification_email_sent_at TEXT,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    # 2. Donors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        blood_group TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT DEFAULT 'Male',
        location TEXT NOT NULL,
        distance_km REAL DEFAULT 5.0,
        last_donation_days INTEGER DEFAULT 180,
        last_donation_date TEXT,
        total_donations INTEGER DEFAULT 0,
        donation_frequency INTEGER DEFAULT 2,
        previous_response_rate REAL DEFAULT 0.90,
        preferred_time TEXT DEFAULT 'Morning',
        health_score INTEGER DEFAULT 95,
        availability_status TEXT DEFAULT 'HIGH',
        availability_score REAL DEFAULT 91.5,
        is_available INTEGER DEFAULT 1
    );
    """)

    # 3. Blood Inventory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blood_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blood_group TEXT UNIQUE NOT NULL,
        component_type TEXT DEFAULT 'Whole Blood',
        units_available INTEGER DEFAULT 0,
        expiry_date TEXT NOT NULL,
        status TEXT DEFAULT 'AVAILABLE'
    );
    """)

    # 4. Blood Requests Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blood_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_name TEXT NOT NULL,
        hospital_address TEXT,
        contact_phone TEXT,
        blood_group TEXT NOT NULL,
        units_needed INTEGER NOT NULL,
        urgency_level TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        request_date TEXT NOT NULL,
        created_by_user_id INTEGER
    );
    """)

    # 5. Appointments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id TEXT,
        donor_name TEXT NOT NULL,
        donor_email TEXT,
        blood_group TEXT NOT NULL,
        appointment_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        center_name TEXT DEFAULT 'Central Blood Bank Hub #1',
        status TEXT DEFAULT 'SCHEDULED',
        created_at TEXT
    );
    """)

    # 6. Past Donations History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donation_code TEXT UNIQUE,
        donor_email TEXT NOT NULL,
        donor_name TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        units INTEGER DEFAULT 1,
        donation_date TEXT NOT NULL,
        center_name TEXT NOT NULL,
        status TEXT DEFAULT 'Verified'
    );
    """)

    # Minimal additive audit tables for idempotent stock additions and emergency alert outcomes.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_additions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key TEXT NOT NULL UNIQUE,
        inventory_id INTEGER,
        blood_group TEXT NOT NULL,
        component_type TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        created_by_user_id INTEGER,
        created_at TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key TEXT NOT NULL UNIQUE,
        request_id INTEGER,
        requested_by_user_id INTEGER NOT NULL,
        donor_id TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        hospital_name TEXT NOT NULL,
        urgency_level TEXT NOT NULL,
        patient_reference TEXT,
        delivery_status TEXT NOT NULL,
        email_configured INTEGER NOT NULL DEFAULT 0,
        delivered INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_request_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        donor_id TEXT NOT NULL,
        response TEXT NOT NULL CHECK(response IN ('ACCEPTED', 'REJECTED')),
        created_at TEXT NOT NULL,
        UNIQUE(request_id, donor_id),
        FOREIGN KEY(request_id) REFERENCES blood_requests(id)
    );
    """)
    conn.commit()

    # Database Schema Migrations for existing DB files (add missing columns safely)
    def add_col_if_missing(table, col, col_def):
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [c[1] for c in cursor.fetchall()]
        if col not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def};")

    add_col_if_missing("users", "is_verified", "INTEGER DEFAULT 0")
    add_col_if_missing("users", "verification_token", "TEXT")
    add_col_if_missing("users", "verification_token_expiry", "TEXT")
    add_col_if_missing("users", "last_verification_email_sent_at", "TEXT")

    add_col_if_missing("donors", "user_id", "INTEGER")
    add_col_if_missing("donors", "gender", "TEXT DEFAULT 'Male'")
    add_col_if_missing("donors", "last_donation_date", "TEXT")
    add_col_if_missing("donors", "is_available", "INTEGER DEFAULT 1")
    add_col_if_missing("donors", "dob", "TEXT")
    add_col_if_missing("donors", "phone", "TEXT")
    add_col_if_missing("donors", "district", "TEXT")
    add_col_if_missing("donors", "taluk", "TEXT")
    add_col_if_missing("donors", "fictional_address", "TEXT")
    add_col_if_missing("donors", "latitude", "REAL")
    add_col_if_missing("donors", "longitude", "REAL")
    add_col_if_missing("donors", "consent", "TEXT")
    add_col_if_missing("donors", "response_time_hrs", "REAL")

    add_col_if_missing("blood_requests", "hospital_address", "TEXT")
    add_col_if_missing("blood_requests", "contact_phone", "TEXT")
    add_col_if_missing("blood_requests", "created_by_user_id", "INTEGER")
    add_col_if_missing("blood_requests", "destination_latitude", "REAL")
    add_col_if_missing("blood_requests", "destination_longitude", "REAL")

    # Additive notification migration. Existing request assignments remain NULL; never infer them.
    migrate_email_notification_schema(conn)

    add_col_if_missing("appointments", "donor_id", "TEXT")
    add_col_if_missing("appointments", "donor_email", "TEXT")
    add_col_if_missing("appointments", "center_name", "TEXT DEFAULT 'Central Blood Bank Hub #1'")
    add_col_if_missing("appointments", "created_at", "TEXT")
    conn.commit()

    # Optional demo fixtures; never inject fictional records into a normal/production database.
    if os.getenv("HAEMOPULSE_ENABLE_DEMO_SEED", "false").strip().lower() in {"1", "true", "yes"}:
        cursor.execute("SELECT COUNT(*) FROM donors;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
            INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, distance_km, last_donation_days, last_donation_date, total_donations, donation_frequency, previous_response_rate, preferred_time, health_score, availability_status, availability_score, is_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
            """, [
                ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', 29, 'Male', 'Zone A (Central)', 3.5, 150,
                 '2026-03-15', 4, 3, 0.95, 'Morning', 98, 'HIGH', 94.5),
                ('DNR-1002', 'Sarah Jenkins', 'sarah.j@email.com', 'A-', 34, 'Female', 'Zone B (North)', 6.2, 125,
                 '2026-04-10', 6, 4, 0.88, 'Afternoon', 95, 'HIGH', 89.0),
                ('DNR-1003', 'Michael Brown', 'mbrown@email.com', 'B+', 42, 'Male', 'Zone A (Central)', 8.0, 24,
                 '2026-07-20', 2, 1, 0.40, 'Evening', 85, 'LOW', 35.0),
                ('DNR-1004', 'Emily Davis', 'emily.d@email.com', 'AB+', 25, 'Female', 'Zone C (South)', 12.5, 215,
                 '2026-01-12', 3, 2, 0.75, 'Morning', 92, 'MEDIUM', 68.5)
            ])
            conn.commit()

        # Demo-data mode deliberately does not seed login accounts or default credentials.
        # Provision management access with backend/create_role_user.py instead.

        cursor.execute("SELECT COUNT(*) FROM blood_inventory;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
            INSERT INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status)
            VALUES (?, ?, ?, ?, ?);
            """, [
                ('O+', 'Whole Blood', 45, '2026-09-15', 'AVAILABLE'),
                ('O-', 'Whole Blood', 8, '2026-09-01', 'LOW_STOCK'),
                ('A+', 'Whole Blood', 32, '2026-09-20', 'AVAILABLE'),
                ('A-', 'Whole Blood', 12, '2026-08-30', 'AVAILABLE'),
                ('B+', 'Whole Blood', 28, '2026-09-10', 'AVAILABLE'),
                ('B-', 'Whole Blood', 5, '2026-08-25', 'LOW_STOCK'),
                ('AB+', 'Whole Blood', 18, '2026-09-25', 'AVAILABLE'),
                ('AB-', 'Whole Blood', 4, '2026-08-28', 'LOW_STOCK')
            ])
            conn.commit()

        cursor.execute("SELECT COUNT(*) FROM blood_requests;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
            INSERT INTO blood_requests (hospital_name, hospital_address, contact_phone, blood_group, units_needed, urgency_level, patient_name, status, request_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                ('City General Hospital', '100 Healthcare Blvd, Suite 400', '+1-800-555-0101', 'O-', 4, 'EMERGENCY',
                 'Trauma Unit Patient #402', 'PENDING', '2026-08-13 08:30:00'),
                ('St. Jude Emergency Center', '450 Trauma Way, East Wing', '+1-800-555-0102', 'B-', 2, 'HIGH',
                 'Surgical Patient #109', 'APPROVED', '2026-08-12 14:15:00')
            ])
            conn.commit()

        cursor.execute("SELECT COUNT(*) FROM donations;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
            INSERT INTO donations (donation_code, donor_email, donor_name, blood_group, units, donation_date, center_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                ('DON-901', 'john.doe@email.com', 'John Doe', 'O+', 1, '2026-03-15', 'Central Blood Bank Hub #1',
                 'Verified'),
                ('DON-812', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-10-18', 'City General Blood Center',
                 'Verified'),
                ('DON-705', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-06-04', 'St. Jude Mobile Drive',
                 'Verified')
            ])
            conn.commit()

        cursor.execute("SELECT COUNT(*) FROM appointments;")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
            INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', '2026-10-20', 'Morning (8 AM - 12 PM)',
                 'Central Blood Bank Hub #1', 'SCHEDULED', '2026-10-10 10:00:00')
            ])
            conn.commit()

    conn.close()


# Initialize DB
init_sqlite_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the background notification worker with FastAPI's lifespan API."""
    start_notification_worker()
    try:
        yield
    finally:
        stop_notification_worker()


app = FastAPI(
    title="HaemoPulse Blood Bank API",
    description="Enterprise REST API with Real SMTP Email Verification, JWT Authentication, and ML Optimization",
    version="3.5.0",
    lifespan=lifespan,
)

_cors_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", f"{FRONTEND_URL},http://127.0.0.1:3000"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


# --- REAL SMTP EMAIL SERVICE ---
def send_real_verification_email(to_email: str, recipient_name: str, token: str) -> dict:
    verify_link = f"{FRONTEND_URL}/verify-email?token={token}"
    subject = "Verify Your HaemoPulse Donor Account"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 0; }}
        .container {{ max-width: 580px; margin: 30px auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #991b1b, #dc2626); padding: 32px 24px; text-align: center; }}
        .title {{ color: #ffffff; font-size: 24px; font-weight: 800; margin: 8px 0 0; }}
        .subtitle {{ color: #fecaca; font-size: 13px; margin: 4px 0 0; }}
        .content {{ padding: 32px 28px; line-height: 1.6; color: #cbd5e1; font-size: 14px; }}
        .btn {{ display: inline-block; background: #dc2626; color: #ffffff !important; font-weight: 700; font-size: 14px; text-decoration: none; padding: 14px 28px; border-radius: 10px; margin: 20px 0; text-align: center; }}
        .footer {{ padding: 20px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; background: #090d16; }}
        .card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin: 16px 0; font-size: 12px; color: #94a3b8; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div style="font-size: 36px;">🩸</div>
          <h1 class="title">HaemoPulse</h1>
          <p class="subtitle">Online Blood Bank & ML Availability Engine</p>
        </div>
        <div class="content">
          <h2 style="color: #ffffff; font-size: 18px; margin-top: 0;">Welcome, {recipient_name}!</h2>
          <p>Thank you for registering as a blood donor. Every donation helps save lives during critical medical emergencies.</p>
          <p>Please click the button below to verify your email address and activate all features of your Donor Portal:</p>
          <div style="text-align: center;">
            <a href="{verify_link}" class="btn">Verify My Email Address</a>
          </div>
          <div class="card">
            <strong>Link not working?</strong> Copy and paste this URL into your browser:<br>
            <a href="{verify_link}" style="color: #f87171; word-break: break-all;">{verify_link}</a>
          </div>
          <p style="font-size: 12px; color: #64748b;">This verification link will expire in 24 hours. If you did not create this account, please ignore this email.</p>
        </div>
        <div class="footer">
          &copy; 2026 HaemoPulse Blood Bank Management System. All rights reserved.
        </div>
      </div>
    </body>
    </html>
    """

    email_sent = False
    error_msg = None

    # External messages are opt-in; do not send mail in test or controlled environments.
    if EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = MAIL_FROM
            msg["To"] = to_email

            part = MIMEText(html_content, "html")
            msg.attach(part)

            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            email_sent = True
        except Exception as e:
            error_msg = str(e)
            print(f"[SMTP ERROR] Failed to send email via {SMTP_HOST}:{SMTP_PORT}: {e}")
    # Never print or return the raw verification token/link. The UI must report actual delivery state.
    return {
        "sent": email_sent,
        "recipient": to_email,
        "delivery_status": "DELIVERED" if email_sent else ("DISABLED" if not EXTERNAL_MESSAGES_ENABLED else (
            "NOT_CONFIGURED" if not (SMTP_USER and SMTP_PASS) else "FAILED")),
        "error": "Email delivery failed. Check SMTP configuration." if error_msg else None
    }


def send_emergency_alert_email(to_email: str, recipient_name: str, blood_group: str, hospital_name: str, urgency: str,
                               patient: str) -> dict:
    """Compatibility wrapper; patient detail is intentionally never included in donor email."""
    request = {"id": 0, "blood_group": blood_group, "hospital_name": hospital_name,
               "urgency_level": urgency, "units_needed": "Not specified", "hospital_address": "Not specified"}
    subject, text_content, html_content = render_donor_emergency_email(request, recipient_name)
    result = send_transactional_email(recipient_email=to_email, recipient_name=recipient_name,
                                      subject=subject, text_content=text_content, html_content=html_content)
    return {"sent": result.status == "SUBMITTED", "to": to_email,
            "delivery_status": result.status, "provider_message_id": result.provider_message_id,
            "error_code": result.error_code}


# --- PYDANTIC SCHEMAS ---
class RegisterDonorRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=256)
    phone: str = Field(..., min_length=6, max_length=32)
    blood_group: str
    age: int = Field(..., ge=18, le=65)
    gender: Optional[str] = "Male"
    location: str = Field(..., min_length=2, max_length=160)
    district: Optional[str] = None
    taluk: Optional[str] = None
    preferred_time: Optional[str] = "Morning"
    consent_to_emergency_alerts: bool = False


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateDonorProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    location: Optional[str] = None
    preferred_time: Optional[str] = None


class AvailabilityToggleRequest(BaseModel):
    is_available: bool


class BookAppointmentRequest(BaseModel):
    donor_id: Optional[str] = None
    donor_name: Optional[str] = None
    donor_email: Optional[str] = None
    blood_group: str
    appointment_date: str
    time_slot: str
    center_name: Optional[str] = "Central Blood Bank Hub #1"


class RequestCreateRequest(BaseModel):
    hospital_name: str = Field(..., min_length=2, max_length=160)
    hospital_address: str = Field(..., min_length=4, max_length=300)
    contact_phone: Optional[str] = Field("", max_length=32)
    blood_group: str
    units_needed: int = Field(..., ge=1, le=1000)
    urgency_level: str
    patient_name: str = Field(..., min_length=1, max_length=160)
    destination_latitude: Optional[float] = Field(None, ge=-90, le=90)
    destination_longitude: Optional[float] = Field(None, ge=-180, le=180)
    hospital_user_id: Optional[int] = Field(None, ge=1)
    assigned_admin_user_id: Optional[int] = Field(None, ge=1)


class EmergencyRequestResponse(BaseModel):
    action: str = Field(..., min_length=3, max_length=10)


class NotificationAssignmentsUpdate(BaseModel):
    hospital_user_id: Optional[int] = Field(None, ge=1)
    assigned_admin_user_id: Optional[int] = Field(None, ge=1)


class InventoryCreateRequest(BaseModel):
    blood_group: str
    units_available: int = Field(..., ge=1, le=10000)
    component_type: Optional[str] = "Whole Blood"
    expiry_date: Optional[str] = None
    idempotency_key: str = Field(..., min_length=8, max_length=128)


class ResendVerificationRequest(BaseModel):
    email: str


# Dependency to extract optional/required token user
def get_current_user_from_header(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    return decode_access_token(parts[1])


def require_roles(user_payload: Optional[dict], allowed_roles: set[str]) -> dict:
    if not user_payload or not user_payload.get("id"):
        raise HTTPException(status_code=401, detail="A valid authentication token is required.")
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id, role, status FROM users WHERE id = ?", (user_payload["id"],)).fetchone()
    finally:
        conn.close()
    if not row or (row["status"] or "ACTIVE").upper() != "ACTIVE":
        raise HTTPException(status_code=401, detail="The authenticated account is unavailable.")
    role = str(row["role"] or "").upper()
    if role not in allowed_roles or str(user_payload.get("role", "")).upper() != role:
        raise HTTPException(status_code=403, detail="Your account is not authorized to perform this action.")
    return {**user_payload, "role": role}


@app.get("/")
def home():
    return {
        "service": "HaemoPulse REST API Engine",
        "database": "SQLite Relational Database (bloodbank.db)",
        "smtp_configured": bool(EXTERNAL_MESSAGES_ENABLED and SMTP_USER and SMTP_PASS),
        "external_messages_enabled": EXTERNAL_MESSAGES_ENABLED,
        "status": "ONLINE"
    }


# ========================================================
# 1. AUTHENTICATION & EMAIL VERIFICATION
# ========================================================

@app.post("/api/v1/auth/register")
def register_donor(req: RegisterDonorRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    req_email = req.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", req_email):
        conn.close()
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if req.blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
        conn.close()
        raise HTTPException(status_code=422, detail="Unsupported blood group.")
    if req.gender and req.gender not in {"Male", "Female", "Other"}:
        conn.close()
        raise HTTPException(status_code=422, detail="Unsupported gender value.")
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email address already exists. Please log in.")

    # Generate 32-byte secure token for 24-hour verification
    raw_token = secrets.token_urlsafe(32)
    expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    now_iso = datetime.utcnow().isoformat()
    hashed_pwd = hash_password(req.password)

    # Public registration always creates a donor; submitted role fields are intentionally ignored.
    safe_name = req.name.strip()
    safe_phone = req.phone.strip()
    safe_location = req.location.strip()
    if not safe_name or not safe_phone or not safe_location:
        conn.close()
        raise HTTPException(status_code=422, detail="Name, phone, and location are required.")
    # District/taluk values are checked against the same catalogue returned by the location API.
    catalogue = get_location_catalog_data(conn)
    district_values = {str(value).casefold(): value for value in catalogue["districts"]}
    selected_district = district_values.get((req.district or "").strip().casefold()) if req.district else None
    if req.district and not selected_district:
        conn.close()
        raise HTTPException(status_code=422, detail="Select a valid district from the location catalog.")
    if req.taluk:
        valid_taluks = catalogue["taluks_by_district"].get(selected_district, []) if selected_district else []
        selected_taluk = {str(value).casefold(): value for value in valid_taluks}.get(req.taluk.strip().casefold())
        if not selected_taluk:
            conn.close()
            raise HTTPException(status_code=422, detail="Select a taluk belonging to the chosen district.")

    # Insert user with is_verified = 0
    cursor.execute("""
    INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry, last_verification_email_sent_at)
    VALUES (?, ?, ?, ?, 'ROLE_DONOR', 0, ?, ?, ?);
    """, (safe_name, req_email, hashed_pwd, safe_phone, raw_token, expiry, now_iso))

    user_id = cursor.lastrowid
    donor_id = f"DNR-{1000 + user_id}"

    # Insert donor profile
    cursor.execute("""
    INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location,
                        distance_km, last_donation_days, last_donation_date, total_donations,
                        donation_frequency, previous_response_rate, preferred_time, health_score,
                        availability_status, availability_score, is_available)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, 0, NULL, ?, NULL, NULL, NULL, 1);
    """, (donor_id, user_id, safe_name, req_email, req.blood_group.strip().upper(), req.age,
          req.gender or "Male", safe_location, req.preferred_time or "Morning"))
    cursor.execute("UPDATE donors SET district = ?, taluk = ?, phone = ?, consent = ? WHERE user_id = ?",
                   (req.district.strip() if req.district else None, req.taluk.strip() if req.taluk else None,
                    safe_phone, "OPTED_IN" if req.consent_to_emergency_alerts else "PENDING", user_id))

    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    new_user = dict(cursor.fetchone())
    for secret_field in ("password", "verification_token", "verification_token_expiry",
                         "last_verification_email_sent_at"):
        new_user.pop(secret_field, None)

    cursor.execute("SELECT * FROM donors WHERE user_id = ?;", (user_id,))
    new_donor = dict(cursor.fetchone())
    conn.close()

    # Send real email verification
    mail_result = send_real_verification_email(req_email, safe_name, raw_token)

    # Create JWT session token; role comes from the server, never from the request body.
    jwt_token = create_access_token({"sub": req_email, "id": user_id, "role": "ROLE_DONOR"})

    return {
        "message": "Registration successful. " + ("Verification email was delivered." if mail_result[
            "sent"] else f"Verification email status: {mail_result['delivery_status']}."),
        "token": jwt_token,
        "user": {
            **new_user,
            "donor_id": donor_id,
            "blood_group": req.blood_group,
            "is_verified": False,
            "role": "ROLE_DONOR"
        },
        "donor": new_donor,
        "email_delivery": mail_result
    }


@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    req_email = req.email.strip().lower()

    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
    user = cursor.fetchone()
    valid_password, needs_rehash = verify_password(req.password, user["password"] if user else "")

    if not user or not valid_password or (user["status"] or "ACTIVE").upper() != "ACTIVE":
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if needs_rehash:
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(req.password), user["id"]))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
        user = cursor.fetchone()

    user_dict = dict(user)
    for secret_field in ("password", "verification_token", "verification_token_expiry",
                         "last_verification_email_sent_at"):
        user_dict.pop(secret_field, None)

    # Attach donor profile if donor
    donor_profile = None
    if user_dict["role"] in ["ROLE_DONOR", "DONOR"]:
        cursor.execute("SELECT * FROM donors WHERE LOWER(email) = ? OR user_id = ?;", (req_email, user_dict["id"]))
        donor_row = cursor.fetchone()
        if donor_row:
            donor_profile = dict(donor_row)
            user_dict["donor_id"] = donor_profile["donor_id"]
            user_dict["blood_group"] = donor_profile["blood_group"]
            user_dict["is_available"] = bool(donor_profile.get("is_available", 1))

    conn.close()

    jwt_token = create_access_token({
        "sub": req_email,
        "id": user_dict["id"],
        "role": user_dict["role"]
    })

    return {
        "message": "Login successful",
        "token": jwt_token,
        "user": user_dict,
        "donor": donor_profile
    }


@app.get("/api/v1/auth/me")
def get_current_user_profile(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication token required or expired.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_payload["id"],))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    user_dict = dict(user)
    for secret_field in ("password", "verification_token", "verification_token_expiry",
                         "last_verification_email_sent_at"):
        user_dict.pop(secret_field, None)

    donor_profile = None
    if user_dict["role"] in ["ROLE_DONOR", "DONOR"]:
        cursor.execute(
            "SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1;",
            (user_dict["id"], user_dict["email"].lower(), user_dict["id"]))
        d = cursor.fetchone()
        if d:
            donor_profile = dict(d)
            user_dict["donor_id"] = donor_profile["donor_id"]
            user_dict["blood_group"] = donor_profile["blood_group"]
            user_dict["is_available"] = bool(donor_profile.get("is_available", 1))

    conn.close()
    return {"user": user_dict, "donor": donor_profile}


@app.get("/api/v1/auth/verify-email")
@app.post("/api/v1/auth/verify-email")
def verify_email(token: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE verification_token = ?;", (token,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid verification token. It may have already been used.")

    user_dict = dict(user)
    expiry_str = user_dict.get("verification_token_expiry")
    if expiry_str:
        try:
            exp_dt = datetime.fromisoformat(expiry_str)
        except ValueError:
            conn.close()
            raise HTTPException(status_code=400, detail="Verification token is invalid.")
        if datetime.utcnow() > exp_dt:
            conn.close()
            raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")

    # Mark as verified and invalidate token
    cursor.execute("""
    UPDATE users 
    SET is_verified = 1, verification_token = NULL, verification_token_expiry = NULL 
    WHERE id = ?;
    """, (user_dict["id"],))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Your email has been successfully verified! All donor portal features are now unlocked.",
        "email": user_dict["email"]
    }


@app.post("/api/v1/auth/resend-verification")
def resend_verification_email(req: ResendVerificationRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    req_email = req.email.strip().lower()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="No account found with this email.")

    if user["is_verified"] == 1:
        conn.close()
        return {"message": "This email address is already verified.", "already_verified": True}

    # 60 seconds rate limit check
    last_sent = user["last_verification_email_sent_at"]
    if last_sent:
        try:
            last_dt = datetime.fromisoformat(last_sent)
            seconds_diff = (datetime.utcnow() - last_dt).total_seconds()
            if seconds_diff < 60:
                conn.close()
                wait_left = int(60 - seconds_diff)
                raise HTTPException(status_code=429,
                                    detail=f"Please wait {wait_left} seconds before requesting another email.")
        except HTTPException:
            raise
        except Exception:
            pass

    new_token = secrets.token_urlsafe(32)
    new_expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    now_iso = datetime.utcnow().isoformat()

    cursor.execute("""
    UPDATE users
    SET verification_token = ?, verification_token_expiry = ?, last_verification_email_sent_at = ?
    WHERE id = ?;
    """, (new_token, new_expiry, now_iso, user["id"]))
    conn.commit()
    conn.close()

    res = send_real_verification_email(req_email, user["name"], new_token)
    return {
        "success": bool(res["sent"]),
        "message": (f"Verification email delivered to {req_email}." if res[
            "sent"] else f"Verification email was not delivered ({res['delivery_status']})."),
        "delivery": {"sent": res["sent"], "delivery_status": res["delivery_status"]}
    }


# ========================================================
# 2. DONOR DASHBOARD & PROFILE MANAGEMENT
# ========================================================

@app.get("/api/v1/donors/me")
def get_my_donor_dashboard(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_payload["id"],))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    user = dict(user_row)
    if str(user.get("role", "")).upper() not in {"ROLE_DONOR", "DONOR"}:
        conn.close()
        raise HTTPException(status_code=403, detail="A donor account is required to view this profile.")
    cursor.execute("SELECT * FROM donors WHERE user_id = ? ORDER BY id LIMIT 1;", (user["id"],))
    donor_row = cursor.fetchone()
    if not donor_row:
        cursor.execute("SELECT * FROM donors WHERE user_id IS NULL AND LOWER(email) = ? ORDER BY id LIMIT 1;",
                       (user["email"].lower(),))
        donor_row = cursor.fetchone()
    if not donor_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor profile not found.")

    donor = dict(donor_row)

    # Fetch recorded donations; only verified donation records count toward the donor total.
    cursor.execute("SELECT * FROM donations WHERE LOWER(donor_email) = ? ORDER BY donation_date DESC;",
                   (user["email"].lower(),))
    donations = [dict(r) for r in cursor.fetchall()]
    verified_donation_count = cursor.execute(
        "SELECT COUNT(*) FROM donations WHERE LOWER(donor_email) = LOWER(?) AND UPPER(TRIM(COALESCE(status, ''))) IN ('VERIFIED', 'VERIFIED_COMPLETED')",
        (user["email"],)).fetchone()[0]

    # Fetch donor appointments
    cursor.execute(
        "SELECT * FROM appointments WHERE LOWER(donor_email) = ? OR (donor_id = ? AND (donor_email IS NULL OR LOWER(donor_email) = ?)) ORDER BY appointment_date DESC;",
        (user["email"].lower(), donor["donor_id"], user["email"].lower()))
    appointments = [dict(r) for r in cursor.fetchall()]

    # Fetch matching emergency requests for notifications
    cursor.execute("""
        SELECT id, blood_group, units_needed, urgency_level, status, request_date,
               hospital_name, 'Emergency blood request' AS patient_name
        FROM blood_requests WHERE UPPER(blood_group) = UPPER(?) AND status = 'PENDING'
        ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC
    """, (donor["blood_group"],))
    notifications = [dict(r) for r in cursor.fetchall()]

    conn.close()

    # Calculate eligibility (Male: 90 days, Female: 120 days)
    last_days = donor.get("last_donation_days")
    gender = donor.get("gender") or "Unknown"
    required_gap = 120 if str(gender).lower() == "female" else 90
    is_eligible = last_days is not None and int(last_days) >= required_gap
    days_until_eligible = max(0, required_gap - int(last_days)) if last_days is not None else None

    return {
        "donor": donor,
        "user": {
            "name": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "is_verified": bool(user["is_verified"])
        },
        "stats": {
            "total_donations": int(verified_donation_count),
            "last_donation_days": last_days,
            "last_donation_date": donor.get("last_donation_date"),
            "is_eligible": is_eligible,
            "required_gap": required_gap,
            "days_until_eligible": days_until_eligible,
            "availability_score": None,
            "availability_status": None,
            "is_available": bool(donor.get("is_available", 1))
        },
        "donations": donations,
        "appointments": appointments,
        "emergency_notifications": notifications
    }


@app.put("/api/v1/donors/me/availability")
def toggle_donor_availability(req: AvailabilityToggleRequest,
                              user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})

    conn = get_db_connection()
    cursor = conn.cursor()
    new_avail = 1 if req.is_available else 0

    cursor.execute("""
    UPDATE donors 
    SET is_available = ? 
    WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?);
    """, (new_avail, user_payload["id"], user_payload["sub"].lower()))
    conn.commit()
    conn.close()

    return {"success": True, "is_available": req.is_available, "message": "Availability status updated."}


@app.put("/api/v1/donors/me/profile")
def update_donor_profile(req: UpdateDonorProfileRequest,
                         user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user_payload = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update Users table
    if req.name or req.phone:
        updates = []
        vals = []
        if req.name:
            updates.append("name = ?")
            vals.append(req.name)
        if req.phone:
            updates.append("phone = ?")
            vals.append(req.phone)
        vals.append(user_payload["id"])
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?;", tuple(vals))

    # Update Donors table
    d_updates = []
    d_vals = []
    if req.name:
        d_updates.append("name = ?")
        d_vals.append(req.name)
    if req.age is not None:
        d_updates.append("age = ?")
        d_vals.append(req.age)
    if req.gender:
        d_updates.append("gender = ?")
        d_vals.append(req.gender)
    if req.blood_group:
        d_updates.append("blood_group = ?")
        d_vals.append(req.blood_group)
    if req.location:
        d_updates.append("location = ?")
        d_vals.append(req.location)
    if req.preferred_time:
        d_updates.append("preferred_time = ?")
        d_vals.append(req.preferred_time)
    if req.phone:
        d_updates.append("phone = ?")
        d_vals.append(req.phone.strip())

    if d_updates:
        d_vals.extend([user_payload["id"], user_payload.get("sub", "").lower()])
        cursor.execute(
            f"UPDATE donors SET {', '.join(d_updates)} WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?);",
            tuple(d_vals))

    conn.commit()
    cursor.execute(
        "SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = ?) ORDER BY id LIMIT 1;",
        (user_payload["id"], user_payload.get("sub", "").lower()))
    updated_row = cursor.fetchone()
    if not updated_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor profile not found.")
    updated_donor = dict(updated_row)
    conn.close()

    return {"success": True, "message": "Profile updated successfully.", "donor": updated_donor}


# ========================================================
# 3. APPOINTMENTS (Booking & Verification)
# ========================================================

@app.get("/api/v1/appointments")
def get_all_appointments(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF", "ROLE_DONOR"})
    conn = get_db_connection()
    try:
        if user["role"] in {"ROLE_DONOR", "DONOR"}:
            donor = conn.execute(
                "SELECT donor_id, email FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1",
                (user["id"], user.get("sub", ""), user["id"])).fetchone()
            if not donor:
                raise HTTPException(status_code=404, detail="Donor profile not found.")
            rows = conn.execute(
                "SELECT * FROM appointments WHERE LOWER(COALESCE(donor_email, '')) = LOWER(?) OR (donor_id = ? AND (donor_email IS NULL OR LOWER(donor_email) = LOWER(?))) ORDER BY appointment_date ASC, id ASC",
                (donor["email"], donor["donor_id"], donor["email"])).fetchall()
        else:
            rows = conn.execute("SELECT * FROM appointments ORDER BY appointment_date ASC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/api/v1/appointments")
def book_appointment(req: BookAppointmentRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
    conn = get_db_connection()
    try:
        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not user_row or (user_row["status"] or "ACTIVE").upper() != "ACTIVE":
            raise HTTPException(status_code=401, detail="The authenticated account is unavailable.")
        if not bool(user_row["is_verified"]):
            raise HTTPException(status_code=403,
                                detail="Please verify your email address to book blood donation appointments.")
        donor = conn.execute(
            "SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1",
            (user["id"], user.get("sub", ""), user["id"])).fetchone()
        if not donor:
            raise HTTPException(status_code=404, detail="Donor profile not found.")
        try:
            appointment_date = datetime.strptime(req.appointment_date, "%Y-%m-%d").date()
            if appointment_date < datetime.now().date():
                raise HTTPException(status_code=422, detail="Appointment date cannot be in the past.")
        except ValueError:
            raise HTTPException(status_code=422, detail="Appointment date must use YYYY-MM-DD format.")
        if not req.time_slot.strip() or len(req.time_slot) > 80:
            raise HTTPException(status_code=422, detail="Enter a valid appointment time slot.")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute("""
          INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
        """, (donor["donor_id"], donor["name"], user_row["email"].lower(), donor["blood_group"], req.appointment_date,
              req.time_slot.strip(), (req.center_name or "Central Blood Bank Hub #1").strip(), now_str))
        conn.commit()
        return {"success": True, "id": cursor.lastrowid,
                "message": f"Appointment booked for {req.appointment_date} ({req.time_slot})."}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.put("/api/v1/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: int, status: str = Query(...),
                              user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
    clean_status = status.strip().upper()
    if clean_status not in {"SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"}:
        raise HTTPException(status_code=422, detail="Status must be SCHEDULED, COMPLETED, CANCELLED, or NO_SHOW.")
    conn = get_db_connection()
    try:
        cursor = conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (clean_status, appointment_id))
        conn.commit()
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="Appointment not found.")
        row = conn.execute("SELECT id, status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        return {"success": True, "id": row["id"], "status": row["status"],
                "message": "Appointment status was persisted."}
    finally:
        conn.close()


# ========================================================
# Durable notification outbox helpers
# ========================================================

NOTIFICATION_MAX_ATTEMPTS = 6
NOTIFICATION_BATCH_SIZE = 20
NOTIFICATION_LEASE_SECONDS = 90
NOTIFICATION_WORKER_SLEEP_SECONDS = 2
_notification_stop_event = threading.Event()
_notification_worker_thread = None
_notification_worker_id = f"worker-{os.getpid()}-{secrets.token_hex(4)}"


def utc_now_text() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _eligible_linked_donors(conn, blood_group: str):
    """Reuse server-side eligibility and consent rules; only explicitly linked active/verified users."""
    return conn.execute("""
        SELECT d.donor_id, d.name AS donor_name, d.user_id, u.email AS recipient_email, u.name AS account_name
        FROM donors d
        JOIN users u ON u.id = d.user_id
        WHERE UPPER(TRIM(d.blood_group)) = ?
          AND COALESCE(d.is_available, 0) = 1
          AND COALESCE(d.age, 0) BETWEEN 18 AND 65
          AND COALESCE(d.health_score, 0) >= 60
          AND COALESCE(d.last_donation_days, 0) >= CASE WHEN LOWER(COALESCE(d.gender, '')) = 'female' THEN 120 ELSE 90 END
          AND UPPER(TRIM(COALESCE(d.consent, ''))) IN ('OPTED_IN', 'TRUE', 'YES', '1')
          AND UPPER(TRIM(COALESCE(u.status, 'ACTIVE'))) = 'ACTIVE'
          AND COALESCE(u.is_verified, 0) = 1
          AND UPPER(TRIM(u.role)) IN ('ROLE_DONOR', 'DONOR')
          AND TRIM(COALESCE(u.email, '')) != ''
          AND LOWER(TRIM(COALESCE(d.email, ''))) = LOWER(TRIM(COALESCE(u.email, '')))
        ORDER BY d.id
    """, (blood_group,)).fetchall()


def _insert_outbox_event(conn, *, event_key: str, event_type: str, request_id: int | None,
                         donor_id: str | None, recipient_user_id: int | None,
                         recipient_email: str | None, status: str = "PENDING", error_code: str | None = None):
    now = utc_now_text()
    conn.execute("""
        INSERT OR IGNORE INTO notification_outbox
        (event_key, event_type, request_id, donor_id, recipient_user_id, recipient_email,
         status, next_retry_at, last_error_code, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (event_key, event_type, request_id, donor_id, recipient_user_id,
          recipient_email, status, now if status == "PENDING" else None, error_code, now, now))
    return conn.execute("SELECT id, status FROM notification_outbox WHERE event_key = ?", (event_key,)).fetchone()


def _enqueue_emergency_request_notifications(conn, request_row) -> int:
    """Call within the request transaction. No radius is fabricated because requests have no radius field."""
    if str(request_row["urgency_level"] or "").upper() != "EMERGENCY":
        return 0
    donors = _eligible_linked_donors(conn, str(request_row["blood_group"]).upper())
    for donor in donors:
        _insert_outbox_event(
            conn,
            event_key=f"request-created:{request_row['id']}:donor:{donor['donor_id']}",
            event_type="DONOR_EMERGENCY_REQUEST",
            request_id=int(request_row["id"]), donor_id=str(donor["donor_id"]),
            recipient_user_id=int(donor["user_id"]), recipient_email=str(donor["recipient_email"]),
        )
    return len(donors)


def _active_assignment(conn, user_id, expected_role: str):
    if user_id is None:
        return None
    row = conn.execute("SELECT id, name, email, role, status, is_verified FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or str(row["status"] or "ACTIVE").upper() != "ACTIVE":
        return None
    allowed = {expected_role.upper(), expected_role.replace("ROLE_", "").upper()}
    if str(row["role"] or "").upper() not in allowed:
        return None
    if not str(row["email"] or "").strip() or "@" not in str(row["email"]):
        return None
    return row


def _enqueue_acceptance_notifications(conn, request_row, donor_row, accepted_at: str) -> None:
    """Create explicit routed events or NEEDS_REVIEW markers; never fall back to arbitrary users."""
    request_id = int(request_row["id"])
    donor_id = str(donor_row["donor_id"])
    routes = (
        ("HOSPITAL", request_row["hospital_user_id"] if "hospital_user_id" in request_row.keys() else None,
         "ROLE_HOSPITAL"),
        ("ADMIN", request_row["assigned_admin_user_id"] if "assigned_admin_user_id" in request_row.keys() else None,
         "ROLE_ADMIN"),
    )
    for recipient_kind, assigned_id, role in routes:
        account = _active_assignment(conn, assigned_id, role)
        missing_reason = None
        if assigned_id is None:
            missing_reason = f"MISSING_{recipient_kind}_ASSIGNMENT"
        elif account is None:
            missing_reason = f"INVALID_OR_INACTIVE_{recipient_kind}_ASSIGNMENT"
        event_key = f"acceptance:{request_id}:donor:{donor_id}:{recipient_kind.lower()}:{assigned_id or 'unassigned'}"
        event = _insert_outbox_event(
            conn, event_key=event_key,
            event_type=f"DONOR_ACCEPTANCE_{recipient_kind}", request_id=request_id,
            donor_id=donor_id, recipient_user_id=int(account["id"]) if account else (int(assigned_id) if assigned_id else None),
            recipient_email=str(account["email"]) if account else None,
            status="PENDING" if account else "NEEDS_REVIEW", error_code=missing_reason,
        )
        # A missing/inactive assignment can be repaired by an authorized admin; only reset
        # configuration-related failures, never an ambiguous provider send or stale lease.
        if account and event and event["status"] in {"NEEDS_REVIEW", "FAILED"}:
            existing = conn.execute("SELECT last_error_code, provider_message_id FROM notification_outbox WHERE event_key=?", (event_key,)).fetchone()
            repairable_errors = {"MISSING_HOSPITAL_ASSIGNMENT", "MISSING_ADMIN_ASSIGNMENT",
                                 "INVALID_OR_INACTIVE_HOSPITAL_ASSIGNMENT", "INVALID_OR_INACTIVE_ADMIN_ASSIGNMENT",
                                 "ASSIGNMENT_CHANGED"}
            if existing and existing["last_error_code"] in repairable_errors and not existing["provider_message_id"]:
                conn.execute("""UPDATE notification_outbox SET status='PENDING', recipient_user_id=?, recipient_email=?,
                    next_retry_at=?, last_error_code=NULL, updated_at=? WHERE event_key=?""",
                    (int(account["id"]), str(account["email"]), utc_now_text(), utc_now_text(), event_key))


def _claim_next_notification() -> dict | None:
    """Atomically claim one due event. Expired processing leases go to review to avoid blind duplicate sends."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = utc_now_text()
        conn.execute("""
            UPDATE notification_outbox
            SET status='NEEDS_REVIEW', claimed_by=NULL, claimed_at=NULL, claim_expires_at=NULL,
                last_error_code='STALE_CLAIM_REQUIRES_RECONCILIATION', updated_at=?
            WHERE status='PROCESSING' AND claim_expires_at IS NOT NULL AND claim_expires_at < ?
        """, (now, now))
        row = conn.execute("""
            SELECT * FROM notification_outbox
            WHERE status IN ('PENDING','RETRY') AND (next_retry_at IS NULL OR next_retry_at <= ?)
            ORDER BY created_at, id LIMIT 1
        """, (now,)).fetchone()
        if not row:
            conn.commit()
            return None
        lease_until = (datetime.fromisoformat(now) + timedelta(seconds=NOTIFICATION_LEASE_SECONDS)).replace(microsecond=0).isoformat()
        updated = conn.execute("""
            UPDATE notification_outbox
            SET status='PROCESSING', attempt_count=attempt_count+1, claimed_by=?, claimed_at=?,
                claim_expires_at=?, updated_at=?
            WHERE id=? AND status IN ('PENDING','RETRY')
        """, (_notification_worker_id, now, lease_until, now, row["id"]))
        if updated.rowcount != 1:
            conn.rollback()
            return None
        claimed = conn.execute("SELECT * FROM notification_outbox WHERE id = ?", (row["id"],)).fetchone()
        conn.commit()
        return dict(claimed)
    finally:
        conn.close()


def _load_notification_context(conn, event: dict):
    request = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (event["request_id"],)).fetchone() if event.get("request_id") else None
    if not request:
        return None
    request_data = dict(request)
    recipient = conn.execute("SELECT id, name, email, phone, role, status, is_verified FROM users WHERE id = ?", (event.get("recipient_user_id"),)).fetchone() if event.get("recipient_user_id") else None
    donor = None
    if event.get("donor_id"):
        donor = conn.execute("SELECT donor_id, user_id, name, email, phone, blood_group, age, gender, is_available, last_donation_days, health_score, consent FROM donors WHERE donor_id = ?", (event["donor_id"],)).fetchone()

    def account_current(expected_role: str) -> bool:
        return bool(recipient
            and str(recipient["status"] or "ACTIVE").upper() == "ACTIVE"
            and str(recipient["role"] or "").upper() in {expected_role.upper(), expected_role.replace("ROLE_", "").upper()}
            and str(recipient["email"] or "").strip()
            and str(recipient["email"]).strip().lower() == str(event.get("recipient_email") or "").strip().lower())

    if event["event_type"] in {"DONOR_EMERGENCY_REQUEST", "MANUAL_DONOR_ALERT"}:
        if not account_current("ROLE_DONOR") or not bool(recipient["is_verified"]) or not donor:
            return None
        if int(donor["user_id"] or 0) != int(recipient["id"]):
            return None
        required_gap = 120 if str(donor["gender"] or "").lower() == "female" else 90
        if (str(donor["email"] or "").strip().lower() != str(recipient["email"]).strip().lower()
                or str(donor["blood_group"] or "").upper() != str(request_data["blood_group"] or "").upper()
                or not bool(donor["is_available"]) or int(donor["age"] or 0) < 18 or int(donor["age"] or 0) > 65
                or int(donor["last_donation_days"] or 0) < required_gap or int(donor["health_score"] or 0) < 60
                or str(donor["consent"] or "").strip().upper() not in {"OPTED_IN", "TRUE", "YES", "1"}
                or str(request_data["urgency_level"] or "").upper() != "EMERGENCY"
                or str(request_data["status"] or "").upper() not in {"PENDING", "APPROVED"}):
            return None
        subject, text_body, html_body = render_donor_emergency_email(request_data, recipient["name"])
        return str(event["recipient_email"]), str(recipient["name"]), subject, text_body, html_body

    if event["event_type"] in {"DONOR_ACCEPTANCE_HOSPITAL", "DONOR_ACCEPTANCE_ADMIN"}:
        if not donor:
            return None
        kind = "HOSPITAL" if event["event_type"].endswith("HOSPITAL") else "ADMIN"
        expected_role = "ROLE_HOSPITAL" if kind == "HOSPITAL" else "ROLE_ADMIN"
        assigned_field = "hospital_user_id" if kind == "HOSPITAL" else "assigned_admin_user_id"
        if not account_current(expected_role) or int(request_data.get(assigned_field) or 0) != int(recipient["id"]):
            return None
        response = conn.execute("SELECT created_at FROM emergency_request_responses WHERE request_id=? AND donor_id=? AND response='ACCEPTED'", (event["request_id"], event["donor_id"])).fetchone()
        if not response:
            return None
        donor_data = dict(donor)
        donor_data["accepted_at"] = response["created_at"]
        subject, text_body, html_body = render_acceptance_email(request_data, donor_data, kind)
        return str(event["recipient_email"]), str(recipient["name"]), subject, text_body, html_body
    return None


def process_notification_batch(*, sender=None, limit: int = NOTIFICATION_BATCH_SIZE) -> int:
    """Process due events. `sender` is injectable for tests; no call occurs while external sending is disabled."""
    if not EXTERNAL_MESSAGES_ENABLED:
        return 0
    sender = sender or send_transactional_email
    processed = 0
    for _ in range(max(1, min(int(limit), 100))):
        event = _claim_next_notification()
        if not event:
            break
        processed += 1
        conn = get_db_connection()
        try:
            context = _load_notification_context(conn, event)
        finally:
            conn.close()
        now = utc_now_text()
        if not context or not event.get("recipient_email"):
            result = SubmissionResult("NEEDS_REVIEW", error_code="RECIPIENT_OR_CONTEXT_UNAVAILABLE")
        else:
            email, name, subject, text_body, html_body = context
            result = sender(recipient_email=email, recipient_name=name, subject=subject,
                            text_content=text_body, html_content=html_body, timeout_seconds=10)
        update = get_db_connection()
        try:
            update.execute("BEGIN IMMEDIATE")
            attempt_count = int(event.get("attempt_count") or 1)
            status = result.status
            next_retry = None
            error_code = result.error_code
            submitted_at = None
            delivered_at = None
            if status == "SUBMITTED":
                submitted_at = now
                error_code = None
            elif status == "RETRY":
                if attempt_count >= NOTIFICATION_MAX_ATTEMPTS:
                    status = "FAILED"
                    error_code = error_code or "RETRY_LIMIT_REACHED"
                else:
                    # Bounded exponential backoff with jitter. Quota responses wait longer by default,
                    # and a provider Retry-After value is treated as a minimum delay (capped at 24h).
                    if error_code == "HTTP_429":
                        delay = min(86400, 3600 * (2 ** max(0, attempt_count - 1)))
                    else:
                        delay = min(3600, 30 * (2 ** max(0, attempt_count - 1)))
                    if result.retry_after_seconds is not None:
                        delay = max(delay, min(86400, max(1, int(result.retry_after_seconds))))
                    delay = min(86400, delay + random.randint(0, max(1, int(delay * 0.15))))
                    next_retry = (datetime.fromisoformat(now) + timedelta(seconds=delay)).replace(microsecond=0).isoformat()
            elif status == "DISABLED":
                # Preserve the pending event; enabling sending later will allow processing.
                status, next_retry = "PENDING", now
            update.execute("""
                UPDATE notification_outbox SET status=?, next_retry_at=?, provider_message_id=COALESCE(?, provider_message_id),
                  last_error_code=?, submitted_at=COALESCE(?, submitted_at), delivered_at=COALESCE(?, delivered_at),
                  claimed_by=NULL, claimed_at=NULL, claim_expires_at=NULL, updated_at=? WHERE id=? AND claimed_by=?
            """, (status, next_retry, result.provider_message_id, error_code, submitted_at, delivered_at,
                  now, event["id"], _notification_worker_id))
            if event["event_type"] == "MANUAL_DONOR_ALERT":
                prefix = "manual-alert:"
                idem_key = str(event.get("event_key") or "")[len(prefix):] if str(event.get("event_key") or "").startswith(prefix) else None
                if idem_key:
                    update.execute("""
                        UPDATE emergency_alerts SET delivery_status=?, email_configured=?, delivered=?
                        WHERE idempotency_key=?
                    """, (status, 1 if status in {"SUBMITTED", "DELIVERED"} else 0,
                          1 if status == "DELIVERED" else 0, idem_key))
            update.commit()
        except Exception:
            update.rollback()
            raise
        finally:
            update.close()
    return processed


def _notification_worker_loop():
    while not _notification_stop_event.is_set():
        try:
            process_notification_batch()
        except Exception as exc:
            # Log only the exception class, not request payloads, email addresses, or credentials.
            print(f"[notification-worker] processing error: {type(exc).__name__}")
        _notification_stop_event.wait(NOTIFICATION_WORKER_SLEEP_SECONDS)


def start_notification_worker():
    global _notification_worker_thread
    if EXTERNAL_MESSAGES_ENABLED and (_notification_worker_thread is None or not _notification_worker_thread.is_alive()):
        _notification_stop_event.clear()
        _notification_worker_thread = threading.Thread(target=_notification_worker_loop, name="haemopulse-notifications", daemon=True)
        _notification_worker_thread.start()


def stop_notification_worker():
    _notification_stop_event.set()
    if _notification_worker_thread and _notification_worker_thread.is_alive():
        _notification_worker_thread.join(timeout=2)


# ========================================================
# 4. HOSPITAL BLOOD REQUISITIONS & STAFF SYNC
# ========================================================

@app.get("/api/v1/requests")
def get_requests(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF", "ROLE_DONOR", "DONOR"})
    conn = get_db_connection()
    cursor = conn.cursor()
    if user["role"] in {"ROLE_DONOR", "DONOR"}:
        donor = cursor.execute(
            "SELECT blood_group FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1",
            (user["id"], user.get("sub", ""), user["id"])).fetchone()
        if not donor:
            conn.close()
            return []
        cursor.execute("""
            SELECT br.id, br.blood_group, br.units_needed, br.urgency_level, br.status, br.request_date,
                   br.hospital_name, 'Emergency blood request' AS patient_name,
                   br.hospital_address, NULL AS contact_phone,
                   br.destination_latitude, br.destination_longitude,
                   er.response AS donor_response
            FROM blood_requests br
            LEFT JOIN emergency_request_responses er ON er.request_id = br.id AND er.donor_id = (
                SELECT donor_id FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?))
                ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1
            )
            WHERE UPPER(br.blood_group) = UPPER(?) AND UPPER(br.status) IN ('PENDING', 'APPROVED')
            ORDER BY CASE WHEN br.urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, br.request_date DESC;
        """, (user["id"], user.get("sub", ""), user["id"], donor["blood_group"]))
    else:
        cursor.execute("""
        SELECT * FROM blood_requests
        ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC;
        """)
    rows = [dict(r) for r in cursor.fetchall()]
    if user["role"] not in {"ROLE_DONOR", "DONOR"}:
        for item in rows:
            counts = conn.execute(
                "SELECT status, COUNT(*) AS total FROM notification_outbox WHERE request_id=? GROUP BY status",
                (item["id"],),
            ).fetchall()
            item["notification_status"] = {entry["status"]: entry["total"] for entry in counts}
    conn.close()
    return rows


@app.get("/api/v1/notification-assignees")
def get_notification_assignees(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
    conn = get_db_connection()
    try:
        if user["role"] == "ROLE_ADMIN":
            hospitals = [dict(row) for row in conn.execute("SELECT id, name FROM users WHERE UPPER(role) IN ('ROLE_HOSPITAL','HOSPITAL') AND UPPER(COALESCE(status,'ACTIVE'))='ACTIVE' AND TRIM(COALESCE(email,'')) != '' ORDER BY name")]
        else:
            hospitals = []
        admins = [dict(row) for row in conn.execute("SELECT id, name FROM users WHERE UPPER(role) IN ('ROLE_ADMIN','ADMIN') AND UPPER(COALESCE(status,'ACTIVE'))='ACTIVE' AND TRIM(COALESCE(email,'')) != '' ORDER BY name")]
        return {"hospitals": hospitals, "admins": admins}
    finally:
        conn.close()


@app.get("/api/v1/donors/me/availability-score")
def get_my_availability_score(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    """Return a real ML prediction only when verified donation history and model inputs are available."""
    user = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
    conn = get_db_connection()
    try:
        donor = conn.execute(
            "SELECT * FROM donors WHERE user_id = ? OR (user_id IS NULL AND LOWER(email) = LOWER(?)) ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, id LIMIT 1",
            (user["id"], user.get("sub", ""), user["id"])).fetchone()
        if not donor:
            raise HTTPException(status_code=404, detail="Donor profile is unavailable.")
        donor = dict(donor)
        verified = conn.execute(
            "SELECT COUNT(*) AS n FROM donations WHERE LOWER(donor_email) = LOWER(?) AND UPPER(TRIM(COALESCE(status, ''))) IN ('VERIFIED', 'VERIFIED_COMPLETED')",
            (donor["email"],)).fetchone()["n"]
        if verified == 0:
            return {"eligible": False, "reason": "MISSING_DONATION_HISTORY", "completed_donations": None,
                    "required_donations": 3,
                    "message": "No verified completed donation history is recorded for this account yet. Your personalized score requires 3 verified completed blood donations."}
        if verified < 3:
            return {"eligible": False, "reason": "INSUFFICIENT_VERIFIED_DONATIONS",
                    "completed_donations": int(verified), "required_donations": 3,
                    "message": "Your personalized availability score will become available after 3 verified completed blood donations."}
        required = {
            "age": donor.get("age"), "gender": donor.get("gender"), "blood_group": donor.get("blood_group"),
            "location": donor.get("location"), "distance_km": donor.get("distance_km"),
            "last_donation_days": donor.get("last_donation_days"),
            "donation_frequency": donor.get("donation_frequency"),
            "previous_response_rate": donor.get("previous_response_rate"),
            "preferred_time": donor.get("preferred_time"),
            "response_time_hrs": donor.get("response_time_hrs"), "health_eligibility_score": donor.get("health_score")
        }
        missing = [key for key, value in required.items() if
                   value is None or (isinstance(value, str) and not value.strip())]
        if missing:
            return {"eligible": False, "reason": "MISSING_MODEL_INPUTS", "completed_donations": int(verified),
                    "required_donations": 3, "missing_fields": missing,
                    "message": "Your donation history meets the threshold, but required prediction information is not available yet."}
        try:
            payload = {"donor_id": str(donor["donor_id"]), **required}
            base = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8000").rstrip("/")
            request = urllib.request.Request(base + "/predict", data=json.dumps(payload).encode("utf-8"),
                                             headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=5) as response:
                prediction = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            raise HTTPException(status_code=503, detail="The availability prediction service is currently unavailable.")
        if not isinstance(prediction, dict) or not isinstance(prediction.get("availability_score"),
                                                              (int, float)) or not isinstance(
                prediction.get("availability_category"), str):
            raise HTTPException(status_code=502,
                                detail="The availability prediction service returned an invalid response.")
        return {"eligible": True, "completed_donations": int(verified), "required_donations": 3,
                "availability_score": prediction["availability_score"],
                "availability_status": prediction["availability_category"], "model_used": prediction.get("model_used")}
    finally:
        conn.close()


@app.post("/api/v1/requests/{request_id}/response")
def respond_to_emergency_request(request_id: int, req: EmergencyRequestResponse,
                                 user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_DONOR", "DONOR"})
    action = req.action.strip().upper()
    if action not in {"ACCEPT", "REJECT"}:
        raise HTTPException(status_code=422, detail="Action must be ACCEPT or REJECT.")
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        user_row = conn.execute("SELECT is_verified, status FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not user_row or not bool(user_row["is_verified"]):
            raise HTTPException(status_code=403, detail="Verify your email address before responding to emergency requests.")
        donor = conn.execute(
            "SELECT donor_id, user_id, name, email, phone, blood_group FROM donors WHERE user_id = ? ORDER BY id LIMIT 1",
            (user["id"],)).fetchone()
        if not donor:
            raise HTTPException(status_code=404, detail="An explicitly linked donor profile was not found for this account.")
        request_row = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (request_id,)).fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Emergency request not found.")
        if str(request_row["status"]).upper() not in {"PENDING", "APPROVED"}:
            raise HTTPException(status_code=409, detail="This emergency request is no longer open. Refresh the request list.")
        if str(request_row["blood_group"]).upper() != str(donor["blood_group"]).upper():
            raise HTTPException(status_code=403, detail="You are not eligible to respond to this blood-group request.")
        existing = conn.execute(
            "SELECT response FROM emergency_request_responses WHERE request_id = ? AND donor_id = ?",
            (request_id, donor["donor_id"])).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"You have already responded to this request ({existing['response'].lower()}).")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_value = "ACCEPTED" if action == "ACCEPT" else "REJECTED"
        conn.execute(
            "INSERT INTO emergency_request_responses (request_id, donor_id, response, created_at) VALUES (?, ?, ?, ?)",
            (request_id, donor["donor_id"], response_value, now))
        notification_count = 0
        needs_review_count = 0
        if response_value == "ACCEPTED" and str(request_row["urgency_level"] or "").upper() == "EMERGENCY":
            _enqueue_acceptance_notifications(conn, request_row, donor, now)
            rows = conn.execute("SELECT id, status FROM notification_outbox WHERE request_id=? AND donor_id=? AND event_type LIKE 'DONOR_ACCEPTANCE_%'", (request_id, donor["donor_id"])).fetchall()
            notification_count = sum(1 for row in rows if row["status"] in {"PENDING", "RETRY", "SUBMITTED", "DELIVERED"})
            needs_review_count = sum(1 for row in rows if row["status"] == "NEEDS_REVIEW")
        conn.commit()
        message = "Your response was recorded successfully."
        if response_value == "ACCEPTED" and needs_review_count:
            message += f" {needs_review_count} notification recipient assignment(s) need authorized review; your acceptance remains saved."
        return {"success": True, "request_id": request_id, "response": response_value,
                "notifications_queued": notification_count, "notifications_needing_review": needs_review_count,
                "message": message}
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="A response for this request has already been recorded.")
    finally:
        conn.close()


@app.post("/api/v1/requests")
def create_hospital_request(req: RequestCreateRequest,
                            user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
    blood_group = req.blood_group.strip().upper()
    urgency = req.urgency_level.strip().upper()
    if blood_group not in VALID_BLOOD_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported blood group.")
    if urgency not in {"EMERGENCY", "HIGH", "NORMAL"}:
        raise HTTPException(status_code=422, detail="Unsupported urgency level.")
    if (req.destination_latitude is None) != (req.destination_longitude is None):
        raise HTTPException(status_code=422, detail="Provide both destination latitude and longitude, or leave both blank.")

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        hospital_user_id = req.hospital_user_id
        if user["role"] == "ROLE_HOSPITAL":
            if hospital_user_id is not None and int(hospital_user_id) != int(user["id"]):
                raise HTTPException(status_code=403, detail="Hospital accounts may only link requests to their own account.")
            hospital_user_id = int(user["id"])
        elif urgency == "EMERGENCY" and hospital_user_id is None:
            raise HTTPException(status_code=422, detail="Select the responsible hospital account for an emergency request.")
        if hospital_user_id is not None:
            hospital = _active_assignment(conn, hospital_user_id, "ROLE_HOSPITAL")
            if not hospital:
                raise HTTPException(status_code=422, detail="Responsible hospital must be an active hospital account.")
        assigned_admin_id = req.assigned_admin_user_id
        if assigned_admin_id is not None and not _active_assignment(conn, assigned_admin_id, "ROLE_ADMIN"):
            raise HTTPException(status_code=422, detail="Assigned administrator must be an active admin account.")

        req_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute("""
            INSERT INTO blood_requests
              (hospital_name, hospital_address, contact_phone, blood_group, units_needed, urgency_level,
               patient_name, status, request_date, created_by_user_id, destination_latitude, destination_longitude,
               hospital_user_id, assigned_admin_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?)
        """, (req.hospital_name.strip(), req.hospital_address.strip(), (req.contact_phone or "").strip(),
              blood_group, req.units_needed, urgency, req.patient_name.strip(), req_date, user["id"],
              req.destination_latitude, req.destination_longitude, hospital_user_id, assigned_admin_id))
        new_id = cursor.lastrowid
        request_row = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (new_id,)).fetchone()
        queued_donors = _enqueue_emergency_request_notifications(conn, request_row)
        conn.commit()
        row = dict(conn.execute("SELECT * FROM blood_requests WHERE id = ?", (new_id,)).fetchone())
        row["notification_summary"] = {
            "eligible_donors": queued_donors,
            "status": "QUEUED" if queued_donors else ("NO_ELIGIBLE_DONORS" if urgency == "EMERGENCY" else "NOT_APPLICABLE"),
            "message": (f"Queued notifications for {queued_donors} eligible opted-in donor(s)." if queued_donors else
                        "No eligible, opted-in donors with active verified accounts were found." if urgency == "EMERGENCY" else
                        "Automatic donor notifications apply only to emergency requests."),
        }
        return row
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="The request could not be saved because of a data relationship conflict.")
    finally:
        conn.close()


@app.put("/api/v1/requests/{request_id}/notification-assignments")
def update_request_notification_assignments(
    request_id: int,
    req: NotificationAssignmentsUpdate,
    user_payload: Optional[dict] = Depends(get_current_user_from_header),
):
    user = require_roles(user_payload, {"ROLE_ADMIN"})
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        request_row = conn.execute("SELECT * FROM blood_requests WHERE id=?", (request_id,)).fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request not found.")
        if str(request_row["urgency_level"] or "").upper() == "EMERGENCY" and req.hospital_user_id is None:
            raise HTTPException(status_code=422, detail="Emergency requests must retain an explicitly assigned responsible hospital account.")
        if req.hospital_user_id is not None and not _active_assignment(conn, req.hospital_user_id, "ROLE_HOSPITAL"):
            raise HTTPException(status_code=422, detail="Responsible hospital must be an active hospital account.")
        if req.assigned_admin_user_id is not None and not _active_assignment(conn, req.assigned_admin_user_id, "ROLE_ADMIN"):
            raise HTTPException(status_code=422, detail="Assigned administrator must be an active admin account.")

        previous_hospital = request_row["hospital_user_id"]
        previous_admin = request_row["assigned_admin_user_id"]
        # Cancel not-yet-submitted events for a prior assignee. Submitted messages cannot be recalled.
        if previous_hospital != req.hospital_user_id:
            conn.execute("""UPDATE notification_outbox SET status='FAILED', last_error_code='ASSIGNMENT_CHANGED',
                next_retry_at=NULL, claimed_by=NULL, claimed_at=NULL, claim_expires_at=NULL, updated_at=?
                WHERE request_id=? AND event_type='DONOR_ACCEPTANCE_HOSPITAL' AND recipient_user_id IS NOT ?
                  AND status IN ('PENDING','RETRY','PROCESSING')""", (utc_now_text(), request_id, req.hospital_user_id))
        if previous_admin != req.assigned_admin_user_id:
            conn.execute("""UPDATE notification_outbox SET status='FAILED', last_error_code='ASSIGNMENT_CHANGED',
                next_retry_at=NULL, claimed_by=NULL, claimed_at=NULL, claim_expires_at=NULL, updated_at=?
                WHERE request_id=? AND event_type='DONOR_ACCEPTANCE_ADMIN' AND recipient_user_id IS NOT ?
                  AND status IN ('PENDING','RETRY','PROCESSING')""", (utc_now_text(), request_id, req.assigned_admin_user_id))
        conn.execute("UPDATE blood_requests SET hospital_user_id=?, assigned_admin_user_id=? WHERE id=?",
                     (req.hospital_user_id, req.assigned_admin_user_id, request_id))
        if req.hospital_user_id is not None:
            conn.execute("""UPDATE notification_outbox SET status='FAILED', last_error_code='ASSIGNMENT_RESOLVED_NO_SEND', updated_at=?
                WHERE request_id=? AND event_type='DONOR_ACCEPTANCE_HOSPITAL' AND recipient_user_id IS NULL
                  AND status='NEEDS_REVIEW' AND last_error_code='MISSING_HOSPITAL_ASSIGNMENT'""", (utc_now_text(), request_id))
        if req.assigned_admin_user_id is not None:
            conn.execute("""UPDATE notification_outbox SET status='FAILED', last_error_code='ASSIGNMENT_RESOLVED_NO_SEND', updated_at=?
                WHERE request_id=? AND event_type='DONOR_ACCEPTANCE_ADMIN' AND recipient_user_id IS NULL
                  AND status='NEEDS_REVIEW' AND last_error_code='MISSING_ADMIN_ASSIGNMENT'""", (utc_now_text(), request_id))
        updated_request = conn.execute("SELECT * FROM blood_requests WHERE id=?", (request_id,)).fetchone()
        accepted = conn.execute("SELECT donor_id, created_at FROM emergency_request_responses WHERE request_id=? AND response='ACCEPTED'", (request_id,)).fetchall()
        enqueued = 0
        for response_row in accepted:
            donor = conn.execute("SELECT donor_id, name, email, phone, blood_group, user_id FROM donors WHERE donor_id=?", (response_row["donor_id"],)).fetchone()
            if donor and str(updated_request["urgency_level"] or "").upper() == "EMERGENCY":
                _enqueue_acceptance_notifications(conn, updated_request, donor, response_row["created_at"])
                enqueued += 1
        conn.commit()
        return {"success": True, "request_id": request_id,
                "hospital_user_id": req.hospital_user_id, "assigned_admin_user_id": req.assigned_admin_user_id,
                "accepted_responses_checked": len(accepted),
                "message": f"Notification assignments saved. {enqueued} existing acceptance response(s) checked; only newly assigned recipients are queued."}
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="The notification assignment could not be saved.")
    finally:
        conn.close()


@app.put("/api/v1/requests/{request_id}/status")
def update_request_status(request_id: int, status: str = Query(...),
                          user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
    allowed_statuses = ["PENDING", "APPROVED", "ALLOCATED", "FULFILLED", "REJECTED"]
    clean_status = status.strip().upper()
    if clean_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {allowed_statuses}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE blood_requests SET status = ? WHERE id = ?;", (clean_status, request_id))
    conn.commit()
    found = cursor.rowcount
    conn.close()
    if not found:
        raise HTTPException(status_code=404, detail="Blood request not found.")

    return {"success": True, "message": f"Requisition #{request_id} status updated to {clean_status}."}


@app.delete("/api/v1/requests/{request_id}")
def delete_request(request_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN"})
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blood_requests WHERE id = ?;", (request_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Requisition #{request_id} deleted."}


# ========================================================
# 5. INVENTORY & DONORS GENERAL
# ========================================================

class DonorAlertEmailRequest(BaseModel):
    donor_id: str = Field(..., min_length=1, max_length=80)
    blood_group: str
    request_id: int
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    # Legacy fields are accepted for API transition but never trusted for recipient identity.
    donor_email: Optional[str] = None
    donor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    urgency: Optional[str] = "EMERGENCY"
    patient: Optional[str] = None


@app.post("/api/v1/donors/send-email-alert")
def send_donor_alert(req: DonorAlertEmailRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
    blood_group = req.blood_group.strip().upper()
    if blood_group not in VALID_BLOOD_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported blood group.")

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("SELECT * FROM emergency_alerts WHERE idempotency_key = ?", (req.idempotency_key,)).fetchone()
        if previous:
            queued = conn.execute("SELECT id, status FROM notification_outbox WHERE event_key = ?", (f"manual-alert:{req.idempotency_key}",)).fetchone()
            conn.commit()
            outbox_status = queued["status"] if queued else previous["delivery_status"]
            return {"accepted": True, "persisted": True, "queued": bool(queued), "delivered": outbox_status == "DELIVERED",
                    "delivery_status": outbox_status, "duplicate": True, "alert_id": previous["id"],
                    "donor_id": previous["donor_id"], "message": "This alert was already recorded; no second notification was created."}

        blood_request = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req.request_id,)).fetchone()
        if not blood_request:
            raise HTTPException(status_code=404, detail="Selected blood request was not found.")
        if str(blood_request["status"]).upper() != "PENDING":
            raise HTTPException(status_code=409, detail="Only pending blood requests can receive emergency alerts.")
        if str(blood_request["urgency_level"]).upper() != "EMERGENCY":
            raise HTTPException(status_code=422, detail="Select an emergency-level blood request before dispatching an alert.")
        if str(blood_request["blood_group"]).upper() != blood_group:
            raise HTTPException(status_code=422, detail="Alert blood group must match the selected blood request.")

        donor = conn.execute("""
            SELECT d.*, u.id AS linked_user_id, u.name AS account_name, u.email AS account_email,
                   u.status AS account_status, u.is_verified, u.role AS account_role
            FROM donors d LEFT JOIN users u ON u.id = d.user_id
            WHERE CAST(d.id AS TEXT) = ? OR d.donor_id = ? ORDER BY d.id LIMIT 1
        """, (req.donor_id, req.donor_id)).fetchone()
        if not donor:
            raise HTTPException(status_code=404, detail="Selected donor was not found.")
        if str(donor["blood_group"]).upper() != blood_group:
            raise HTTPException(status_code=422, detail="Selected donor blood group does not match the request.")
        if not bool(donor["is_available"]):
            raise HTTPException(status_code=409, detail="Selected donor is not currently marked available.")
        required_gap = 120 if str(donor["gender"] or "").lower() == "female" else 90
        if int(donor["age"] or 0) < 18 or int(donor["age"] or 0) > 65 or int(donor["last_donation_days"] or 0) < required_gap or int(donor["health_score"] or 0) < 60:
            raise HTTPException(status_code=409, detail="Selected donor does not meet the stored eligibility criteria.")
        if str(donor["consent"] or "").strip().upper() not in {"OPTED_IN", "TRUE", "YES", "1"}:
            raise HTTPException(status_code=409, detail="This donor has not explicitly opted in to emergency email alerts.")
        if not donor["linked_user_id"] or str(donor["account_status"] or "").upper() != "ACTIVE" or not bool(donor["is_verified"]) or str(donor["account_role"] or "").upper() not in {"ROLE_DONOR", "DONOR"} or str(donor["account_email"] or "").lower() != str(donor["email"] or "").lower():
            raise HTTPException(status_code=409, detail="Selected donor must be explicitly linked to an active, email-verified donor account.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute("""
            INSERT INTO emergency_alerts
              (idempotency_key, request_id, requested_by_user_id, donor_id, blood_group, hospital_name,
               urgency_level, patient_reference, delivery_status, email_configured, delivered, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'EMERGENCY', NULL, 'PENDING', 0, 0, ?)
        """, (req.idempotency_key, req.request_id, requester["id"], donor["donor_id"], blood_group,
              blood_request["hospital_name"], now))
        alert_id = cursor.lastrowid
        _insert_outbox_event(conn, event_key=f"manual-alert:{req.idempotency_key}", event_type="MANUAL_DONOR_ALERT",
                             request_id=req.request_id, donor_id=str(donor["donor_id"]),
                             recipient_user_id=int(donor["linked_user_id"]), recipient_email=str(donor["account_email"]))
        conn.commit()
        return {"accepted": True, "persisted": True, "queued": True, "delivered": False,
                "delivery_status": "PENDING", "duplicate": False, "alert_id": alert_id,
                "donor_id": donor["donor_id"],
                "message": "The emergency alert was saved and queued. External delivery remains disabled until configured and enabled."}
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Alert request conflicts with an existing operation.")
    finally:
        conn.close()


@app.get("/api/v1/notifications/requests/{request_id}")
def get_request_notification_status(request_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
    conn = get_db_connection()
    try:
        request_row = conn.execute("SELECT id, hospital_user_id FROM blood_requests WHERE id=?", (request_id,)).fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request not found.")
        if user["role"] == "ROLE_HOSPITAL" and request_row["hospital_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You can view notification state only for requests assigned to your hospital account.")
        rows = [dict(row) for row in conn.execute("""
            SELECT id, event_type, request_id, donor_id, status, attempt_count, next_retry_at,
                   provider_message_id, last_error_code, created_at, updated_at, submitted_at, delivered_at
            FROM notification_outbox WHERE request_id=? ORDER BY created_at, id
        """, (request_id,)).fetchall()]
        counts = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {"request_id": request_id, "counts": counts, "notifications": rows}
    finally:
        conn.close()


@app.post("/api/v1/notifications/{notification_id}/retry")
def retry_notification(notification_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    user = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL"})
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM notification_outbox WHERE id=?", (notification_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification event not found.")
        if user["role"] == "ROLE_HOSPITAL":
            request_row = conn.execute("SELECT hospital_user_id FROM blood_requests WHERE id=?", (row["request_id"],)).fetchone() if row["request_id"] else None
            if not request_row or request_row["hospital_user_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="Only the linked responsible hospital can retry this notification.")
        if row["status"] != "FAILED" or not str(row["last_error_code"] or "").startswith(("HTTP_429", "HTTP_408", "HTTP_425", "HTTP_5")):
            raise HTTPException(status_code=409, detail="Only exhausted transient provider failures may be retried. Ambiguous or permanent failures require reconciliation/configuration first.")
        now = utc_now_text()
        conn.execute("UPDATE notification_outbox SET status='PENDING', attempt_count=0, next_retry_at=?, last_error_code=NULL, updated_at=? WHERE id=?",
                     (now, now, notification_id))
        conn.commit()
        return {"success": True, "id": notification_id, "status": "PENDING", "message": "Notification returned to the queue for controlled retry."}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.post("/api/v1/webhooks/brevo/transactional")
def brevo_transactional_webhook(
    payload: dict,
    authorization: Optional[str] = Header(None),
):
    expected = os.getenv("BREVO_WEBHOOK_BEARER_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook authentication is not configured.")
    actual = authorization or ""
    if not hmac.compare_digest(actual, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Invalid webhook authorization.")
    event_name = str(payload.get("event") or "").strip()
    message_id = str(payload.get("message-id") or payload.get("messageId") or "").strip()
    if not event_name or not message_id:
        raise HTTPException(status_code=422, detail="Webhook event and provider message ID are required.")
    event_ts = payload.get("ts_event", payload.get("ts", 0))
    try:
        event_epoch = float(event_ts or 0)
    except (TypeError, ValueError):
        event_epoch = 0
    from datetime import timezone
    event_at = datetime.fromtimestamp(event_epoch, timezone.utc).replace(microsecond=0).isoformat() if event_epoch > 0 else None
    event_key = hashlib.sha256(f"brevo|{message_id}|{event_name}|{event_at or ''}".encode()).hexdigest()
    mapping = {
        "request": "SUBMITTED", "sent": "SUBMITTED", "delivered": "DELIVERED",
        "hardBounce": "BOUNCED", "softBounce": "BOUNCED", "blocked": "BOUNCED",
        "invalid": "BOUNCED", "spam": "BOUNCED", "deferred": "SUBMITTED",
    }
    mapped_status = mapping.get(event_name)
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id FROM notification_provider_events WHERE event_key=?", (event_key,)).fetchone()
        if existing:
            conn.commit()
            return {"accepted": True, "duplicate": True}
        outbox = conn.execute("SELECT * FROM notification_outbox WHERE provider_message_id=? ORDER BY id DESC LIMIT 1", (message_id,)).fetchone()
        cursor = conn.execute("""
            INSERT INTO notification_provider_events(event_key,provider_message_id,event_type,event_at,received_at,matched_outbox_id)
            VALUES (?,?,?,?,?,?)
        """, (event_key, message_id, event_name[:80], event_at, utc_now_text(), outbox["id"] if outbox else None))
        if outbox and mapped_status:
            current = str(outbox["status"])
            current_event_at = outbox["last_provider_event_at"]
            newer_event = bool(event_at and current_event_at and event_at >= current_event_at) or (
                not current_event_at and bool(event_at) and current not in {"DELIVERED", "BOUNCED", "FAILED"}
            )
            # Delivered is final: neither a later-timestamp bounce nor a timestamp-less event
            # may downgrade it. A bounce can be upgraded to delivered only with explicit,
            # strictly newer provider timestamps; missing timestamps cannot establish order.
            if current == "DELIVERED" or current == "FAILED":
                apply_provider_status = False
            elif current == "BOUNCED":
                apply_provider_status = bool(mapped_status == "DELIVERED" and event_at and current_event_at and event_at > current_event_at)
            else:
                apply_provider_status = newer_event or (not event_at and not current_event_at)
            if apply_provider_status:
                now = utc_now_text()
                new_status = mapped_status
                if mapped_status == "RETRY":
                    new_status = "RETRY"
                conn.execute("""
                    UPDATE notification_outbox SET status=?, last_provider_event_at=?,
                      delivered_at=CASE WHEN ?='DELIVERED' THEN ? ELSE delivered_at END,
                      last_error_code=CASE WHEN ? IN ('BOUNCED','RETRY') THEN ? WHEN ?='SUBMITTED' AND ?='deferred' THEN 'PROVIDER_DEFERRED' ELSE NULL END,
                      updated_at=? WHERE id=?
                """, (new_status, event_at or now, mapped_status, now, mapped_status,
                      "PROVIDER_" + event_name.upper(), mapped_status, event_name, now, outbox["id"]))
                if str(outbox["event_type"]) == "MANUAL_DONOR_ALERT":
                    prefix = "manual-alert:"
                    idem_key = str(outbox["event_key"])[len(prefix):] if str(outbox["event_key"]).startswith(prefix) else None
                    if idem_key:
                        conn.execute("UPDATE emergency_alerts SET delivery_status=?, delivered=? WHERE idempotency_key=?",
                                     (new_status, 1 if new_status == "DELIVERED" else 0, idem_key))
        conn.commit()
        return {"accepted": True, "duplicate": False, "matched": bool(outbox)}
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"accepted": True, "duplicate": True}
    finally:
        conn.close()


@app.get("/api/v1/locations")
def get_location_catalog():
    return get_location_catalog_data()


@app.get("/api/v1/availability/summary")
def get_location_availability_summary(
        district: Optional[str] = None,
        taluk: Optional[str] = None,
        blood_group: Optional[str] = None
):
    if blood_group and blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported blood group.")
    conn = get_db_connection()
    try:
        catalogue = get_location_catalog_data(conn)
        district_values = {str(value).casefold(): value for value in catalogue["districts"]}
        selected_district = district_values.get(
            (district or "").strip().casefold()) if district and district.lower() != "all" else None
        if district and district.lower() != "all" and not selected_district:
            raise HTTPException(status_code=422, detail="Unknown district; choose a value from the location catalog.")
        if taluk and taluk.lower() != "all":
            if not selected_district:
                raise HTTPException(status_code=422, detail="Choose a district before selecting a taluk.")
            valid_taluks = catalogue["taluks_by_district"].get(selected_district, [])
            if taluk.strip().casefold() not in {str(value).casefold() for value in valid_taluks}:
                raise HTTPException(status_code=422,
                                    detail="The selected taluk does not belong to the selected district.")
        clauses = ["1=1"]
        params = []
        if district and district.lower() != "all":
            clauses.append("LOWER(TRIM(district)) = LOWER(TRIM(?))")
            params.append(district)
        if taluk and taluk.lower() != "all":
            clauses.append("LOWER(TRIM(taluk)) = LOWER(TRIM(?))")
            params.append(taluk)
        if blood_group:
            clauses.append("UPPER(blood_group) = UPPER(?)")
            params.append(blood_group)
        where = " AND ".join(clauses)
        row = conn.execute(f"""
            SELECT COUNT(*) AS total_records,
              SUM(CASE WHEN COALESCE(is_available, 0) = 1
                        AND COALESCE(age, 0) BETWEEN 18 AND 65
                        AND COALESCE(health_score, 0) >= 60
                        AND COALESCE(last_donation_days, 0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END
                       THEN 1 ELSE 0 END) AS eligible_available,
              SUM(CASE WHEN COALESCE(is_available, 0) = 1
                        AND COALESCE(age, 0) BETWEEN 18 AND 65
                        AND COALESCE(health_score, 0) >= 60
                        AND COALESCE(last_donation_days, 0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END
                        AND UPPER(COALESCE(consent,'')) IN ('OPTED_IN','TRUE','YES','1')
                       THEN 1 ELSE 0 END) AS eligible_contactable
            FROM donors WHERE {where}
        """, tuple(params)).fetchone()
        return {
            "district": district or "All",
            "taluk": taluk or "All",
            "blood_group": blood_group.upper() if blood_group else "All",
            "source": "database",
            "total_records": int(row["total_records"] or 0),
            "eligible_available_donors": int(row["eligible_available"] or 0),
            "eligible_contactable_donors": int(row["eligible_contactable"] or 0)
        }
    finally:
        conn.close()


@app.get("/api/v1/donors")
def get_donors(
        blood_group: Optional[str] = None,
        district: Optional[str] = None,
        taluk: Optional[str] = None,
        availability_level: Optional[str] = None,
        eligible_only: bool = False,
        radius_km: Optional[float] = Query(None, gt=0, le=500),
        destination_latitude: Optional[float] = Query(None, ge=-90, le=90),
        destination_longitude: Optional[float] = Query(None, ge=-180, le=180),
        user_payload: Optional[dict] = Depends(get_current_user_from_header)
):
    requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF"})
    if blood_group and blood_group.strip().upper() not in VALID_BLOOD_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported blood group.")
    if availability_level and availability_level.upper() not in {"ALL", "HIGH", "MEDIUM", "LOW"}:
        raise HTTPException(status_code=422, detail="Availability level must be All, High, Medium, or Low.")
    if (destination_latitude is None) != (destination_longitude is None):
        raise HTTPException(status_code=422, detail="Provide both destination coordinates.")
    if radius_km is not None and not valid_coordinates(destination_latitude, destination_longitude):
        raise HTTPException(status_code=422, detail="A radius filter requires valid destination coordinates.")

    conn = get_db_connection()
    try:
        catalogue = get_location_catalog_data(conn)
        district_values = {str(value).casefold(): value for value in catalogue["districts"]}
        selected_district = district_values.get(
            (district or "").strip().casefold()) if district and district.lower() != "all" else None
        if district and district.lower() != "all" and not selected_district:
            raise HTTPException(status_code=422, detail="Unknown district; choose a value from the location catalog.")
        if taluk and taluk.lower() != "all":
            if not selected_district or taluk.strip().casefold() not in {str(value).casefold() for value in
                                                                         catalogue["taluks_by_district"].get(
                                                                                 selected_district, [])}:
                raise HTTPException(status_code=422,
                                    detail="The selected taluk does not belong to the selected district.")
        clauses = ["1=1"]
        params = []
        if eligible_only:
            clauses.extend([
                "COALESCE(is_available,0) = 1", "COALESCE(age,0) BETWEEN 18 AND 65", "COALESCE(health_score,0) >= 60",
                "COALESCE(last_donation_days,0) >= CASE WHEN LOWER(COALESCE(gender,'')) = 'female' THEN 120 ELSE 90 END",
                "UPPER(COALESCE(consent,'')) IN ('OPTED_IN','TRUE','YES','1')"
            ])
        if blood_group:
            clauses.append("UPPER(blood_group) = UPPER(?)")
            params.append(blood_group)
        if district and district.lower() != "all":
            clauses.append("LOWER(TRIM(district)) = LOWER(TRIM(?))")
            params.append(district)
        if taluk and taluk.lower() != "all":
            clauses.append("LOWER(TRIM(taluk)) = LOWER(TRIM(?))")
            params.append(taluk)
        if availability_level and availability_level.upper() != "ALL":
            if availability_level.upper() == "HIGH":
                clauses.append("availability_score IS NOT NULL AND availability_score >= 75")
            elif availability_level.upper() == "MEDIUM":
                clauses.append(
                    "availability_score IS NOT NULL AND availability_score >= 40 AND availability_score < 75")
            else:
                clauses.append("availability_score IS NOT NULL AND availability_score < 40")
        rows = [dict(row) for row in
                conn.execute("SELECT * FROM donors WHERE " + " AND ".join(clauses), tuple(params)).fetchall()]
    finally:
        conn.close()

    results = []
    for donor in rows:
        lat, lon = donor.get("latitude"), donor.get("longitude")
        distance = None
        if valid_coordinates(lat, lon) and valid_coordinates(destination_latitude, destination_longitude):
            distance = round(haversine_distance_km(float(lat), float(lon), float(destination_latitude),
                                                   float(destination_longitude)), 2)
        if radius_km is not None and (distance is None or distance > radius_km):
            continue
        # Return only fields needed for dispatch. Precise coordinates and private address fields stay server-side.
        result = {
            "id": donor["id"], "donor_id": donor["donor_id"], "name": donor["name"],
            "blood_group": donor["blood_group"], "age": donor["age"], "gender": donor.get("gender"),
            "location": donor.get("location"), "district": donor.get("district"), "taluk": donor.get("taluk"),
            "availability_status": donor.get("availability_status"),
            "availability_score": donor.get("availability_score"),
            "last_donation_date": donor.get("last_donation_date"),
            "last_donation_days": donor.get("last_donation_days"),
            "total_donations": donor.get("total_donations"), "donation_frequency": donor.get("donation_frequency"),
            "previous_response_rate": donor.get("previous_response_rate"), "health_score": donor.get("health_score"),
            "distance_km": distance, "distance_available": distance is not None,
            "is_available": bool(donor.get("is_available"))
        }
        # Admin donor directory needs contact details; hospital/staff matching views do not.
        # Emergency alerts are sent server-side, so these roles need no donor email or phone.
        if requester["role"] == "ROLE_ADMIN":
            result["email"] = donor["email"]
            result["phone"] = donor.get("phone")
        results.append(result)
    if valid_coordinates(destination_latitude, destination_longitude):
        results.sort(key=lambda item: (item["distance_km"] is None,
                                       item["distance_km"] if item["distance_km"] is not None else float("inf"),
                                       -(item["availability_score"] or 0)))
    else:
        results.sort(key=lambda item: (-(item["availability_score"] or 0), item["donor_id"]))
    return results


@app.delete("/api/v1/donors/{donor_id}")
def delete_donor(donor_id: str, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN"})
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM donors WHERE id = ? OR donor_id = ? OR email = ?;", (donor_id, donor_id, donor_id))
    conn.commit()
    count = cursor.rowcount
    conn.close()
    if count == 0:
        raise HTTPException(status_code=404, detail="Donor not found.")
    return {"success": True, "message": f"Donor {donor_id} deleted."}


@app.get("/api/v1/inventory")
def get_inventory(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN", "ROLE_HOSPITAL", "ROLE_STAFF"})
    conn = get_db_connection()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM blood_inventory ORDER BY id ASC").fetchall()]
        return rows
    finally:
        conn.close()


@app.post("/api/v1/inventory")
def add_inventory(req: InventoryCreateRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    requester = require_roles(user_payload, {"ROLE_ADMIN", "ROLE_STAFF"})
    blood_group = req.blood_group.strip().upper()
    component_type = (req.component_type or "Whole Blood").strip()
    if blood_group not in VALID_BLOOD_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported blood group.")
    if component_type not in SUPPORTED_COMPONENT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported inventory component type.")
    if req.units_available <= 0:
        raise HTTPException(status_code=422, detail="Units to add must be greater than zero.")
    if req.expiry_date:
        try:
            parsed_expiry = datetime.strptime(req.expiry_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Expiry date must use YYYY-MM-DD format.")
        if parsed_expiry < datetime.now().date():
            raise HTTPException(status_code=422, detail="New stock expiry date cannot be in the past.")

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        duplicate = conn.execute("SELECT * FROM inventory_additions WHERE idempotency_key = ?",
                                 (req.idempotency_key,)).fetchone()
        if duplicate:
            item = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?",
                                (duplicate["blood_group"],)).fetchone()
            conn.commit()
            return {"success": True, "persisted": True, "duplicate": True,
                    "message": "This stock addition was already applied.", "item": dict(item) if item else None}

        existing = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (blood_group,)).fetchone()
        if existing:
            inventory_id = existing["id"]
            conn.execute("""
                UPDATE blood_inventory
                SET units_available = units_available + ?,
                    component_type = ?,
                    status = CASE WHEN units_available + ? > 10 THEN 'AVAILABLE' ELSE 'LOW_STOCK' END
                WHERE id = ?
            """, (req.units_available, component_type, req.units_available, inventory_id))
        else:
            if not req.expiry_date:
                raise HTTPException(status_code=422,
                                    detail="Expiry date is required when creating a new inventory blood-group record.")
            status = "AVAILABLE" if req.units_available > 10 else "LOW_STOCK"
            cursor = conn.execute("""
                INSERT INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (blood_group, component_type, req.units_available, req.expiry_date, status))
            inventory_id = cursor.lastrowid
        conn.execute("""
            INSERT INTO inventory_additions (idempotency_key, inventory_id, blood_group, component_type, quantity, created_by_user_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.idempotency_key, inventory_id, blood_group, component_type, req.units_available, requester["id"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        item = conn.execute("SELECT * FROM blood_inventory WHERE id = ?", (inventory_id,)).fetchone()
        conn.commit()
        return {"success": True, "persisted": True, "duplicate": False, "message": f"Stock updated for {blood_group}.",
                "item": dict(item)}
    except HTTPException:
        conn.rollback()
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        previous = conn.execute("SELECT * FROM inventory_additions WHERE idempotency_key = ?",
                                (req.idempotency_key,)).fetchone()
        if previous:
            item = conn.execute("SELECT * FROM blood_inventory WHERE blood_group = ?",
                                (previous["blood_group"],)).fetchone()
            return {"success": True, "persisted": True, "duplicate": True,
                    "message": "This stock addition was already applied.", "item": dict(item) if item else None}
        raise HTTPException(status_code=409,
                            detail="Stock addition conflicted with another operation; refresh and retry with a new request key.")
    finally:
        conn.close()


@app.delete("/api/v1/inventory/{item_id}")
def delete_inventory(item_id: int, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    require_roles(user_payload, {"ROLE_ADMIN"})
    conn = get_db_connection()
    try:
        cursor = conn.execute("DELETE FROM blood_inventory WHERE id = ?", (item_id,))
        conn.commit()
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="Inventory item not found.")
        return {"success": True, "message": f"Inventory item {item_id} deleted."}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
