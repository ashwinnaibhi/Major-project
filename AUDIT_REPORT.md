# HaemoPulse project audit and implementation report

Audit date: 22 October 2026

## 1. Inspected project and preservation

The uploaded ZIP extracts to `Major-project/`. The inspected application is a React 18/Vite/Tailwind frontend, a Python FastAPI backend backed by SQLite, and a separate FastAPI/Scikit-learn ML service. `backend/pom.xml` is a legacy Maven file, not the current startup route. The repository ZIP does not include `.git/`, so Git branch, history, and pre-existing uncommitted changes could not be inspected.

The original `backend/bloodbank.db` and `backend/bloodbank_backup.db` were left unchanged. SHA-256 comparisons of the original extraction and working copies matched. A separate disposable copy of the 2.76 MB main database was initialized through the updated schema code: row counts remained `users=2`, `donors=5002`, `blood_inventory=8`, `blood_requests=4`, and `appointments=1`; destination-coordinate columns and the `inventory_additions` / `emergency_alerts` tables were added successfully. This migration test did not use or modify the original file.

## 2. Findings and corrections

### A. Admin emergency search, score filters, and radius

**Confirmed prior behavior:** the emergency search used client-side filtering and fallback score/distance values, did not send a real score/radius filter contract to the backend, and posted email fields directly to an unauthenticated alert endpoint. The backend did not verify the recipient against the selected emergency request.

**Correction:** filtering now runs in the backend for blood group, district, taluk, stored score tier, and eligibility. `HIGH` means score >= 75, `MEDIUM` means 40 to <75, and `LOW` means <40; donors without a stored score are not assigned a fabricated tier. Distances use the Haversine formula in kilometres from the selected request's valid destination coordinates. Distances are returned when coordinates are available, nearest-first ordering is applied, and a radius excludes donors whose distance cannot be verified. Precise donor coordinates are not returned to the browser. The server checks the caller's database-backed role, the pending emergency request, blood-group match, stored eligibility, and explicit alert consent. Alert submissions have an idempotency key and distinguish persistence from real email delivery. Contact email/phone fields are returned by donor search only to the administrator role; hospital/staff matching views use the server-side alert operation instead.

### B. Hospital request modal

**Confirmed prior behavior:** the request modal was a fixed overlay without a properly constrained scrollable inner panel and without a clear back/close path. Request creation did not provide a reliable UI confirmation based on the persisted response.

**Correction:** the overlay and dialog can scroll on small/large screens, the dialog has a labelled close/back control, Escape and backdrop dismissal are supported, and unsaved changes trigger a discard confirmation. Valid destination coordinates can be submitted with the request. The form closes only after the backend returns a saved request ID; errors remain visible and duplicate submissions are disabled while saving.

### C. Donor registration, login, and own profile

**Confirmed prior behavior:** public registration accepted a submitted account role, inserted default availability/donation metrics, and login compared a newly hashed password directly with the stored value. The frontend had fallback/local-only identity/profile behavior rather than consistently showing the authenticated donor's persisted data.

**Correction:** public registration always creates `ROLE_DONOR`, validates the shared location catalog and account inputs, and leaves unknown donor metrics unscored. Passwords use salted PBKDF2-HMAC-SHA256 (310,000 iterations); prior SHA-256/plain legacy values can authenticate for compatibility and are upgraded after a successful login. The own-profile route derives identity from the verified token/database user and profile updates are persisted. The UI no longer manufactures donor records, availability scores, donation counts, or histories. It reports verification-email status without claiming that an unavailable provider delivered a message. Existing role views do not grant permissions on their own. The optional demo-fixture path no longer creates seeded login accounts or common/default passwords; management accounts are provisioned interactively with `backend/create_role_user.py`.

### D. District/taluk and ML prediction

**Confirmed prior behavior:** the frontend calculated a simulated score locally, so displayed results were not a response from the existing ML service. There were no dependent district/taluk selectors. The saved model's feature schema uses synthetic zone strings, not Karnataka district/taluk categories.

