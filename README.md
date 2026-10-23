# HaemoPulse — Blood Donor Availability & Emergency Response Engine

HaemoPulse is an existing blood-bank management application with a React/Vite frontend, a FastAPI + SQLite backend, and a separate FastAPI/Scikit-learn prediction service. The project includes academic documentation, a training dataset, a saved Random Forest pipeline, and a model evaluation report.

## Actual project structure

```text
Major-project/
├── backend/
│   ├── server.py                 # FastAPI API and SQLite access
│   ├── create_role_user.py       # Interactive provisioning for ADMIN/HOSPITAL/STAFF
│   ├── location_catalog.json     # Shared district/taluk options
│   ├── requirements.txt
│   └── .env.example
├── frontend/                     # React 18 + Vite + Tailwind
│   ├── package.json
│   └── src/
├── ml_service/
│   ├── app.py                    # Prediction API
│   ├── requirements.txt
│   ├── dataset/                  # Existing training data and generator
│   └── model/                    # Saved pipeline and evaluation results
├── backend/tests/                # Isolated SQLite/API regression checks
└── docs/                         # Existing project documents
```

The current operational backend is Python/FastAPI with SQLite; `backend/pom.xml` is a legacy Maven file and is not the startup path used by the application. The frontend uses Vite. The ML service loads the pre-existing serialized pipeline; it does not need to retrain the model during startup.

## Requirements

- Python 3.10 or newer (Python 3.11 is a suitable baseline).
- Node.js 18 or newer and npm.
- A copy of the SQLite database if you need existing local records. This project archive intentionally excludes databases containing personal donor information.

## 1. Prepare the backend

From the project root, create and activate a virtual environment. Use the activation command for your shell:

```bash
python -m venv .venv-backend
# macOS/Linux
source .venv-backend/bin/activate
# Windows PowerShell (use this instead of the line above):
# .venv-backend\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

Create the backend's local environment file:

```bash
# macOS/Linux
cp backend/.env.example backend/.env
# Windows PowerShell
# Copy-Item backend/.env.example backend/.env
```

Edit `backend/.env` and set a strong, random, stable `JWT_SECRET` (at least 32 characters). Keep this file private. External email is disabled by default even when no `.env` file is present. Leave `HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=true` during development and testing. Only change it to `false` after intentionally configuring and testing the SMTP provider in a controlled environment.

The backend defaults to `backend/bloodbank.db`. To use an existing local database at another path, set `BLOODBANK_DB_FILE` to that full path in `backend/.env`. **Back up the database before the first startup of an updated backend:** the API adds missing columns/tables in a backward-compatible initialization step. No database file or production records are bundled in the source ZIP.

Start the API from the project root:

```bash
python backend/server.py
```

The default API URL is `http://localhost:8080`; API documentation is at `http://localhost:8080/docs`. The backend does not create default admin credentials. Create a management account interactively (password is hidden while entered):

```bash
python backend/create_role_user.py
```

Choose `ADMIN`, `HOSPITAL`, or `STAFF`. The script uses `backend/.env` and the same `BLOODBANK_DB_FILE` setting as the API. Public self-registration always creates a donor account; it cannot create a management role.

## 2. Start the ML prediction service

Use a separate virtual environment to match the pre-existing model artifact's Scikit-learn version:

```bash
python -m venv .venv-ml
# macOS/Linux
source .venv-ml/bin/activate
# Windows PowerShell (instead of source):
# .venv-ml\Scripts\Activate.ps1
python -m pip install -r ml_service/requirements.txt
python -m uvicorn app:app --app-dir ml_service --reload --port 8000
```

The service is available at `http://localhost:8000`; use `/health`, `/metrics`, and `/docs` to inspect it. Its model scenario endpoint is `POST /predict`. The checked-in model is a pre-existing pipeline trained using the dataset's `Zone A (Central)` to `Zone E (West)` categories—not Karnataka district/taluk labels. The UI therefore keeps model-zone input separate from actual district/taluk database counts. Scores are scenario predictions, not confirmations that a real donor is available or medically eligible. If the model artifact is missing or incompatible, inference is disabled rather than silently retraining or overwriting it.

## 3. Start the frontend

Open a third terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 3000
```

The frontend uses these defaults unless overridden:

- `VITE_API_BASE_URL=http://localhost:8080`
- `VITE_ML_API_BASE_URL=http://localhost:8000`

To change these values, create `frontend/.env.local` with the desired `VITE_...` settings and restart Vite. Never place secrets in Vite environment variables; all `VITE_` values are exposed to the browser.

## Tests and build

Install backend requirements and run the regression tests against a disposable SQLite database, not the application database:

```bash
python -m pytest backend/tests/test_regressions.py -q
python -m py_compile backend/server.py backend/create_role_user.py backend/tests/test_regressions.py ml_service/app.py
```

Build the frontend using the existing lockfile:

```bash
cd frontend
npm ci
npm run build
```

The tests cover password hashing and compatibility, donor self-registration and role assignment, authenticated own-profile access, shared location validation, availability-score and geographic-radius filters, inventory atomic/idempotent additions, disabled real-message delivery, and appointment status persistence. Browser-based visual/keyboard and full cross-service end-to-end checks still require a running browser environment.

## Security, data, and operation notes

- Treat `backend/bloodbank.db`, any backup databases, `.env` files, SMTP app passwords, and other credentials as private. They are ignored by Git and excluded from distributable source archives.
- Back up the database before running an updated server. Startup may add missing fields and audit tables; it does not reset or deliberately reseed an existing database. Optional donor/inventory/request demo fixtures are disabled unless `HAEMOPULSE_ENABLE_DEMO_SEED=true` is explicitly set; this setting does not create login accounts or default passwords. Provision management accounts interactively with `backend/create_role_user.py`.
- Emergency alerts require an authorized administrator/hospital account, a pending emergency request, matching blood group, stored eligibility fields, and explicit donor consent. The API saves an audit result and reports persistence separately from delivery. Test with external messaging disabled.
- Inventory supports the component type already represented in the schema: `Whole Blood`. The schema aggregates stock by blood group and stores one expiry date per group, not per batch/lot.
- Location-specific availability counts are database aggregates. The current ML feature schema does not contain district/taluk features, so district/taluk counts are not represented as ML predictions.
- Keep external credentials out of source control. Never use invented donor coordinates, dummy credentials, or development sample data to claim operational results.

## Existing documentation

See `docs/IEEE_Project_Report.md`, `docs/UML_Diagrams.md`, `docs/PPT_Presentation_Content.md`, `docs/Viva_Questions_And_Answers.md`, and `docs/DEPLOYMENT_GUIDE.md` for the project's existing academic and deployment materials. Review their architecture/metrics against the current implementation before relying on them; some were written for earlier project iterations.
