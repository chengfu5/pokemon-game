# ai/train_models.py
import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

def train_and_evaluate():
    data_path = "../data/battle_dataset.csv"
    
    # 1. Load the Data
    try:
        df = pd.read_csv(data_path)
    except FileNotFoundError:
        print(f"Error: Could not find {data_path}. Run simulate_battles.py first!")
        return

    print(f"Loaded dataset with {len(df)} turns.")

    # 2. Prepare Features (X) and Target (y)
    X = df[["p1_hp_pct", "p1_alive", "p2_hp_pct", "p2_alive"]]
    y = df["p1_won"]

    # Split into 80% training data and 20% unseen testing data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 3. Define the Models and Hyperparameter Grids
    models = {
        "Logistic Regression": {
            "model": LogisticRegression(max_iter=1000),
            "params": {
                "C": [0.01, 0.1, 1, 10, 100]
            }
        },
        "Random Forest": {
            "model": RandomForestClassifier(random_state=42),
            "params": {
                "n_estimators": [50, 100, 200],
                "max_depth": [None, 5, 10, 20],
                "min_samples_split": [2, 5, 10]
            }
        },
        "XGBoost": {
            "model": XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42),
            "params": {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.1, 0.2],
                "max_depth": [3, 5, 7],
                "subsample": [0.8, 1.0]
            }
        }
    }

    best_model_name = ""
    best_model_obj = None
    best_score = 0

    print("\n--- Starting Random Search Hyperparameter Tuning ---")
    
    # 4. Train and Tune each model
    for name, config in models.items():
        print(f"Tuning {name}...")
        
        # RandomizedSearchCV tries up to 10 random combinations of the hyperparameters
        search = RandomizedSearchCV(
            config["model"], 
            param_distributions=config["params"], 
            n_iter=10, 
            cv=3, 
            scoring='accuracy', 
            n_jobs=-1, 
            random_state=42
        )
        
        search.fit(X_train, y_train)
        best_tuned_model = search.best_estimator_
        
        # Evaluate on the unseen test set
        predictions = best_tuned_model.predict(X_test)
        probabilities = best_tuned_model.predict_proba(X_test)[:, 1]
        
        accuracy = accuracy_score(y_test, predictions)
        roc_auc = roc_auc_score(y_test, probabilities)
        
        print(f"  Best Params: {search.best_params_}")
        print(f"  Test Accuracy: {accuracy * 100:.2f}% | ROC-AUC: {roc_auc:.4f}")
        
        # Keep track of the absolute best model
        if accuracy > best_score:
            best_score = accuracy
            best_model_name = name
            best_model_obj = best_tuned_model

    # 5. Save the Champion Model
    print("\n==================================================")
    print(f"🏆 CHAMPION MODEL: {best_model_name} (Accuracy: {best_score * 100:.2f}%)")
    print("==================================================")
    
    save_path = "../data/best_battle_model.pkl"
    joblib.dump(best_model_obj, save_path)
    print(f"Model saved to {save_path}!")

if __name__ == "__main__":
    # Ensure we run from the correct directory so relative paths work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    train_and_evaluate()