**Correction:** the UI now obtains district/taluk choices from one shared catalog endpoint and resets taluk when district changes. Actual eligible/available/contactable donor counts are computed by the SQLite-backed aggregate endpoint and explicitly labelled as database statistics. Model scenario predictions come from the existing `POST /predict` service using its existing model feature schema; the model zone selector remains separate from district/taluk. No training data or model artifact was regenerated. The service now leaves inference disabled if its artifact is missing or unloadable, rather than automatically training/overwriting a model.

**Limitation:** current district/taluk counts reflect the records actually stored in the database. The current ML model does not produce district-specific predictions; its zone-based score must not be interpreted as proof of a donor's availability or medical eligibility. The bundled catalogue is assembled from existing distinct district/taluk values and has not been independently validated against an official geographic source.

### E. Blood inventory

**Confirmed prior behavior:** the inventory view displayed eight hard-coded rows and optimistically changed local quantities while firing a request without authentication or checking persistence. Repeated requests could add stock twice, and deletion also updated the UI before confirmation.

**Correction:** inventory loads from the protected API and empty/error states are explicit. The component dropdown exposes the supported schema value (`Whole Blood`); the blood-group and quantity controls are keyboard-accessible. Additions use backend validation, SQLite `BEGIN IMMEDIATE`, an idempotency key/audit row, and a returned persisted item. The UI updates/reloads only after a persisted response. New blood-group rows require an expiry date; existing rows keep the current expiry because the schema stores one expiry per blood group rather than per stock lot. Admin/staff can add stock; only admins can delete records.

## 3. Database, API, and security notes

- Schema initialization is additive: it creates missing audit tables and adds missing nullable fields, including request destination latitude/longitude, donor contact/location/coordinates/consent fields, and appointment fields. No migration was run against the only original database file. Optional demo fixtures remain off by default and never create login credentials.
- `POST /api/v1/donors/send-email-alert` now requires an authenticated admin/hospital role plus a real request and donor reference. It returns separate `accepted`, `persisted`, `queued`, `delivered`, and `delivery_status` fields. It does not pretend that a saved alert was delivered.
- `GET /api/v1/donors` is role-protected and accepts `availability_level`, `eligible_only`, `radius_km`, `destination_latitude`, and `destination_longitude` in addition to blood group/district/taluk. A radius requires valid destination coordinates. It returns `distance_km` / `distance_available`, not precise donor coordinates.
- `POST /api/v1/requests` persists optional destination coordinates and never dispatches an alert automatically. `PUT /api/v1/appointments/{appointment_id}/status` supports the existing admin/staff appointment-completion workflow.
- `POST /api/v1/inventory` validates blood group, supported component, positive whole-number quantities, expiry, and idempotency key; updates are transactional.
- `JWT_SECRET` should be a unique random value at least 32 characters long. Missing/too-short/template placeholder values trigger an ephemeral development secret and a security notice. This logs users out after restart and is not a production configuration.
- External messages are disabled by default unless the operator explicitly sets `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=false`; tests also force them off. SMTP was not configured, and no real emergency alert or verification email was sent.
- Required configuration is documented in `.env.example`, `backend/.env.example`, and `README.md`. Do not place secrets in Vite `VITE_` variables.

## 4. Exact changed-file list

No existing files were deleted. The following paths differ from the extracted original ZIP:

