import os
import sys
import json
import joblib
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

def train_and_evaluate():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, 'dataset', 'blood_donor_dataset.csv')
    
    if not os.path.exists(dataset_path):
        from dataset.generate_dataset import generate_donor_dataset
        generate_donor_dataset()
        
    df = pd.read_csv(dataset_path)
    
    feature_cols = [
        'age', 'gender', 'blood_group', 'location', 'distance_km',
        'last_donation_days', 'donation_frequency', 'previous_response_rate',
        'preferred_time', 'response_time_hrs', 'health_eligibility_score'
    ]
    target_col = 'availability_status'
    
    X = df[feature_cols]
    y = df[target_col]
    
    categorical_features = ['gender', 'blood_group', 'location', 'preferred_time']
    numerical_features = ['age', 'distance_km', 'last_donation_days', 'donation_frequency',
                          'previous_response_rate', 'response_time_hrs', 'health_eligibility_score']
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features),
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features)
        ]
    )
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
        'Decision Tree': DecisionTreeClassifier(max_depth=6, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    }
    
    results = {}
    best_model_name = None
    best_f1 = -1
    best_pipeline = None
    
    for name, model in models.items():
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', model)
        ])
        
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1] if hasattr(pipeline, "predict_proba") else y_pred
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred).tolist()
        
        results[name] = {
            'Accuracy': float(np.round(acc * 100, 2)),
            'Precision': float(np.round(prec * 100, 2)),
            'Recall': float(np.round(rec * 100, 2)),
            'F1_Score': float(np.round(f1 * 100, 2)),
            'Confusion_Matrix': cm
        }
        
        print(f"\n=== {name} Performance ===")
        print(f"Accuracy : {acc * 100:.2f}%")
        print(f"Precision: {prec * 100:.2f}%")
        print(f"Recall   : {rec * 100:.2f}%")
        print(f"F1 Score : {f1 * 100:.2f}%")
        print(f"Confusion Matrix:\n{np.array(cm)}")
        
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_pipeline = pipeline

    model_dir = os.path.dirname(os.path.abspath(__file__))
    model_save_path = os.path.join(model_dir, 'donor_availability_rf.joblib')
    results_save_path = os.path.join(model_dir, 'model_evaluation_results.json')
    
    joblib.dump(best_pipeline, model_save_path)
    with open(results_save_path, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"\nBest Model: {best_model_name} (F1 Score: {best_f1*100:.2f}%) saved to {model_save_path}")
    return results

if __name__ == '__main__':
    train_and_evaluate()
