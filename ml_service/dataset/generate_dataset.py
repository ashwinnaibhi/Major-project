import pandas as pd
import numpy as np
import os

def generate_donor_dataset(num_samples=1200, seed=42):
    np.random.seed(seed)
    
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    locations = ['Zone A (Central)', 'Zone B (North)', 'Zone C (South)', 'Zone D (East)', 'Zone E (West)']
    preferred_times = ['Morning', 'Afternoon', 'Evening']
    genders = ['Male', 'Female', 'Other']
    
    donor_ids = [f"DNR-{1000 + i}" for i in range(num_samples)]
    ages = np.random.randint(18, 65, size=num_samples)
    gender_list = np.random.choice(genders, size=num_samples, p=[0.52, 0.46, 0.02])
    bg_list = np.random.choice(blood_groups, size=num_samples, p=[0.30, 0.05, 0.25, 0.05, 0.08, 0.02, 0.20, 0.05])
    loc_list = np.random.choice(locations, size=num_samples)
    distance_km = np.round(np.random.uniform(1.0, 25.0, size=num_samples), 1)
    
    last_donation_days = np.random.randint(30, 365, size=num_samples)
    donation_frequency = np.random.randint(1, 7, size=num_samples)
    previous_response_rate = np.round(np.random.beta(a=5, b=2, size=num_samples), 2)
    preferred_time_list = np.random.choice(preferred_times, size=num_samples)
    response_time_hrs = np.round(np.random.uniform(0.5, 12.0, size=num_samples), 1)
    health_eligibility_score = np.random.randint(60, 101, size=num_samples)
    
    # Mathematical logit to create realistic target variable
    # Higher response rate, shorter distance, reasonable last donation (>90 days), high frequency -> higher availability
    score = (
        (previous_response_rate * 45) +
        (donation_frequency * 4) +
        (np.where(last_donation_days >= 90, 20, -25)) +
        (np.where(distance_km <= 10, 15, -10)) +
        ((health_eligibility_score - 60) * 0.25) -
        (response_time_hrs * 1.5) +
        np.random.normal(0, 5, size=num_samples)
    )
    
    # Normalize score to 0-100
    normalized_score = np.clip((score - score.min()) / (score.max() - score.min()) * 100, 0, 100)
    
    # Binary classification threshold at score 55
    availability_status = (normalized_score >= 50).astype(int)
    
    df = pd.DataFrame({
        'donor_id': donor_ids,
        'age': ages,
        'gender': gender_list,
        'blood_group': bg_list,
        'location': loc_list,
        'distance_km': distance_km,
        'last_donation_days': last_donation_days,
        'donation_frequency': donation_frequency,
        'previous_response_rate': previous_response_rate,
        'preferred_time': preferred_time_list,
        'response_time_hrs': response_time_hrs,
        'health_eligibility_score': health_eligibility_score,
        'availability_score': np.round(normalized_score, 1),
        'availability_status': availability_status
    })
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, 'blood_donor_dataset.csv')
    df.to_csv(filepath, index=False)
    print(f"Dataset generated successfully at: {filepath} ({len(df)} records)")

if __name__ == '__main__':
    generate_donor_dataset()