- `.env.example` — safe JWT placeholder and explicit external-message test default.
- `.gitignore` — ignore database/backup files, generated dependencies, caches, and environment files.
- `README.md` — correct stack, safe database handling, setup, startup, test commands, and ML limitations.
- `AUDIT_REPORT.md` — this findings, implementation, and test record.
- `backend/.env.example` — matching safe local configuration template.
- `backend/create_role_user.py` — new interactive, password-hidden administrator/hospital/staff account provisioning; no hard-coded default credentials.
- `backend/location_catalog.json` — new shared district/taluk catalogue containing location names/pairs only, not donor records.
- `backend/requirements.txt` — explicit backend and regression-test dependencies.
- `backend/server.py` — role enforcement, password hashing/legacy upgrade, own-profile API, location validation, filtering/distance, request coordinate support, message audit/idempotency, inventory persistence/idempotency, and appointment status API.
- `backend/tests/test_regressions.py` — new isolated-database API, authorization, filter, migration-adjacent, messaging, inventory, and appointment regression tests.
- `frontend/src/App.jsx` — actual session/role handling, backend-driven fetches, and persist-before-refresh operations.
- `frontend/src/components/Navbar.jsx` — genuine session display and donor sign-in/logout controls.
- `frontend/src/pages/AdminDashboard.jsx` — remove fabricated metric/score fallbacks and protect donor/admin-only information in the view.
- `frontend/src/pages/AppointmentsView.jsx` — read persisted appointment records and update status through the API.
- `frontend/src/pages/DonorDashboard.jsx` — authenticated registration/login/profile, shared location selectors, truthful delivery feedback, and removal of fabricated profile metrics.
- `frontend/src/pages/EmergencySearch.jsx` — backend score/district/taluk/radius filters, actual distances, and persisted/authenticated idempotent alert flow.
- `frontend/src/pages/HospitalDashboard.jsx` — scrollable modal, back/close safeguards, coordinate validation, and persistence-confirmed submission.
- `frontend/src/pages/InventoryView.jsx` — API-loaded stock, supported units, authorization, validation, idempotent persisted additions, and confirmed deletion.
- `frontend/src/pages/MLPredictorView.jsx` — real ML-service requests plus separate database-derived district/taluk counts.
- `frontend/src/pages/RequestsView.jsx` — persisted request/status/delete operations, loading/errors, and scroll-safe modal behavior.
- `ml_service/app.py` — controlled CORS, honest missing-model behavior, and safe inference failure responses without auto-training.
- `ml_service/requirements.txt` — pin Scikit-learn to the saved artifact's recorded version, 1.7.1.

There are no unrelated source-code files in the change list. The original source database files are intentionally absent from the deliverable ZIPs due to their personal donor data. External SMTP delivery is opt-in and disabled by default.

## 5. Test report

### PASS — backend regression suite

Command:

```bash
python -m pytest backend/tests/test_regressions.py -q
```

Observed result: **9 passed, 12 warnings**. Tests execute against a disposable SQLite file, not the uploaded database. Coverage includes known Haversine distance and coordinate validation; secure hashing and legacy compatibility; donor registration role enforcement/duplicate rejection/location validation; valid and invalid login; own profile and role access; HIGH/MEDIUM/LOW filters; combined district/taluk/blood-group/eligibility/radius filtering; missing coordinates and contact-field minimization; destination-coordinate persistence; idempotent stock additions and invalid unit/quantity rejection; emergency-alert authorization/persistence/idempotency with messaging disabled; and appointment status persistence/role enforcement. The warnings are Python deprecations from existing `datetime.utcnow()` calls; they did not fail tests.

### PASS — Python syntax/import compilation

```bash
python -m py_compile backend/server.py backend/create_role_user.py backend/tests/test_regressions.py ml_service/app.py
```

Observed result: exit code 0.

### PASS — frontend JavaScript/JSX syntax

A TypeScript compiler parser available in the environment transpiled all **17 `.js`/`.jsx` files** under `frontend/src`; observed result: 0 syntax errors. Command: a `node` inline script using the installed TypeScript compiler API (`transpileModule`) to parse every `.js`/`.jsx` file and check relative imports. Observed result: 17 files parsed, 0 syntax errors, 0 missing relative imports. This is a syntax check, not a Vite production build or browser test.

### PASS — ML service smoke test

