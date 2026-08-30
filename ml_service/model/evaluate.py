import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def display_evaluation_summary():
    model_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(model_dir, 'model_evaluation_results.json')
    
    if not os.path.exists(results_path):
        from train_models import train_and_evaluate
        train_and_evaluate()
        
    with open(results_path, 'r') as f:
        results = json.load(f)
        
    print("=" * 75)
    print("      MACHINE LEARNING MODEL PERFORMANCE COMPARISON MATRIX")
    print("=" * 75)
    print(f"{'Model Name':<25} | {'Accuracy':<10} | {'Precision':<10} | {'Recall':<10} | {'F1 Score':<10}")
    print("-" * 75)
    
    for model_name, metrics in results.items():
        print(f"{model_name:<25} | {metrics['Accuracy']:<9}% | {metrics['Precision']:<9}% | {metrics['Recall']:<9}% | {metrics['F1_Score']:<9}%")
    print("=" * 75)
    
    print("\nDetailed Confusion Matrices:")
    for model_name, metrics in results.items():
        cm = metrics['Confusion_Matrix']
        print(f"\n[{model_name}]")
        print(f"  TN: {cm[0][0]:<4} FP: {cm[0][1]:<4}")
        print(f"  FN: {cm[1][0]:<4} TP: {cm[1][1]:<4}")

if __name__ == '__main__':
    display_evaluation_summary()
