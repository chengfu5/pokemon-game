# fetch_data.py
import requests
import json
import time
import os

def fetch_gen_1_to_4_pokemon():
    # Create directories for data and images
    os.makedirs('data/sprites/front', exist_ok=True)
    os.makedirs('data/sprites/back', exist_ok=True)
    
    pokemon_db = []
    TOTAL_POKEMON = 493
    
    print(f"Fetching {TOTAL_POKEMON} Pokemon data and sprites. This WILL take a few minutes...")
    
    for i in range(1, TOTAL_POKEMON + 1):
        url = f"https://pokeapi.co/api/v2/pokemon/{i}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # --- DOWNLOAD SPRITES ---
            front_url = data['sprites']['front_default']
            back_url = data['sprites']['back_default']
            
            if front_url:
                with open(f'data/sprites/front/{i}.png', 'wb') as f:
                    f.write(requests.get(front_url).content)
            if back_url:
                with open(f'data/sprites/back/{i}.png', 'wb') as f:
                    f.write(requests.get(back_url).content)

            # --- DATA EXTRACTION ---
            types = [t['type']['name'].capitalize() for t in data['types']]
            stats = {stat['stat']['name']: stat['base_stat'] for stat in data['stats']}
            abilities = [a['ability']['name'].replace('-', ' ').title() for a in data['abilities']]
            learnable_moves = [m['move']['name'].replace('-', ' ').title() for m in data['moves']]
            
            pokemon_info = {
                "id": data['id'], # WE NEED THIS ID TO LOAD THE IMAGES LATER!
                "name": data['name'].capitalize(),
                "types": types,
                "abilities": abilities,
                "learnable_moves": learnable_moves,
                "stats": {
                    "hp": stats['hp'], "attack": stats['attack'],
                    "defense": stats['defense'], "sp_atk": stats['special-attack'],
                    "sp_def": stats['special-defense'], "speed": stats['speed']
                }
            }
            pokemon_db.append(pokemon_info)
            
            if i % 10 == 0 or i == TOTAL_POKEMON: 
                print(f"Fetched {i}/{TOTAL_POKEMON}...")
            time.sleep(0.05) # Be polite to the API
        else:
            print(f"Failed to fetch Pokemon ID {i}")

    with open('data/pokemon_data.json', 'w') as f:
        json.dump(pokemon_db, f, indent=4)
    print("\nSuccessfully saved data and downloaded all sprites!")

if __name__ == "__main__":
    fetch_gen_1_to_4_pokemon()