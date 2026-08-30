import os
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date

app = FastAPI(
    title="Blood Bank Management System REST API (MongoDB NoSQL)",
    description="Backend API Service supporting Donor Registration, Login, RBAC, Inventory, and ML Predictions",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB PyMongo Connection Attempt with Fallback
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/bloodbank_db")
mongo_connected = False
db = None

try:
    import pymongo
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()
    db = client.get_database("bloodbank_db")
    mongo_connected = True
    print(f"Connected to MongoDB at: {MONGO_URI}")
except Exception as e:
    print(f"MongoDB notice ({e}). Operating with in-memory JSON document cache.")

# Mock In-Memory MongoDB Collections Cache
USERS_DB = [
    {"_id": "usr-1", "name": "System Admin", "email": "admin@bloodbank.org", "role": "ROLE_ADMIN", "phone": "+1-800-555-0199"},
    {"_id": "usr-2", "name": "City General Hospital", "email": "contact@cityhospital.org", "role": "ROLE_HOSPITAL", "phone": "+1-800-555-0101"},
    {"_id": "usr-4", "name": "John Doe", "email": "john.doe@email.com", "role": "ROLE_DONOR", "phone": "+1-555-0144"}
]

DONORS_DB = [
    {
        "_id": "dnr-1", "donor_id": "DNR-1001", "name": "John Doe", "email": "john.doe@email.com", "blood_group": "O+",
        "age": 29, "gender": "Male", "location": "Zone A (Central)", "distance_km": 3.5, "last_donation_days": 150,
        "total_donations": 4, "donation_frequency": 3, "previous_response_rate": 0.95, "preferred_time": "Morning",
        "health_score": 98, "availability_status": "HIGH", "availability_score": 94.5
    }
]

INVENTORY_DB = [
    {"_id": "inv-1", "blood_group": "O+", "units_available": 45, "status": "AVAILABLE", "expiry_date": "2026-09-15"},
    {"_id": "inv-2", "blood_group": "O-", "units_available": 8, "status": "LOW_STOCK", "expiry_date": "2026-09-01"},
    {"_id": "inv-3", "blood_group": "A+", "units_available": 32, "status": "AVAILABLE", "expiry_date": "2026-09-20"},
    {"_id": "inv-4", "blood_group": "A-", "units_available": 12, "status": "AVAILABLE", "expiry_date": "2026-08-30"},
    {"_id": "inv-5", "blood_group": "B+", "units_available": 28, "status": "AVAILABLE", "expiry_date": "2026-09-10"},
    {"_id": "inv-6", "blood_group": "B-", "units_available": 5, "status": "LOW_STOCK", "expiry_date": "2026-08-25"},
    {"_id": "inv-7", "blood_group": "AB+", "units_available": 18, "status": "AVAILABLE", "expiry_date": "2026-09-25"},
    {"_id": "inv-8", "blood_group": "AB-", "units_available": 4, "status": "LOW_STOCK", "expiry_date": "2026-08-28"}
]

REQUESTS_DB = [
    {
        "_id": "req-1", "hospital_name": "City General Hospital", "blood_group": "O-", "units_needed": 4,
        "urgency_level": "EMERGENCY", "patient_name": "Trauma Unit Patient #402", "status": "PENDING",
        "request_date": "2026-08-13 08:30:00"
    }
]

APPOINTMENTS_DB = [
    {"_id": "app-1", "donor_name": "John Doe", "blood_group": "O+", "date": "2026-08-16", "time_slot": "10:00 AM", "status": "SCHEDULED"}
]

class RegisterDonorRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str
    blood_group: str
    age: int
    gender: str
    location: str
    preferred_time: str
    role: Optional[str] = "ROLE_DONOR"

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/")
def home():
    return {"service": "Blood Bank REST API (Registration Enabled)", "status": "ACTIVE"}

# New Donor Registration Endpoint
@app.post("/api/v1/auth/register")
def register_donor(req: RegisterDonorRequest):
    new_user = {
        "_id": f"usr-{len(USERS_DB) + 1}",
        "name": req.name,
        "email": req.email,
        "role": req.role,
        "phone": req.phone
    }
    
    new_donor = {
        "_id": f"dnr-{len(DONORS_DB) + 1}",
        "donor_id": f"DNR-{1000 + len(DONORS_DB) + 1}",
        "name": req.name,
        "email": req.email,
        "blood_group": req.blood_group,
        "age": req.age,
        "gender": req.gender,
        "location": req.location,
        "distance_km": 4.0,
        "last_donation_days": 180,
        "total_donations": 0,
        "donation_frequency": 2,
        "previous_response_rate": 0.90,
        "preferred_time": req.preferred_time,
        "health_score": 95,
        "availability_status": "HIGH",
        "availability_score": 91.5
    }
    
    if mongo_connected:
        res_u = db.users.insert_one(new_user)
        new_donor["user_id"] = str(res_u.inserted_id)
        res_d = db.donors.insert_one(new_donor)
        return {
            "message": "Donor registered successfully in MongoDB!",
            "user_id": str(res_u.inserted_id),
            "donor_id": new_donor["donor_id"]
        }
    
    USERS_DB.append(new_user)
    DONORS_DB.append(new_donor)
    return {
        "message": "Donor registered successfully!",
        "donor_id": new_donor["donor_id"],
        "user": new_user
    }

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    for u in USERS_DB:
        if u["email"].lower() == req.email.lower():
            return {"token": f"jwt-token-for-{u['_id']}-{u['role']}", "user": u}
    raise HTTPException(status_code=401, detail="Invalid email or password")

@app.get("/api/v1/donors")
def get_donors(blood_group: Optional[str] = None):
    if blood_group:
        return [d for d in DONORS_DB if d["blood_group"].lower() == blood_group.lower()]
    return DONORS_DB

@app.get("/api/v1/donors/emergency-search")
def emergency_search(blood_group: str, location: Optional[str] = None):
    results = [d for d in DONORS_DB if d["blood_group"].upper() == blood_group.upper()]
    results.sort(key=lambda x: x["availability_score"], reverse=True)
    return {"requested_blood_group": blood_group, "total_matched": len(results), "donors": results}

@app.get("/api/v1/inventory")
def get_inventory():
    return INVENTORY_DB

@app.get("/api/v1/requests")
def get_requests():
    return REQUESTS_DB

@app.get("/api/v1/appointments")
def get_appointments():
    return APPOINTMENTS_DB

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
