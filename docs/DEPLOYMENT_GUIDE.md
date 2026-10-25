# HaemoPulse Free-Tier Cloud Deployment Guide

This guide describes how to deploy the entire HaemoPulse Blood Bank management system (React Frontend, FastAPI Backend, SQLite Database, and Random Forest ML Service) on 100% free-tier cloud hosting with automatic HTTPS and persistent verification links.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |         Mobile / Web Browsers         |
                      +---------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
       HTTPS (Static Assets)                                 HTTPS (REST API)
                |                                                   |
                v                                                   v
+-------------------------------+                   +-------------------------------+
|   Cloudflare Pages / Vercel   |                   |     Render / Koyeb / Docker   |
|   (React 18 + Vite SPA)       |                   |  (FastAPI Backend + ML Engine)|
|                               |                   |                               |
|   * Free tier, unlimited CDN  |                   |   * Free Python 3.11 service  |
|   * Automatic HTTPS           |                   |   * Automatic HTTPS           |
|   * Rewrites for SPA routing  |                   |   * Unified ML Predictor      |
+-------------------------------+                   +-------------------------------+
                                                                    |
                                                     +--------------+--------------+
                                                     |                             |
                                                     v                             v
                                            +-----------------+           +-----------------+
                                            | SQLite Database |           |   Gmail SMTP    |
                                            | (bloodbank.db)  |           | (Port 587/465)  |
                                            +-----------------+           +-----------------+
```

---

## Step 1: Deploy Backend to Render (Free Web Service)

Render provides free hosting for Python web services with HTTPS and environment variables.

1. Create a free account at [render.com](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository:
   - **Repository**: Select your HaemoPulse repository (`Project_blood` or `Major-project`).
   - **Branch**: `test_branch_2` (or your main branch).
   - **Root Directory**: `Major-project`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`
4. In the **Environment Variables** section, add:
   | Variable | Value | Description |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.4` | Enforces compatible Python runtime |
   | `JWT_SECRET` | *(Click 'Generate' or enter 64-char key)* | Secret for auth tokens |
   | `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES` | `false` | Enables live email verification delivery |
   | `SMTP_HOST` | `smtp.gmail.com` | Google SMTP server |
   | `SMTP_PORT` | `587` (or `465`) | 587 for STARTTLS; 465 for Direct SSL |
   | `SMTP_USER` | `ashwinkumarnsrao@gmail.com` | Your verified Gmail address |
   | `SMTP_PASS` | `your-16-char-app-password` | Google Account App Password |
   | `SMTP_MAIL_FROM` | `HaemoPulse Blood Bank <ashwinkumarnsrao@gmail.com>` | Sender header |
   | `FRONTEND_BASE_URL` | `https://your-frontend-app.pages.dev` | Frontend URL for email links (update after Step 2) |
   | `ALLOWED_ORIGINS` | `https://your-frontend-app.pages.dev` | Allowed CORS domain |
5. Click **Create Web Service**.
6. Note down your backend URL: e.g., `https://haemopulse-api.onrender.com`.

---

## Step 2: Deploy Frontend to Cloudflare Pages (or Vercel)

Cloudflare Pages provides permanent free static hosting with zero spin-down delays and global edge delivery.

1. Create a free account at [cloudflare.com](https://cloudflare.com) and navigate to **Workers & Pages**.
2. Click **Create Application** -> **Pages** -> **Connect to Git**.
3. Select your repository and configure build settings:
   - **Project Name**: `haemopulse`
   - **Production Branch**: `test_branch_2`
   - **Framework Preset**: `Vite`
   - **Root Directory**: `Major-project/frontend`
   - **Build Command**: `npm run build`
   - **Build Output Directory**: `dist`
4. Add the following **Environment Variables**:
   | Variable | Value |
   | :--- | :--- |
   | `VITE_API_BASE_URL` | `https://haemopulse-api.onrender.com` *(your backend URL from Step 1)* |
   | `VITE_ML_SERVICE_URL` | `https://haemopulse-api.onrender.com` |
5. Click **Save and Deploy**.
6. Cloudflare will deploy your site and provide an HTTPS URL: `https://haemopulse.pages.dev`.
7. **Important**: Go back to Render (Step 1) and update `FRONTEND_BASE_URL` and `ALLOWED_ORIGINS` with this exact URL!

---

## Step 3: Verifying the Live Deployment

1. **Check Backend Diagnostics**:
   Open in your browser:
   `https://haemopulse-api.onrender.com/api/v1/auth/smtp-status`
   Verify:
   - `"overall_status": "READY"`
   - `"network_probe": {"connectivity_status": "REACHABLE", "tls_ready": true}`
2. **Check ML Prediction**:
   Test inference:
   ```bash
   curl -X POST https://haemopulse-api.onrender.com/predict-availability \
     -H "Content-Type: application/json" \
     -d '{"taluk":"Koppa","district":"Chikmagalur","blood_group":"B+","units_requested":2,"urgency_level":"High"}'
   ```
3. **Test Email Verification from Phone or Laptop**:
   - Open `https://haemopulse.pages.dev` on your smartphone.
   - Register a new donor account with a real email.
   - Check the email inbox on your smartphone.
   - The email will contain a clickable link starting with `https://haemopulse.pages.dev/verify-email?token=...`.
   - Tap the link: the page validates the token and updates the donor profile to **Verified**.

---

## Free-Tier Considerations for College Demonstration

1. **Render Inactivity Spin-Down**:
   - Render's free tier spins down the backend container after 15 minutes of inactivity.
   - The first request after spin-down may take ~45-50 seconds (cold start).
   - *Tip for demo*: Visit the backend URL (`https://.../health`) 2 minutes before the presentation to wake up the service.
2. **Database Persistence**:
   - The SQLite database is bundled with the backend image.
   - For an academic demo, this guarantees all 5,003 donors, Karnataka hospitals, and blood inventory are always present.

---

## Rollback Procedure

If you ever need to revert any deployment change:
1. In Git, restore the backup checkpoint branch:
   ```bash
   git checkout backup_checkpoint_test_branch_2
   ```
2. Or redeploy a previous build commit directly from the Render or Cloudflare Pages dashboard with one click on the "Deployments" tab.
