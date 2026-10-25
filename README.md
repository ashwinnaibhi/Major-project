# HaemoPulse Blood Bank Management System

A full-stack healthcare platform facilitating hospital blood requisitions, donor matching, nearby hospital blood search, inventory management, and machine-learning-based regional blood availability simulation.

---

## Architecture Overview

- **Backend**: FastAPI (Python 3.11+), SQLite (`backend/bloodbank.db`), PBKDF2 authentication, PyJWT
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide icons, Axios
- **ML Service**: FastAPI, scikit-learn Random Forest pipeline (`ml_service/model/donor_availability_rf.joblib`)

---

## Setup and Execution Instructions

### 1. Backend Service
```bash
cd backend
# Install dependencies
pip install fastapi uvicorn pydantic pyjwt python-dotenv

# Run the backend server (runs on port 8000 / 8080)
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Application
```bash
cd frontend
# Install dependencies
npm install

# Build for production or start development server
npm run dev
# or: npx vite
```

### 3. ML Prediction Service (Optional / Microservice)
```bash
cd ml_service
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

---

## Issues Addressed in this Release

1. **Issue 1: Assigned Administrator Dropdown Removed**
   - Removed the obsolete "Assigned Administrator" dropdown from the hospital requisition form in `HospitalDashboard.jsx`.
   - Single admin auto-assignment is handled transparently on the backend.

2. **Issue 2: Verified Karnataka Government Hospitals Dataset**
   - Integrated `karnataka_government_hospitals.json` containing verified government hospitals in Karnataka organized by district and taluk.
   - Updated `/api/v1/hospitals/nearby-blood` to return actual facility records, filter proximity by taluk and district, and clearly indicate when blood inventory requires facility inquiry.

3. **Issue 3: Donor Login and Registration Redirection**
   - Fixed role normalization across `ROLE_DONOR`, `ROLE_HOSPITAL`, and `ROLE_ADMIN`.
   - Updated `App.jsx`, `AuthModal.jsx`, and `server.py` so donors land directly on their donor dashboard with database-persisted profile data.

4. **Issue 4: Hospital ML Availability Simulator**
   - Simplified features to `taluk`, `district`, `blood_group`, `units_requested`, and `urgency_level`.
   - Retrained Random Forest pipeline (`donor_availability_rf.joblib`) eliminating donor demographic features (age, gender, response time) not pertinent to hospital taluk-level availability.

5. **Issue 5: Blood Inventory Management**
   - Connected hospital stock management to the `hospital_blood_inventory` table (`/api/v1/hospitals/me/inventory`).
   - Units update only upon database transaction confirmation. Positive quantities and schema-compliant expiry handling enforced.

6. **Issue 6: Emergency Donor Search & Alert**
   - Fixed blood group compatibility filtering in `/api/donors/emergency-search`.
   - Authenticated hospital identity is derived directly from the JWT session; arbitrary fallback to Koppa for unrelated hospitals has been eliminated.
