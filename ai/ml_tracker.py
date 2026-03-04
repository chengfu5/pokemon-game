# ai/ml_tracker.py
import math
import os
import joblib
import pandas as pd

class WinProbabilityModel:
    def __init__(self):
        self.model = None
        self.using_real_ai = False
        
        # Try to load the trained machine learning model
        model_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'best_battle_model.pkl')
        
        try:
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                self.using_real_ai = True
        except Exception as e:
            print(f"Warning: Could not load trained model ({e}). Using heuristic fallback.")

    def _extract_features(self, game_state):
        p_hp_pct = game_state["p_total_hp"] / max(1, game_state["p_max_hp"])
        ai_hp_pct = game_state["ai_total_hp"] / max(1, game_state["ai_max_hp"])
        p_alive = game_state["p_alive"]
        ai_alive = game_state["ai_alive"]
        
        return p_hp_pct, p_alive, ai_hp_pct, ai_alive

    def predict_win_probability(self, game_state):
        p_hp_pct, p_alive, ai_hp_pct, ai_alive = self._extract_features(game_state)
        
        if self.using_real_ai:
            # Format the data exactly how Scikit-Learn/XGBoost expects it (a Pandas DataFrame)
            features_df = pd.DataFrame([{
                "p1_hp_pct": p_hp_pct,
                "p1_alive": p_alive,
                "p2_hp_pct": ai_hp_pct,
                "p2_alive": ai_alive
            }])
            
            # predict_proba returns an array like [[prob_loss, prob_win]]
            # We want the second value (index 1), which is the probability of class '1' (Player winning)
            probability = self.model.predict_proba(features_df)[0][1]
            return probability
            
        else:
            # Fallback Heuristic
            hp_diff = p_hp_pct - ai_hp_pct
            roster_diff = p_alive - ai_alive
            z = (hp_diff * 2.5) + (roster_diff * 1.5)
            return 1 / (1 + math.exp(-z))