"""
HaemoPulse ML Model Training Script
Trains a clean Random Forest Pipeline on taluk-level blood availability.
"""

import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "dataset", "taluk_blood_availability.csv")
MODEL_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "donor_availability_rf.joblib")

def generate_taluk_training_data():
    """Generates a verified synthetic training set if CSV is not present."""
    import random
    taluks = ["Koppa", "Sringeri", "Chikmagalur", "Mudigere", "Tarikere", "Kadur", "Narasimharajapura"]
    districts = ["Chikmagalur", "Shimoga", "Hassan", "Udupi"]
    blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    urgencies = ["Low", "Medium", "High", "Critical"]

    rows = []
    for _ in range(2500):
        t = random.choice(taluks)
        d = "Chikmagalur" if t in taluks[:5] else random.choice(districts)
        bg = random.choice(blood_groups)
        units = random.randint(1, 10)
        urg = random.choice(urgencies)

        # Logical ground truth availability rule
        if bg in ["AB-", "O-", "B-"] and units > 3:
            avail = 1 if random.random() < 0.25 else 0
        elif units > 7:
            avail = 1 if random.random() < 0.40 else 0
        else:
            avail = 1 if random.random() < 0.85 else 0

        rows.append({
            "taluk": t,
            "district": d,
            "blood_group": bg,
            "units_requested": units,
            "urgency_level": urg,
            "is_available": avail
        })
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
    df.to_csv(DATASET_PATH, index=False)
    return df

def train():
    if os.path.exists(DATASET_PATH):
        df = pd.read_csv(DATASET_PATH)
    else:
        df = generate_taluk_training_data()

    X = df[["taluk", "district", "blood_group", "units_requested", "urgency_level"]]
    y = df["is_available"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    categorical_features = ["taluk", "district", "blood_group", "urgency_level"]
    numerical_features = ["units_requested"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", "passthrough", numerical_features)
        ]
    )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42))
    ])

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Model successfully trained. Accuracy: {acc * 100:.2f}%")
    print(classification_report(y_test, y_pred))

    os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    print(f"Persisted pipeline to {MODEL_OUTPUT_PATH}")

if __name__ == "__main__":
    train()