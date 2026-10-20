# District, Taluk and Request-Origin Distance Guide

This guide documents the district/taluk selector and emergency donor-search additions.

## What changed

- Donor registration and donor profile editing now support district, taluk, optional locality text, and optional latitude/longitude.
- Hospital and admin blood-request forms now support district, taluk, and optional latitude/longitude.
- `GET /api/v1/locations` provides one shared catalog for the React selectors and backend validation.
- `GET /api/v1/donors` accepts combined `blood_group`, `district`, `taluk`, and `available_only` filters. For distance-aware search, pass a saved `request_id`; optionally set `sort_by=distance` or `radius_km=<positive km>`.
- The API returns `distance_from_request_km` as a rounded kilometre value or `null`. Donor latitude/longitude are used only on the backend and are not included in donor-search responses.
- Emergency search displays `Distance unavailable` when a valid donor/request coordinate pair is missing. Distance is straight-line Haversine distance, not driving distance.

## Location catalog accuracy

`backend/location_catalog.json` is a bounded project catalog of 31 district labels and 239 district/taluk pairs found in this archive's structured donor data. The pairs matched the bundled records, but they have **not** been exhaustively reconciled against a current official administrative directory. The catalog is explicitly marked `authoritative: false`; do not describe it as a complete government list. Current official sources to validate against are the [Karnataka District Portal](https://karnataka.s3waas.gov.in/) for district scope and the Government of India's [Local Government Directory (LGD)](https://lgdirectory.gov.in/) / [LGD overview](https://panchayat.gov.in/en/lgd/) for administrative identifiers. The current official district portal lists 31 Karnataka districts. Do not operationally rely on the taluk pairs until verified and refreshed against LGD.

The backend reads selectable pairs only from this configured JSON file. It deliberately does **not** merge arbitrary pairs found in the donor database into the options or validation rules, because a legacy/mistyped database value must not silently become a selectable administrative location. District and taluk comparisons are case-insensitive; the taluk must be configured under the selected district. `GET /api/v1/locations` returns `authoritative: false`, a notice, and the reference URLs so clients do not mistake this project subset for verified official geography. A separate state selector was not added because the current donor/request schema does not define a state field; the configured catalog scope is Karnataka.

## Coordinates and distance

- Coordinates are optional. Supply both latitude and longitude, or leave both blank.
- Latitude must be within `-90..90`; longitude must be within `-180..180`.
- Coordinates should be verified for the actual donor/request location. Do not infer coordinates from district/taluk names.
- The request coordinates are taken from the selected saved blood request (`request_id`). The browser's location is not used.
- Radius filtering excludes donors whose distance is unavailable; it does not treat them as zero-distance candidates.
- Nearest-first sorting places donors with unavailable distances after donors with computed distances.

## Database migration and data preservation

The existing FastAPI startup initializer adds nullable `district`, `taluk`, `latitude`, and `longitude` columns to `blood_requests` only when missing, using the project's `add_col_if_missing` pattern. It also adds missing donor location columns and search indexes. Existing rows remain valid with `NULL` structured location values; old zone strings are not automatically mapped to districts or taluks. The updated code no longer inserts the four artificial zone-labelled donor seed records into a newly empty database. It does not delete any existing donors or requests.

**Preserve your local database.** When applying these changes to an existing checkout, copy the listed source files into the matching locations and keep your existing `backend/bloodbank.db`. Do not replace the whole project directory with a source-only archive. The downloadable sanitized ZIP intentionally excludes the bundled SQLite databases to avoid redistribution of donor-like records.

## ML location feature compatibility

`frontend/src/pages/MLPredictorView.jsx` now calls the existing ML API at `POST /predict`; it no longer creates a pretend score in the browser. The request keeps the existing feature contract, including the string-valued `location` feature, populated with `Taluk, District`. The current training script `ml_service/model/train_models.py` trains a `OneHotEncoder(handle_unknown="ignore")` on synthetic `Zone A` through `Zone E` values from `ml_service/dataset/generate_dataset.py`. The new Karnataka labels are therefore accepted by the API but ignored by that encoder and do not contribute a learned location-specific effect. The UI discloses this limitation. The serialized `.joblib` model was not loaded during this audit because it is an unsafe serialized artifact; inference must be validated only in the user's controlled local environment. No model retraining or synthetic location-labelled training data was created.

`backend/src/main/resources/data.sql` is part of the separate Java/Spring scaffold and still contains legacy demo zone labels; it is not the Python FastAPI runtime database seed. The old Zone A-E values also remain in the ML training generator to preserve the model's current feature contract. They are not offered as real Karnataka districts in the updated UI. Existing legacy donor rows stay unmapped until verified location data is supplied.

## macOS local verification

From the project root:

```bash
cd /Users/venkats/Desktop/Ashwin-Project/Major-project
python -m unittest discover -s backend/tests -v
python -m py_compile backend/server.py backend/tests/test_location_search.py
python -m json.tool backend/location_catalog.json >/dev/null
```

Install frontend packages from the existing lockfile and build from the frontend directory:

```bash
cd /Users/venkats/Desktop/Ashwin-Project/Major-project/frontend
npm ci
npm run build
```

Start the Python backend as in the existing project setup so its startup initializer can apply the backward-compatible schema upgrade. The location additions use the existing backend at `http://localhost:8080`; the frontend's development server defaults to `http://localhost:3000`. If the project uses a different existing frontend API base configuration, retain that configuration rather than introducing a second backend.

The focused tests use a temporary SQLite database, create only `NORMAL` requests, and do not contact SMTP, real donor accounts, or external APIs. Do not create a test request with `urgency_level=EMERGENCY` against a real configured environment: the existing backend automatically attempts emergency email notifications for that urgency level.
