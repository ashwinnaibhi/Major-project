 HaemoPulse — Donor Emergency Responses and Next Appointment Fixes

**Scope:** Minimal changes to the existing React/Vite + FastAPI + SQLite project, based on the latest uploaded `HaemoPulse_Project_latest_1.zip`.

## Execution scope and important limitation

The requested local directory `/mnt/c/Users/Ashwin Kumar N S/OneDrive/Desktop/Project_blood` was not mounted in the execution environment. The implementation was therefore made against an extracted copy of the latest uploaded ZIP, not directly against the user's live local working tree. The uploaded archive did not include `.git`, so the local Git status and unrelated uncommitted changes could not be inspected. The ZIP outputs below are built from the inspected and tested extracted copy.

## Root causes found

### Emergency Accept / Reject

- `frontend/src/pages/DonorDashboard.jsx` already had a handler posting to the existing `POST /api/v1/requests/{request_id}/response` endpoint, and the Notifications subtab already had Accept and Reject buttons. The main-dashboard quick emergency panel, however, only showed a summary without actions. In the notifications list, the UI could fall back to a fabricated list index when a request ID was absent, response feedback was stored as one shared message for all requests, and the list was not refreshed from the server after a response or state conflict.
- `frontend/src/App.jsx` fetched the authenticated request list but exposed no refresh callback to the donor page, so a closed request or pre-existing server response could leave stale cards visible.
- `backend/server.py` already had the `emergency_request_responses` table with `UNIQUE(request_id, donor_id)` and an authenticated response endpoint. The endpoint persisted individual donor responses without globally rejecting the request. The backend did not enforce the email-verification gate that the UI already enforced, and the list endpoint's role handling was inconsistent for the supported `DONOR` role alias.

### Next scheduled appointment

- `frontend/src/pages/DonorDashboard.jsx` displayed `appointments[0]` as the next appointment. Sorting active statuses first and sorting date strings did not exclude past scheduled appointments or filter out cancelled, completed, no-show, or unknown states. It also did not compare the start time for appointments on the current date.
- `backend/server.py` already returned authenticated donor appointments from `/api/v1/donors/me` and `/api/v1/appointments`. The endpoint could be reused; no duplicate endpoint or table was needed.

## Changes made

1. `frontend/src/App.jsx` — adds a request-only refresh callback for the Donor Page so emergency responses reload server-authoritative request state without reloading unrelated donor lists.
2. `frontend/src/pages/DonorDashboard.jsx` — adds Accept/Reject controls to the dashboard quick emergency panel as well as the Notifications list; removes the fabricated request-ID fallback; validates the backend's response before showing a saved state; prevents duplicate local submissions; stores messages per request; refreshes requests after success and after conflicts/errors; displays a conflict notice; differentiates accepted and rejected states; computes and displays the nearest future appointment that is still in an eligible status; and displays appointment loading, empty, and error states. Successful booking triggers a profile reload and reports separately if that refresh fails.
3. `frontend/src/utils/appointments.js` — new dependency-free helper that selects the nearest future `SCHEDULED` or `PENDING` appointment using its stored date and the start time of the stored time slot. Same-day appointments with missing/unparseable start times are not guessed to be upcoming.
4. `frontend/tests/appointments.test.js` — new Node built-in regression tests for nearest date/time, excluded statuses/past appointments, and empty input.
5. `backend/server.py` — accepts the established `DONOR` role alias in the request list endpoint, prioritizes the authenticated donor row, and enforces email verification on the emergency response endpoint to match the existing UI gate. Per-donor persistence and global request status behavior remain unchanged.
6. `backend/tests/test_regressions.py` — adds tests for donor-specific appointment access, verified-donor/open-request requirements, donor role-alias blood-group filtering, unauthenticated response rejection, and incompatible blood-group rejection.
7. `docs/DONOR_PAGE_FIXES_REPORT.md` — this report.

## Database and API changes

- No new table, column, migration, or endpoint was required. The existing `GET /api/v1/requests`, `POST /api/v1/requests/{request_id}/response`, `GET /api/v1/appointments`, and `GET /api/v1/donors/me` APIs are reused.
- The existing `emergency_request_responses` unique key prevents duplicate responses for a `(request_id, donor_id)` pair. A donor's `REJECTED` response does not mutate `blood_requests.status`.
- The response endpoint now enforces the email-verification restriction server-side because the existing donor UI already disables response actions for unverified accounts.
- No application database was opened for editing or migrated by these changes. No backup was created because no database migration was needed. Back up the local `backend/bloodbank.db` before starting any extracted updated server, because the existing startup initialization may apply the project's pre-existing additive schema initialization. Database files are intentionally excluded from the deliverable ZIP to avoid distributing private donor records.

## Verification actually performed

Commands, run from the extracted project root unless otherwise noted:

```bash
python -m py_compile backend/server.py backend/tests/test_regressions.py
pytest -q backend/tests/test_regressions.py
node --test frontend/tests/appointments.test.js
cd frontend && npm run build
```

