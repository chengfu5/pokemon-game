# simulate_battles.py
import json
import random
import csv
import sys
import os

from core.models import Pokemon, Team, calculate_damage

def get_bot_action(team, enemy_team):
    """A greedy AI that calculates the highest damage move."""
    active = team.get_active()
    enemy = enemy_team.get_active()
    
    best_move = active.moves[0]
    max_expected_damage = -1
    
    for m in active.moves:
        exp_dmg, _ = calculate_damage(active, enemy, m)
        if exp_dmg > max_expected_damage:
            max_expected_damage = exp_dmg
            best_move = m
            
    # For this simulation, the bot rarely switches unless forced, 
    # but we give it a 5% chance to randomly switch to simulate human unpredictability
    if random.random() < 0.05 and team.get_alive_count() > 1:
        valid_benches = [i for i, p in enumerate(team.roster) if not p.is_fainted() and i != team.active_idx]
        if valid_benches:
            return {"type": "switch", "target_idx": random.choice(valid_benches), "actor": team}

    return {"type": "attack", "move": best_move, "actor": team}

def extract_state(p1_team, p2_team):
    """Creates a snapshot of the current game state for the dataset."""
    return {
        "p1_hp_pct": round(p1_team.get_total_hp() / max(1, p1_team.get_max_hp()), 4),
        "p1_alive": p1_team.get_alive_count(),
        "p2_hp_pct": round(p2_team.get_total_hp() / max(1, p2_team.get_max_hp()), 4),
        "p2_alive": p2_team.get_alive_count()
    }

def simulate_single_match(pokedex):
    """Runs a complete match silently and returns the turn data."""
    p1_team = Team("Bot 1", [Pokemon(random.choice(pokedex)) for _ in range(6)])
    p2_team = Team("Bot 2", [Pokemon(random.choice(pokedex)) for _ in range(6)])
    
    # Trigger initial abilities silently
    if p2_team.get_active().ability == "Intimidate": p1_team.get_active().modify_stat("attack", -1)
    if p1_team.get_active().ability == "Intimidate": p2_team.get_active().modify_stat("attack", -1)

    match_history = []
    turn_limit = 200 # Prevent infinite loops if two Pokemon can't damage each other
    current_turn = 0

    while p1_team.has_available_pokemon() and p2_team.has_available_pokemon() and current_turn < turn_limit:
        current_turn += 1
        p1_active = p1_team.get_active()
        p2_active = p2_team.get_active()

        # 1. Bots Decide Actions
        p1_action = get_bot_action(p1_team, p2_team)
        p1_action["prefix"] = "P1"
        p2_action = get_bot_action(p2_team, p1_team)
        p2_action["prefix"] = "P2"

        # 2. Sort Priorities
        actions = [p1_action, p2_action]
        def sort_key(a):
            priority = 1 if a["type"] == "switch" else 0
            return (priority, a["actor"].get_active().get_stat("speed") + random.random()) 
        actions.sort(key=sort_key, reverse=True)

        # 3. Execute Actions
        for action in actions:
            team = action["actor"]
            active_poke = team.get_active()
            defender_team = p2_team if team == p1_team else p1_team
            defender = defender_team.get_active()
            
            if active_poke.is_fainted(): continue

            if action["type"] == "switch":
                team.switch_pokemon(action["target_idx"], opponent=defender)
            elif action["type"] == "attack":
                if active_poke.status == "PAR" and random.random() < 0.25:
                    continue # Paralyzed, skip
                
                move = action["move"]
                if move.category == "Status":
                    if move.status_effect: defender.apply_status(move.status_effect)
                    elif move.stat_change: active_poke.modify_stat(move.stat_change["stat"], move.stat_change["stages"])
                else:
                    damage, _ = calculate_damage(active_poke, defender, move)
                    defender.take_damage(damage)

                # Handle mid-turn fainting
                if defender.is_fainted() and defender_team.has_available_pokemon():
                    defender_team.force_switch(opponent=active_poke)
                    if not p1_team.has_available_pokemon() or not p2_team.has_available_pokemon(): break

        # 4. End of turn effects (Burn)
        for team in [p1_team, p2_team]:
            active = team.get_active()
            if not active.is_fainted() and active.status == "BRN":
                active.take_damage(active.max_hp // 8)
                if active.is_fainted() and team.has_available_pokemon(): team.force_switch()

        # 5. Snapshot the state!
        match_history.append(extract_state(p1_team, p2_team))

    # Who won? (1 if P1 won, 0 if P2 won)
    p1_won = 1 if p1_team.has_available_pokemon() and not p2_team.has_available_pokemon() else 0
    
    # Label every snapshot in this match with the final outcome
    for snapshot in match_history:
        snapshot["p1_won"] = p1_won

    return match_history

def generate_dataset(num_matches=1000):
    try:
        with open('data/pokemon_data.json', 'r') as f:
            pokedex = json.load(f)
    except FileNotFoundError:
        print("Error: data/pokemon_data.json not found!")
        return

    print(f"Simulating {num_matches} matches...")
    print("Muting console output so it runs at lightning speed...")
    
    all_data = []
    
    # Temporarily suppress print statements from models.py
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')

    try:
        for i in range(num_matches):
            match_data = simulate_single_match(pokedex)
            all_data.extend(match_data)
            
            # Print a progress bar (temporarily restoring stdout)
            if (i + 1) % 100 == 0:
                sys.stdout = old_stdout
                print(f"Completed {i + 1}/{num_matches} matches...")
                sys.stdout = open(os.devnull, 'w')
    finally:
        # Always restore stdout when done, even if it crashes
        sys.stdout = old_stdout

    print(f"\nSimulation complete! Generated {len(all_data)} turns of data.")
    
    # Write to CSV
    csv_file = "data/battle_dataset.csv"
    keys = ["p1_hp_pct", "p1_alive", "p2_hp_pct", "p2_alive", "p1_won"]
    
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_data)
        
    print(f"Dataset successfully saved to {csv_file}")

if __name__ == "__main__":
    generate_dataset(1000)