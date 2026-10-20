import os
import json
import sqlite3
import smtplib
import secrets
import hashlib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from dotenv import load_dotenv
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bloodbank.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
JWT_SECRET = os.getenv("JWT_SECRET", "haemopulse_secret_key_2026_jwt")
JWT_ALGORITHM = "HS256"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_FROM = os.getenv("MAIL_FROM", f"HaemoPulse Blood Bank <{SMTP_USER}>" if SMTP_USER else "HaemoPulse <no-reply@haemopulse.org>")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

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

    add_col_if_missing("blood_requests", "hospital_address", "TEXT")
    add_col_if_missing("blood_requests", "contact_phone", "TEXT")
    add_col_if_missing("blood_requests", "created_by_user_id", "INTEGER")

    add_col_if_missing("appointments", "donor_id", "TEXT")
    add_col_if_missing("appointments", "donor_email", "TEXT")
    add_col_if_missing("appointments", "center_name", "TEXT DEFAULT 'Central Blood Bank Hub #1'")
    add_col_if_missing("appointments", "created_at", "TEXT")
    conn.commit()

    # Seed Initial SQL Data if empty
    cursor.execute("SELECT COUNT(*) FROM donors;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO donors (donor_id, name, email, blood_group, age, gender, location, distance_km, last_donation_days, last_donation_date, total_donations, donation_frequency, previous_response_rate, preferred_time, health_score, availability_status, availability_score, is_available)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, [
            ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', 29, 'Male', 'Zone A (Central)', 3.5, 150, '2026-03-15', 4, 3, 0.95, 'Morning', 98, 'HIGH', 94.5),
            ('DNR-1002', 'Sarah Jenkins', 'sarah.j@email.com', 'A-', 34, 'Female', 'Zone B (North)', 6.2, 125, '2026-04-10', 6, 4, 0.88, 'Afternoon', 95, 'HIGH', 89.0),
            ('DNR-1003', 'Michael Brown', 'mbrown@email.com', 'B+', 42, 'Male', 'Zone A (Central)', 8.0, 24, '2026-07-20', 2, 1, 0.40, 'Evening', 85, 'LOW', 35.0),
            ('DNR-1004', 'Emily Davis', 'emily.d@email.com', 'AB+', 25, 'Female', 'Zone C (South)', 12.5, 215, '2026-01-12', 3, 2, 0.75, 'Morning', 92, 'MEDIUM', 68.5)
        ])
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO users (name, email, password, phone, role, is_verified, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE');
        """, [
            ('System Admin', 'admin@bloodbank.org', hash_password('admin123'), '+1-800-555-0199', 'ROLE_ADMIN', 1),
            ('City General Hospital', 'contact@cityhospital.org', hash_password('hospital123'), '+1-800-555-0101', 'ROLE_HOSPITAL', 1),
            ('Dr. Robert Vance', 'staff.vance@bloodbank.org', hash_password('staff123'), '+1-800-555-0102', 'ROLE_STAFF', 1),
            ('John Doe', 'john.doe@email.com', hash_password('donor123'), '+1-555-0144', 'ROLE_DONOR', 1),
            ('Sarah Jenkins', 'sarah.j@email.com', hash_password('donor123'), '+1-555-0145', 'ROLE_DONOR', 1)
        ])
        conn.commit()

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
            ('City General Hospital', '100 Healthcare Blvd, Suite 400', '+1-800-555-0101', 'O-', 4, 'EMERGENCY', 'Trauma Unit Patient #402', 'PENDING', '2026-08-13 08:30:00'),
            ('St. Jude Emergency Center', '450 Trauma Way, East Wing', '+1-800-555-0102', 'B-', 2, 'HIGH', 'Surgical Patient #109', 'APPROVED', '2026-08-12 14:15:00')
        ])
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM donations;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO donations (donation_code, donor_email, donor_name, blood_group, units, donation_date, center_name, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            ('DON-901', 'john.doe@email.com', 'John Doe', 'O+', 1, '2026-03-15', 'Central Blood Bank Hub #1', 'Verified'),
            ('DON-812', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-10-18', 'City General Blood Center', 'Verified'),
            ('DON-705', 'john.doe@email.com', 'John Doe', 'O+', 1, '2025-06-04', 'St. Jude Mobile Drive', 'Verified')
        ])
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM appointments;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            ('DNR-1001', 'John Doe', 'john.doe@email.com', 'O+', '2026-10-20', 'Morning (8 AM - 12 PM)', 'Central Blood Bank Hub #1', 'SCHEDULED', '2026-10-10 10:00:00')
        ])
        conn.commit()

    conn.close()

# Initialize DB
init_sqlite_db()

app = FastAPI(
    title="HaemoPulse Blood Bank API",
    description="Enterprise REST API with Real SMTP Email Verification, JWT Authentication, and ML Optimization",
    version="3.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    # Check if SMTP credentials are provided
    if SMTP_USER and SMTP_PASS:
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
            print(f"[SMTP SUCCESS] Real verification email sent to {to_email}")
        except Exception as e:
            error_msg = str(e)
            print(f"[SMTP ERROR] Failed to send email via {SMTP_HOST}:{SMTP_PORT}: {e}")
    else:
        print(f"[SMTP NOTICE] No SMTP_USER/PASS configured in .env. Email simulated.")
        print(f"VERIFICATION LINK: {verify_link}")

    return {
        "sent": email_sent,
        "recipient": to_email,
        "verify_link": verify_link,
        "error": error_msg
    }

def send_emergency_alert_email(to_email: str, recipient_name: str, blood_group: str, hospital_name: str, urgency: str, patient: str) -> dict:
    subject = f"URGENT {blood_group} Blood Emergency Alert - {hospital_name}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; background: #020617; color: #f8fafc; padding: 20px;">
      <div style="max-width: 540px; margin: auto; background: #0f172a; border: 1px solid #991b1b; border-radius: 12px; padding: 24px;">
        <h2 style="color: #ef4444; margin-top: 0;">🚨 CRITICAL EMERGENCY BLOOD REQUEST</h2>
        <p>Dear <strong>{recipient_name}</strong>,</p>
        <p><strong>{hospital_name}</strong> has issued an urgent emergency requisition for blood group <strong>{blood_group}</strong>.</p>
        <div style="background: #1e293b; padding: 14px; border-radius: 8px; margin: 16px 0; font-size: 13px;">
          <p style="margin: 4px 0;"><strong>Blood Group Needed:</strong> <span style="color:#ef4444; font-size: 16px; font-weight:bold;">{blood_group}</span></p>
          <p style="margin: 4px 0;"><strong>Urgency Level:</strong> {urgency}</p>
          <p style="margin: 4px 0;"><strong>Patient / Reason:</strong> {patient}</p>
          <p style="margin: 4px 0;"><strong>Hospital:</strong> {hospital_name}</p>
        </div>
        <p>Our Machine Learning prediction engine identified you as an active, high-priority donor. If you are eligible and available, please respond via your dashboard or visit the hospital emergency trauma unit.</p>
        <div style="text-align: center; margin-top: 20px;">
          <a href="{FRONTEND_URL}" style="background: #dc2626; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold;">Open HaemoPulse Dashboard</a>
        </div>
      </div>
    </body>
    </html>
    """
    
    email_sent = False
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = MAIL_FROM
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html"))

            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            email_sent = True
            print(f"[SMTP EMERGENCY ALERT] Sent to {to_email}")
        except Exception as e:
            print(f"[SMTP ALERT ERROR] {e}")

    return {"sent": email_sent, "to": to_email}

# --- PYDANTIC SCHEMAS ---
class RegisterDonorRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str
    blood_group: str
    age: int
    gender: Optional[str] = "Male"
    location: str
    preferred_time: Optional[str] = "Morning"
    role: Optional[str] = "ROLE_DONOR"

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
    hospital_name: str
    hospital_address: str
    contact_phone: Optional[str] = ""
    blood_group: str
    units_needed: int
    urgency_level: str
    patient_name: str
    created_by_user_id: Optional[int] = None

class InventoryCreateRequest(BaseModel):
    blood_group: str
    units_available: int
    component_type: Optional[str] = "Whole Blood"
    expiry_date: Optional[str] = "2026-12-31"

class ResendVerificationRequest(BaseModel):
    email: str

# Dependency to extract optional/required token user
def get_current_user_from_header(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    return decode_access_token(token)

@app.get("/")
def home():
    return {
        "service": "HaemoPulse REST API Engine",
        "database": "SQLite Relational Database (bloodbank.db)",
        "smtp_configured": bool(SMTP_USER and SMTP_PASS),
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

    # Insert user with is_verified = 0
    cursor.execute("""
    INSERT INTO users (name, email, password, phone, role, is_verified, verification_token, verification_token_expiry, last_verification_email_sent_at)
    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?);
    """, (req.name, req_email, hashed_pwd, req.phone, req.role or "ROLE_DONOR", raw_token, expiry, now_iso))
    
    user_id = cursor.lastrowid
    donor_id = f"DNR-{1000 + user_id}"

    # Insert donor profile
    cursor.execute("""
    INSERT INTO donors (donor_id, user_id, name, email, blood_group, age, gender, location, distance_km, last_donation_days, total_donations, donation_frequency, previous_response_rate, preferred_time, health_score, availability_status, availability_score, is_available)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 4.0, 180, 0, 2, 0.90, ?, 95, 'HIGH', 91.5, 1);
    """, (donor_id, user_id, req.name, req_email, req.blood_group, req.age, req.gender or "Male", req.location, req.preferred_time or "Morning"))

    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    new_user = dict(cursor.fetchone())
    new_user.pop("password", None)
    
    cursor.execute("SELECT * FROM donors WHERE user_id = ?;", (user_id,))
    new_donor = dict(cursor.fetchone())
    conn.close()

    # Send real email verification
    mail_result = send_real_verification_email(req_email, req.name, raw_token)

    # Create JWT session token
    jwt_token = create_access_token({"sub": req_email, "id": user_id, "role": req.role or "ROLE_DONOR"})

    return {
        "message": f"Registration successful! Verification email sent to {req_email}.",
        "token": jwt_token,
        "user": {
            **new_user,
            "donor_id": donor_id,
            "blood_group": req.blood_group,
            "is_verified": False
        },
        "donor": new_donor,
        "email_delivery": mail_result
    }

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    req_email = req.email.strip().lower()
    hashed_pwd = hash_password(req.password)

    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?;", (req_email,))
    user = cursor.fetchone()

    if not user or user["password"] != hashed_pwd:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_dict = dict(user)
    user_dict.pop("password", None)

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
    user_dict.pop("password", None)

    donor_profile = None
    if user_dict["role"] in ["ROLE_DONOR", "DONOR"]:
        cursor.execute("SELECT * FROM donors WHERE user_id = ? OR LOWER(email) = ?;", (user_dict["id"], user_dict["email"].lower()))
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
            if datetime.utcnow() > exp_dt:
                conn.close()
                raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
        except Exception:
            pass

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
                raise HTTPException(status_code=429, detail=f"Please wait {wait_left} seconds before requesting another email.")
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
        "success": True,
        "message": f"New verification email sent to {req_email}. Please check your inbox and spam folder.",
        "delivery": res
    }

# ========================================================
# 2. DONOR DASHBOARD & PROFILE MANAGEMENT
# ========================================================

@app.get("/api/v1/donors/me")
def get_my_donor_dashboard(user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication token required.")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_payload["id"],))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    user = dict(user_row)
    cursor.execute("SELECT * FROM donors WHERE user_id = ? OR LOWER(email) = ?;", (user["id"], user["email"].lower()))
    donor_row = cursor.fetchone()
    if not donor_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor profile not found.")

    donor = dict(donor_row)

    # Fetch past donations
    cursor.execute("SELECT * FROM donations WHERE LOWER(donor_email) = ? ORDER BY donation_date DESC;", (user["email"].lower(),))
    donations = [dict(r) for r in cursor.fetchall()]

    # Fetch donor appointments
    cursor.execute("SELECT * FROM appointments WHERE LOWER(donor_email) = ? OR donor_id = ? ORDER BY appointment_date DESC;", (user["email"].lower(), donor["donor_id"]))
    appointments = [dict(r) for r in cursor.fetchall()]

    # Fetch matching emergency requests for notifications
    cursor.execute("SELECT * FROM blood_requests WHERE UPPER(blood_group) = UPPER(?) AND status = 'PENDING' ORDER BY urgency_level = 'EMERGENCY' DESC, request_date DESC;", (donor["blood_group"],))
    notifications = [dict(r) for r in cursor.fetchall()]

    conn.close()

    # Calculate eligibility (Male: 90 days, Female: 120 days)
    last_days = donor.get("last_donation_days", 180)
    gender = donor.get("gender", "Male")
    required_gap = 120 if gender == "Female" else 90
    is_eligible = last_days >= required_gap
    days_until_eligible = max(0, required_gap - last_days)

    return {
        "donor": donor,
        "user": {
            "name": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "is_verified": bool(user["is_verified"])
        },
        "stats": {
            "total_donations": donor.get("total_donations", len(donations)),
            "last_donation_days": last_days,
            "last_donation_date": donor.get("last_donation_date", "2026-03-15"),
            "is_eligible": is_eligible,
            "required_gap": required_gap,
            "days_until_eligible": days_until_eligible,
            "availability_score": donor.get("availability_score", 94.5),
            "availability_status": donor.get("availability_status", "HIGH"),
            "is_available": bool(donor.get("is_available", 1))
        },
        "donations": donations,
        "appointments": appointments,
        "emergency_notifications": notifications
    }

@app.put("/api/v1/donors/me/availability")
def toggle_donor_availability(req: AvailabilityToggleRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication token required.")

    conn = get_db_connection()
    cursor = conn.cursor()
    new_avail = 1 if req.is_available else 0

    cursor.execute("""
    UPDATE donors 
    SET is_available = ? 
    WHERE user_id = ? OR LOWER(email) = ?;
    """, (new_avail, user_payload["id"], user_payload["sub"].lower()))
    conn.commit()
    conn.close()

    return {"success": True, "is_available": req.is_available, "message": "Availability status updated."}

@app.put("/api/v1/donors/me/profile")
def update_donor_profile(req: UpdateDonorProfileRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication token required.")

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

    if d_updates:
        d_vals.append(user_payload["id"])
        cursor.execute(f"UPDATE donors SET {', '.join(d_updates)} WHERE user_id = ?;", tuple(d_vals))

    conn.commit()
    cursor.execute("SELECT * FROM donors WHERE user_id = ?;", (user_payload["id"],))
    updated_donor = dict(cursor.fetchone())
    conn.close()

    return {"success": True, "message": "Profile updated successfully.", "donor": updated_donor}

# ========================================================
# 3. APPOINTMENTS (Booking & Verification)
# ========================================================

@app.get("/api/v1/appointments")
def get_all_appointments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments ORDER BY appointment_date ASC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/v1/appointments")
def book_appointment(req: BookAppointmentRequest, user_payload: Optional[dict] = Depends(get_current_user_from_header)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if donor is verified
    user_email = req.donor_email or (user_payload["sub"] if user_payload else None)
    if user_email:
        cursor.execute("SELECT is_verified FROM users WHERE LOWER(email) = ?;", (user_email.lower(),))
        u = cursor.fetchone()
        if u and u["is_verified"] == 0:
            conn.close()
            raise HTTPException(status_code=403, detail="Please verify your email address to book blood donation appointments.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO appointments (donor_id, donor_name, donor_email, blood_group, appointment_date, time_slot, center_name, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?);
    """, (req.donor_id or "DNR-1001", req.donor_name or "Registered Donor", user_email, req.blood_group, req.appointment_date, req.time_slot, req.center_name or "Central Blood Bank Hub #1", now_str))

    conn.commit()
    app_id = cursor.lastrowid
    conn.close()

    return {
        "success": True,
        "id": app_id,
        "message": f"Appointment booked for {req.appointment_date} ({req.time_slot}). We look forward to seeing you!"
    }

# ========================================================
# 4. HOSPITAL BLOOD REQUISITIONS & STAFF SYNC
# ========================================================

@app.get("/api/v1/requests")
def get_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Sort EMERGENCY first, then by request_date DESC
    cursor.execute("""
    SELECT * FROM blood_requests 
    ORDER BY CASE WHEN urgency_level = 'EMERGENCY' THEN 1 ELSE 2 END, request_date DESC;
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/v1/requests")
def create_hospital_request(req: RequestCreateRequest):
    if req.units_needed <= 0:
        raise HTTPException(status_code=400, detail="Units required must be greater than zero.")
    if not req.hospital_name.strip():
        raise HTTPException(status_code=400, detail="Hospital name is required.")
    if not req.hospital_address.strip():
        raise HTTPException(status_code=400, detail="Hospital address is required.")

    conn = get_db_connection()
    cursor = conn.cursor()
    req_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO blood_requests (hospital_name, hospital_address, contact_phone, blood_group, units_needed, urgency_level, patient_name, status, request_date, created_by_user_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?);
    """, (req.hospital_name.strip(), req.hospital_address.strip(), req.contact_phone.strip(), req.blood_group, req.units_needed, req.urgency_level, req.patient_name.strip(), req_date, req.created_by_user_id))

    conn.commit()
    new_id = cursor.lastrowid

    # If EMERGENCY, auto-send alerts to matching available donors
    if req.urgency_level == "EMERGENCY":
        cursor.execute("SELECT * FROM donors WHERE UPPER(blood_group) = UPPER(?) AND is_available = 1;", (req.blood_group,))
        matched_donors = cursor.fetchall()
        for d in matched_donors:
            send_emergency_alert_email(d["email"], d["name"], req.blood_group, req.hospital_name, req.urgency_level, req.patient_name)

    conn.close()

    return {
        "id": new_id,
        "hospital_name": req.hospital_name,
        "hospital_address": req.hospital_address,
        "contact_phone": req.contact_phone,
        "blood_group": req.blood_group,
        "units_needed": req.units_needed,
        "urgency_level": req.urgency_level,
        "patient_name": req.patient_name,
        "status": "PENDING",
        "request_date": req_date
    }

@app.put("/api/v1/requests/{request_id}/status")
def update_request_status(request_id: int, status: str = Query(...)):
    allowed_statuses = ["PENDING", "APPROVED", "ALLOCATED", "REJECTED"]
    clean_status = status.strip().upper()
    if clean_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {allowed_statuses}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE blood_requests SET status = ? WHERE id = ?;", (clean_status, request_id))
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Requisition #{request_id} status updated to {clean_status}."}

@app.delete("/api/v1/requests/{request_id}")
def delete_request(request_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blood_requests WHERE id = ?;", (request_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Requisition #{request_id} deleted."}

# ========================================================
# 5. INVENTORY & DONORS GENERAL
# ========================================================

@app.get("/api/v1/donors")
def get_donors(blood_group: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if blood_group:
        cursor.execute("SELECT * FROM donors WHERE UPPER(blood_group) = UPPER(?) ORDER BY availability_score DESC;", (blood_group,))
    else:
        cursor.execute("SELECT * FROM donors ORDER BY id DESC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.delete("/api/v1/donors/{donor_id}")
def delete_donor(donor_id: str):
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
def get_inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blood_inventory ORDER BY id ASC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/v1/inventory")
def add_inventory(req: InventoryCreateRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    status = "AVAILABLE" if req.units_available > 10 else "LOW_STOCK"
    cursor.execute("""
    INSERT INTO blood_inventory (blood_group, component_type, units_available, expiry_date, status)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(blood_group) DO UPDATE SET units_available = units_available + excluded.units_available, status = excluded.status;
    """, (req.blood_group, req.component_type, req.units_available, req.expiry_date, status))
    conn.commit()
    conn.close()
    return {"message": f"Stock updated for {req.blood_group}."}

@app.delete("/api/v1/inventory/{item_id}")
def delete_inventory(item_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blood_inventory WHERE id = ?;", (item_id,))
    conn.commit()
    conn.close()
    return {"message": f"Inventory item {item_id} deleted."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