Observed results:

- Python syntax compilation: **passed**.
- Backend regression suite: **15 passed**, with 19 existing `datetime.utcnow()` deprecation warnings.
- Frontend appointment helper tests: **4 passed**.
- Frontend production build: **not verified**. `npm run build` failed with `sh: 1: vite: not found`. An attempt to run `npm ci --ignore-scripts --no-audit --no-fund` timed out in this environment, leaving an incomplete `node_modules` folder without `node_modules/.bin/vite`. No successful production build is claimed.
- No browser-based end-to-end session was available, so live multi-service behavior and visual rendering remain to be verified on the target machine.

The backend tests use a disposable test SQLite database configured by the test file. They do not reset the user's application database. Real email delivery is disabled in the test environment; no emergency messages were sent.

## Startup commands (Ubuntu/WSL on the target machine)

These commands extract the archive beside the current project rather than overwriting the original. They assume the browser downloaded the ZIP to the Windows Downloads folder; adjust that ZIP path if it was saved elsewhere.

```bash
cd "/mnt/c/Users/Ashwin Kumar N S/OneDrive/Desktop/Project_blood"
mkdir -p donor-fix-release
unzip -q "/mnt/c/Users/Ashwin Kumar N S/Downloads/Project_blood_Donor_Fixes_Updated_20261022_2209.zip" -d donor-fix-release
cd donor-fix-release/Major-project

# Copy the existing database from the original project, keeping a timestamped backup first.
OLD_DB="$(find "/mnt/c/Users/Ashwin Kumar N S/OneDrive/Desktop/Project_blood" -path '*/donor-fix-release/*' -prune -o -type f -path '*/backend/bloodbank.db' -print -quit)"
test -n "$OLD_DB" || { echo "Existing backend/bloodbank.db was not found; do not overwrite or reset the original database."; exit 1; }
cp "$OLD_DB" "${OLD_DB}.pre-donor-page-fixes-$(date +%Y%m%d_%H%M%S)"
cp "$OLD_DB" backend/bloodbank.db

# Terminal 1 — backend
python -m venv .venv-backend
source .venv-backend/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
# Edit backend/.env and replace JWT_SECRET with a strong random secret before startup.
python backend/server.py
```

Open two more terminals at the extracted `Major-project` directory:

```bash
# Terminal 2 — existing ML service
cd "/mnt/c/Users/Ashwin Kumar N S/OneDrive/Desktop/Project_blood/donor-fix-release/Major-project"
python -m venv .venv-ml
source .venv-ml/bin/activate
python -m pip install -r ml_service/requirements.txt
python -m uvicorn app:app --app-dir ml_service --reload --port 8000
```

```bash
# Terminal 3 — frontend
cd "/mnt/c/Users/Ashwin Kumar N S/OneDrive/Desktop/Project_blood/donor-fix-release/Major-project/frontend"
npm ci
npm run dev -- --host 127.0.0.1 --port 3000
```

Then browse to `http://localhost:3000`. Keep the original project and its database untouched until the updated copy has been verified.

## Manual verification

1. Preserve your current `backend/bloodbank.db` and any uncommitted source changes before copying the updated source into the local project.
2. Start the FastAPI backend, the ML service if needed for other dashboard features, and the Vite frontend using the commands in the root `README.md`.
3. Sign in as a verified donor whose blood group matches an open request. In **Donor → Notifications**, Accept or Reject one request. Confirm the response message appears only on that request and the action buttons disappear once the backend confirms the response.
4. Reload the Donor Page. Confirm the same accepted/rejected response is returned from the backend. Try submitting again via a repeated request; the backend should return a conflict and must not overwrite the original response. Try an unauthenticated, unverified, incompatible-blood-group, or closed-request response; the backend should reject it.
5. Confirm the hospital's global request status remains unchanged after one donor rejects it.
6. Create donor appointments on different future dates/time slots and set other test appointments to `CANCELLED`, `COMPLETED`, or `NO_SHOW`. Confirm the closest future `SCHEDULED`/`PENDING` appointment appears as **My Next Scheduled Appointment**. Confirm past/ineligible appointments do not appear in that card. With no eligible appointment, the card reads **You have no upcoming scheduled appointments.**
7. In `frontend/`, run `npm ci`, `npm run build`, and `node --test tests/appointments.test.js` on the target machine. Re-run the backend suite with `python -m pytest backend/tests/test_regressions.py -q`.

## Remaining limitations

- The implementation has been tested against the uploaded ZIP copy, not the unavailable live project folder. Merge/copy the changes into the local project after preserving its current Git state.
- The frontend production build and visual end-to-end run remain unverified because Vite dependencies could not be installed successfully in this execution environment.
- Appointment selection deliberately does not guess a same-day appointment is still upcoming when the stored time slot contains no parseable time. Legacy records with unusual time strings may need those time-slot values normalized.
