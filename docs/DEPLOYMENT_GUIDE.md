# Production Deployment & Installation Guide

This document outlines step-by-step instructions for installing, running locally, and deploying the **Online Blood Bank Management System with Donor Availability Prediction** across modern cloud platforms.

---

## 1. LOCAL DEVELOPMENT SETUP

### Prerequisites
- **Python**: Version 3.11+
- **Node.js**: Version 18+ (npm v9+)
- **Java JDK**: Version 17+ (with Maven 3.8+)

---

### Step A: Machine Learning Service Setup (`ml_service`)
1. Open PowerShell / Terminal and navigate to the project directory:
   ```bash
   cd ml_service
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Train models and generate evaluation metrics:
   ```bash
   python model/train_models.py
   ```
5. Start the FastAPI ML microservice server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Swagger API Documentation will be live at `http://localhost:8000/docs`*

---

### Step B: Backend Application Setup (`backend`)
1. Launch the Python API server or compile Spring Boot:
   ```bash
   cd backend
   python server.py
   ```
   *Or for Maven Spring Boot build*:
   ```bash
   mvn clean package
   java -jar target/blood-bank-backend-1.0.0.jar
   ```
   *Backend REST API will be running on `http://localhost:8080`*

---

### Step C: React Frontend Application Setup (`frontend`)
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Launch Vite development server:
   ```bash
   npm run dev
   ```
   *Open browser at `http://localhost:3000`*

---

## 2. PRODUCTION CLOUD DEPLOYMENT GUIDE

```
+-------------------+      +-------------------+      +-------------------+
|  FRONTEND (UI)    |      |  BACKEND (API)    |      |    ML SERVICE     |
|   Vercel Cloud    | ---> |  Render Platform  | ---> |   Render Platform |
|   (React + Vite)  |      |  (Spring Boot /   |      |  (FastAPI + ML)   |
|                   |      |   Python Server)  |      |                   |
+-------------------+      +-------------------+      +-------------------+
                                     |
                                     v
                           +-------------------+
                           | DATABASE CLOUD    |
                           | Railway / Aiven   |
                           | MySQL 8.0         |
                           +-------------------+
```

### 1. Deploy ML Service on Render
1. Push `ml_service` repository to GitHub.
2. Log into [Render.com](https://render.com) and create a **Web Service**.
3. Set Environment to **Python 3**.
4. Set Build Command: `pip install -r requirements.txt && python model/train_models.py`
5. Set Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 2. Deploy Database on Railway / Aiven MySQL
1. Create a MySQL database instance on [Railway.app](https://railway.app).
2. Execute `backend/src/main/resources/schema.sql` and `data.sql` to instantiate tables and initial seed dataset.

### 3. Deploy Frontend on Vercel
1. Log into [Vercel.com](https://vercel.com) and import the `frontend/` directory.
2. Framework Preset: **Vite**.
3. Set Environment Variable: `VITE_API_BASE_URL = https://your-backend-render.onrender.com`
4. Click **Deploy**.