Using FastAPI `TestClient` against the actual existing artifact: `GET /health` returned HTTP 200 with `model_loaded: true`; `GET /metrics` returned HTTP 200; and a valid `POST /predict` scenario returned HTTP 200 with the expected prediction fields. The local environment emitted Scikit-learn `InconsistentVersionWarning` because the artifact was saved with 1.7.1 while the preinstalled runtime was 1.8.0. `ml_service/requirements.txt` now pins 1.7.1; recreate the ML environment from that file for a matching runtime. No model retraining occurred.

### PASS — external messaging defaults disabled

A fresh Python process with `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES` unset and `BLOODBANK_DB_FILE` pointed at a disposable SQLite path imported `backend/server.py`; it printed `EXTERNAL_MESSAGES_ENABLED= False`. No SMTP provider was contacted.

### PASS — migration against a copy of existing database

The updated schema initialization was run against a temporary copy of the uploaded main database. Row counts for users, donors, inventory, requests, and appointments remained unchanged (2, 5002, 8, 4, and 1 respectively). The request destination columns and alert/inventory audit tables were present afterwards. The original database's hash remained identical to the extracted original.

### BLOCKED — frontend dependency install and production build

Commands and observed results:

```bash
cd frontend
npm run build
# sh: 1: vite: not found (exit 127)

npm ci --ignore-scripts --no-audit --no-fund --offline --fetch-retries=0
# ENOTCACHED: yallist-3.1.1.tgz was not present in npm's local cache (exit 1)
```

An online dependency install did not complete in this environment. `frontend/package-lock.json` was retained unchanged. The Vite build must be rerun after `npm ci` can reach the npm registry.

### NOT RUN — browser/manual and full end-to-end checks

A browser build/runtime was unavailable because frontend dependencies could not be installed. No claims are made that scroll/focus behavior has been manually observed in a browser or that the full frontend → backend → external email chain has passed end-to-end. Real external messaging was deliberately not exercised.

## 6. Startup and verification

See `README.md` for the full setup. From the project root, in PowerShell:

```powershell
py -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
# Edit backend\.env: replace the JWT_SECRET template with a random value.
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Back up any existing database before starting; optionally set BLOODBANK_DB_FILE in backend\.env.
python backend\server.py
```

Create a management account if needed (the script prompts without echoing the password):

```powershell
python backend\create_role_user.py
```

Start the ML service in another terminal with a separate environment:

```powershell
py -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
python -m pip install -r ml_service\requirements.txt
python -m uvicorn app:app --app-dir ml_service --reload --port 8000
```

Start the frontend in a third terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 3000
```

Verification commands:

```powershell
python -m pytest backend\tests\test_regressions.py -q
python -m py_compile backend\server.py backend\create_role_user.py backend\tests\test_regressions.py ml_service\app.py
cd frontend
npm run build
```

For manual acceptance, log in through a real persisted account; create a pending emergency request using the true destination coordinates; test each score option and radius cutoff; submit an alert with external messages disabled and verify it reports “persisted, not delivered”; scroll/close the hospital form with and without unsaved changes; register/login a donor and confirm their own stored profile; compare district/taluk database counts separately from a model-zone prediction; and add stock then reload the inventory list. Configure/verify SMTP only in a controlled environment before enabling actual external messages.

## 7. Final safety review

- Existing main and backup database files in the working copy match the original extracted files by SHA-256.
- No production database was used for automated tests; migration validation ran on a disposable copy and preserved table row counts.
- No real emergency messages or verification messages were sent during testing.
- No model artifact was retrained or overwritten, and no donor records or geographic coordinates were invented in the database.
- The UI no longer uses hard-coded inventory rows or fake donor availability scores as successful API results.
- Existing React/FastAPI/SQLite/Scikit-learn architecture and dependency lockfile were retained.
- Git metadata was absent from the ZIP; branch/history/uncommitted changes cannot be reported.
- Remaining blockers: install frontend dependencies and run the Vite build/browser checks; use Scikit-learn 1.7.1 for artifact-version alignment; configure SMTP intentionally only if actual email delivery is required.
