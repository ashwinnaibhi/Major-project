import sqlite3
import pandas as pd
import joblib
import os
import re
from datetime import datetime

EXCEL_PATH = r"C:\Users\Ashwin Kumar N S\.gemini\antigravity\brain\43446d04-7971-4fd4-853d-f408e6be7247\.user_uploaded\media_1792474716591_4df94c0d.xlsx"
DB_PATH = r"c:\Users\Ashwin Kumar N S\OneDrive\Desktop\Major project\backend\bloodbank.db"
ML_MODEL_PATH = r"c:\Users\Ashwin Kumar N S\OneDrive\Desktop\Major project\ml_service\model\donor_availability_rf.joblib"

def ingest():
    print(f"Reading dataset from: {EXCEL_PATH}")
    df_raw = pd.read_excel(EXCEL_PATH)
    print(f"Read {len(df_raw)} records from Excel.")

    # Load ML pipeline
    pipe = None
    if os.path.exists(ML_MODEL_PATH):
        try:
            pipe = joblib.load(ML_MODEL_PATH)
            print("Loaded Random Forest ML Pipeline successfully.")
        except Exception as e:
            print(f"Warning: Could not load ML model: {e}")

    # Prepare features for ML model & DB
    today = datetime(2026, 10, 20)
    
    rows_to_insert = []
    ml_input_records = []

    preferred_times = ['Morning', 'Afternoon', 'Evening']

    for idx, r in df_raw.iterrows():
        donor_id = str(r['Donor ID']).strip()
        name = str(r['Name']).strip()
        dob_str = str(r['DOB']).strip()
        gender = str(r['Gender']).strip()
        blood_group = str(r['Blood Group']).strip()
        last_donated_str = str(r['Last Donated']).strip()
        phone = str(r['Fake Mobile Number']).strip()
        district = str(r['District']).strip()
        taluk = str(r['Taluk']).strip()
        fictional_addr = str(r['Fictional Address']).strip()
        lat = float(r['Latitude'])
        lng = float(r['Longitude'])
        consent = str(r['Consent']).strip()

        # Parse birth year & age
        try:
            birth_year = int(dob_str.split('-')[0])
            age = max(18, min(65, 2026 - birth_year))
        except:
            age = 30

        # Parse last donation days
        try:
            last_dt = datetime.strptime(last_donated_str, '%Y-%m-%d')
            days_diff = max(1, (today - last_dt).days)
        except:
            days_diff = 120

        # Location text
        location = f"{taluk}, {district}"

        # Clean email
        clean_name = re.sub(r'[^a-zA-Z0-9]', '.', name.lower())
        clean_name = re.sub(r'\.+', '.', clean_name).strip('.')
        email = f"{clean_name}.{donor_id.lower()}@karnatakadonors.org"

        # Deterministic attributes
        h = abs(hash(donor_id))
        dist_km = round(2.0 + (h % 160) / 10.0, 1) # 2.0 to 18.0 km
        total_dons = max(1, min(15, (age - 18) // 3 + (h % 4)))
        freq = 2 + (h % 3) # 2, 3, or 4
        prev_resp = round(0.85 + (h % 14) * 0.01, 2) # 0.85 to 0.98
        pref_time = preferred_times[h % 3]
        health_score = 90 + (h % 10) # 90 to 99
        resp_time = round(1.0 + (h % 15) * 0.1, 1)

        ml_input_records.append({
            'age': age,
            'gender': gender,
            'blood_group': blood_group,
            'location': location,
            'distance_km': dist_km,
            'last_donation_days': days_diff,
            'donation_frequency': freq,
            'previous_response_rate': prev_resp,
            'preferred_time': pref_time,
            'response_time_hrs': resp_time,
            'health_eligibility_score': health_score
        })

        rows_to_insert.append({
            'donor_id': donor_id,
            'name': name,
            'dob': dob_str,
            'age': age,
            'gender': gender,
            'blood_group': blood_group,
            'last_donation_date': last_donated_str,
            'last_donation_days': days_diff,
            'phone': phone,
            'district': district,
            'taluk': taluk,
            'location': location,
            'fictional_address': fictional_addr,
            'latitude': lat,
            'longitude': lng,
            'email': email,
            'distance_km': dist_km,
            'total_donations': total_dons,
            'donation_frequency': freq,
            'previous_response_rate': prev_resp,
            'preferred_time': pref_time,
            'health_score': health_score,
            'consent': consent
        })

    # Run ML Batch Predictions
    if pipe is not None:
        print("Running batch predictions through Random Forest model...")
        ml_df = pd.DataFrame(ml_input_records)
        probas = pipe.predict_proba(ml_df)[:, 1]
    else:
        probas = [0.9] * len(rows_to_insert)

    for i, r in enumerate(rows_to_insert):
        raw_score = round(float(probas[i]) * 100, 1)
        gender = r['gender']
        days = r['last_donation_days']
        min_gap = 90 if gender.lower() == 'male' else 120

        # Eligibility check
        if days < min_gap:
            # Not yet eligible to donate
            score = min(raw_score, 45.0)
            status = 'LOW'
            is_avail = 0
        else:
            score = max(raw_score, 75.0)
            status = 'HIGH' if score >= 75.0 else 'MEDIUM'
            is_avail = 1

        r['availability_score'] = score
        r['availability_status'] = status
        r['is_available'] = is_avail

    # Connect to SQLite DB
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Add any missing columns to donors table
    existing_cols = [col[1] for col in cur.execute("PRAGMA table_info(donors)").fetchall()]
    new_cols = {
        'dob': "TEXT",
        'phone': "TEXT",
        'district': "TEXT",
        'taluk': "TEXT",
        'fictional_address': "TEXT",
        'latitude': "REAL",
        'longitude': "REAL",
        'consent': "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}' to donors table...")
            cur.execute(f"ALTER TABLE donors ADD COLUMN {col_name} {col_type};")

    # Preserve user-linked donors (e.g. registered users)
    cur.execute("SELECT * FROM donors WHERE user_id IS NOT NULL OR email IN (SELECT email FROM users);")
    preserved_donors = cur.fetchall()
    print(f"Preserving {len(preserved_donors)} registered user donor profiles.")

    # Remove previous synthetic donors
    cur.execute("DELETE FROM donors WHERE user_id IS NULL AND email NOT IN (SELECT email FROM users);")
    conn.commit()

    # Insert 5,000 Karnataka donors
    insert_sql = """
    INSERT INTO donors (
        donor_id, name, email, blood_group, age, gender, location, distance_km,
        last_donation_days, last_donation_date, total_donations, donation_frequency,
        previous_response_rate, preferred_time, health_score, availability_status,
        availability_score, is_available, dob, phone, district, taluk,
        fictional_address, latitude, longitude, consent
    ) VALUES (
        :donor_id, :name, :email, :blood_group, :age, :gender, :location, :distance_km,
        :last_donation_days, :last_donation_date, :total_donations, :donation_frequency,
        :previous_response_rate, :preferred_time, :health_score, :availability_status,
        :availability_score, :is_available, :dob, :phone, :district, :taluk,
        :fictional_address, :latitude, :longitude, :consent
    );
    """
    cur.executemany(insert_sql, rows_to_insert)

    # Link existing users if their user_id is None but email matches
    cur.execute("""
    UPDATE donors 
    SET user_id = (SELECT users.id FROM users WHERE LOWER(users.email) = LOWER(donors.email))
    WHERE user_id IS NULL AND LOWER(email) IN (SELECT LOWER(email) FROM users);
    """)

    # Create search indexes
    indexes = [
        ('idx_donors_blood_group', 'donors (blood_group)'),
        ('idx_donors_district', 'donors (district)'),
        ('idx_donors_taluk', 'donors (taluk)'),
        ('idx_donors_district_taluk', 'donors (district, taluk)'),
        ('idx_donors_donor_id', 'donors (donor_id)'),
        ('idx_donors_email', 'donors (email)'),
        ('idx_donors_user_id', 'donors (user_id)'),
        ('idx_donors_avail', 'donors (is_available, availability_score DESC)')
    ]
    for idx_name, idx_def in indexes:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def};")

    cur.execute("ANALYZE;")
    conn.commit()

    total_count = cur.execute("SELECT COUNT(*) FROM donors;").fetchone()[0]
    print(f"Successfully ingested! Total donors in DB now: {total_count}")

    # Sample query test
    cur.execute("SELECT donor_id, name, blood_group, district, taluk, availability_score, availability_status FROM donors LIMIT 5;")
    for row in cur.fetchall():
        print(f"Sample: {row}")

    conn.close()

if __name__ == '__main__':
    ingest()
