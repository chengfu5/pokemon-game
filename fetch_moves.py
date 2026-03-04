import requests
import json
import time
import os

def fetch_gen4_moves():
    os.makedirs("data", exist_ok=True)
    moves_db = {}
    
    print("Fetching 467 Gen 1-4 moves from PokéAPI...")
    print("This will take about a minute. Please wait...")
    
    # Gen 4 moves end at ID 467
    for i in range(1, 468):
        try:
            res = requests.get(f"https://pokeapi.co/api/v2/move/{i}/")
            if res.status_code != 200:
                continue
                
            data = res.json()
            
            # Format the name (e.g., "swords-dance" -> "Swords Dance")
            name = data["name"].replace("-", " ").title()
            
            move_data = {
                "name": name,
                "type": data["type"]["name"].capitalize(),
                "power": data["power"] if data["power"] is not None else 0,
                "accuracy": data["accuracy"] if data["accuracy"] is not None else 100,
                "category": data["damage_class"]["name"].capitalize()
            }
            
            # 1. Parse Status Effects (Burn, Paralysis, Confusion, etc.)
            if data.get("meta") and data["meta"]["ailment"]["name"] != "none":
                ailment = data["meta"]["ailment"]["name"]
                status_map = {
                    "burn": "BRN", "paralysis": "PAR", "poison": "PSN", 
                    "sleep": "SLP", "confusion": "Confusion"
                }
                if ailment in status_map:
                    move_data["status_effect"] = status_map[ailment]
                        
            # 2. Parse Stat Changes (Swords Dance, Leer, etc.)
            if data.get("stat_changes") and len(data["stat_changes"]) > 0:
                change = data["stat_changes"][0]
                stat_map = {
                    "attack": "attack", "defense": "defense", 
                    "special-attack": "sp_atk", "special-defense": "sp_def", "speed": "speed"
                }
                stat_name = change["stat"]["name"]
                if stat_name in stat_map:
                    move_data["stat_change"] = {
                        "stat": stat_map[stat_name],
                        "stages": change["change"]
                    }
                    
            moves_db[name] = move_data
            
            # Print progress every 50 moves
            if i % 50 == 0:
                print(f"Downloaded {i}/467 moves...")
                
            time.sleep(0.1) # Be polite to the API servers!
            
        except Exception as e:
            print(f"Failed to parse move ID {i}: {e}")
            
    with open("data/moves_data.json", "w") as f:
        json.dump(moves_db, f, indent=4)
        
    print("\nSuccess! Master database saved to data/moves_data.json!")

if __name__ == "__main__":
    fetch_gen4_moves()