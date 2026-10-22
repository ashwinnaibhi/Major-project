import os
import json
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Blood Donor Availability Prediction ML Microservice",
    description="Scikit-Learn powered ML REST API for predicting donor availability in emergencies",
    version="1.0.0"
)

_cors_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'donor_availability_rf.joblib')
RESULTS_PATH = os.path.join(BASE_DIR, 'model', 'model_evaluation_results.json')

pipeline = None

@app.on_event("startup")
def load_model():
    global pipeline
    if not os.path.exists(MODEL_PATH):
        pipeline = None
        print(f"ML model artifact not found at {MODEL_PATH}. Inference disabled; no automatic training was started.")
        return
    try:
        pipeline = joblib.load(MODEL_PATH)
        print("ML Pipeline loaded successfully!")
    except Exception as exc:
        pipeline = None
        print(f"ML model artifact could not be loaded ({type(exc).__name__}). Inference is disabled.")

class DonorPredictRequest(BaseModel):
    donor_id: str = Field("DNR-1001", example="DNR-1001")
    age: int = Field(28, ge=18, le=65)
    gender: str = Field("Male", example="Male")
    blood_group: str = Field("O+", example="O+")
    location: str = Field("Zone A (Central)", example="Zone A (Central)")
    distance_km: float = Field(5.0, ge=0.0)
    last_donation_days: int = Field(120, ge=0)
    donation_frequency: int = Field(3, ge=0)
    previous_response_rate: float = Field(0.85, ge=0.0, le=1.0)
    preferred_time: str = Field("Morning", example="Morning")
    response_time_hrs: float = Field(1.5, ge=0.0)
    health_eligibility_score: int = Field(90, ge=0, le=100)

class PredictionResponse(BaseModel):
    donor_id: str
    response_probability: float
    availability_score: float
    availability_category: str
    recommendation: str
    model_used: str

@app.get("/")
def root():
    return {
        "service": "Blood Donor Availability Prediction ML API",
        "status": "Online",
        "endpoints": {
            "predict": "/predict",
            "metrics": "/metrics",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "UP", "model_loaded": pipeline is not None}

@app.get("/metrics")
def get_metrics():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, 'r') as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Metrics file not found")

@app.post("/predict", response_model=PredictionResponse)
def predict_availability(request: DonorPredictRequest):
    if pipeline is None:
        raise HTTPException(status_code=500, detail="ML Model pipeline is not loaded")
    
    input_data = pd.DataFrame([{
        'age': request.age,
        'gender': request.gender,
        'blood_group': request.blood_group,
        'location': request.location,
        'distance_km': request.distance_km,
        'last_donation_days': request.last_donation_days,
        'donation_frequency': request.donation_frequency,
        'previous_response_rate': request.previous_response_rate,
        'preferred_time': request.preferred_time,
        'response_time_hrs': request.response_time_hrs,
        'health_eligibility_score': request.health_eligibility_score
    }])
    
    try:
        proba = float(pipeline.predict_proba(input_data)[0][1])
        score = round(proba * 100, 1)
        
        if score >= 75.0:
            category = "High"
            rec = "Highly Available - Priority contact candidate for emergency blood request."
        elif score >= 40.0:
            category = "Medium"
            rec = "Moderately Available - Alternate backup donor."
        else:
            category = "Low"
            rec = "Low Availability - Recent donation or low response probability."
            
        return PredictionResponse(
            donor_id=request.donor_id,
            response_probability=round(proba, 4),
            availability_score=score,
            availability_category=category,
            recommendation=rec,
            model_used="Random Forest Classifier (v1.0)"
        )
    except Exception as exc:
        print(f"ML prediction error ({type(exc).__name__}): {exc}")
        raise HTTPException(status_code=400, detail="The model could not process this scenario. Check the service logs and input compatibility.")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
