import json
import random
import time

# --- FULL GEN 4 TYPE CHART ---
TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", 
         "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel"]

def get_multiplier(move_type, defender_types):
    super_effective = {
        "Fire": ["Grass", "Ice", "Bug", "Steel"], "Water": ["Fire", "Ground", "Rock"],
        "Grass": ["Water", "Ground", "Rock"], "Electric": ["Water", "Flying"],
        "Ice": ["Grass", "Ground", "Flying", "Dragon"], "Fighting": ["Normal", "Ice", "Rock", "Dark", "Steel"],
        "Poison": ["Grass"], "Ground": ["Fire", "Electric", "Poison", "Rock", "Steel"],
        "Flying": ["Grass", "Fighting", "Bug"], "Psychic": ["Fighting", "Poison"],
        "Bug": ["Grass", "Psychic", "Dark"], "Rock": ["Fire", "Ice", "Flying", "Bug"],
        "Ghost": ["Psychic", "Ghost"], "Dragon": ["Dragon"],
        "Dark": ["Psychic", "Ghost"], "Steel": ["Ice", "Rock"]
    }
    not_effective = {
        "Fire": ["Fire", "Water", "Rock", "Dragon"], "Water": ["Water", "Grass", "Dragon"],
        "Grass": ["Fire", "Grass", "Poison", "Flying", "Bug", "Dragon", "Steel"],
        "Electric": ["Electric", "Grass", "Dragon"], "Ice": ["Fire", "Water", "Ice", "Steel"],
        "Fighting": ["Poison", "Flying", "Psychic", "Bug"], "Poison": ["Poison", "Ground", "Rock", "Ghost"],
        "Ground": ["Grass", "Bug"], "Flying": ["Electric", "Rock", "Steel"],
        "Psychic": ["Psychic", "Steel"], "Bug": ["Fire", "Fighting", "Poison", "Flying", "Ghost", "Steel"],
        "Rock": ["Fighting", "Ground", "Steel"], "Ghost": ["Dark"], "Dragon": ["Steel"],
        "Dark": ["Fighting", "Dark"], "Steel": ["Fire", "Water", "Electric", "Steel"],
        "Normal": ["Rock", "Steel"]
    }
    immunities = {
        "Normal": ["Ghost"], "Fighting": ["Ghost"], "Electric": ["Ground"],
        "Poison": ["Steel"], "Ground": ["Flying"], "Psychic": ["Dark"], "Ghost": ["Normal"]
    }

    multiplier = 1.0
    for def_type in defender_types:
        if def_type in immunities.get(move_type, []): return 0.0
        if def_type in super_effective.get(move_type, []): multiplier *= 2.0
        if def_type in not_effective.get(move_type, []): multiplier *= 0.5
    return multiplier

# Converts a stage (-6 to 6) to a stat multiplier
def get_stat_multiplier(stage):
    if stage > 0: return (2 + stage) / 2.0
    elif stage < 0: return 2.0 / (2 - stage)
    return 1.0

class Move:
    def __init__(self, name, m_type, power, category, stat_change=None):
        self.name = name
        self.type = m_type
        self.power = power
        self.category = category 
        self.stat_change = stat_change # Format: {"stat": "attack", "stages": 2}

class Pokemon:
    def __init__(self, data):
        self.name = data["name"]
        self.types = data["types"]
        
        self.base_stats = {
            "hp": (2 * data["stats"]["hp"] + 31) + 110,
            "attack": (2 * data["stats"]["attack"] + 31) + 5,
            "defense": (2 * data["stats"]["defense"] + 31) + 5,
            "sp_atk": (2 * data["stats"]["sp_atk"] + 31) + 5,
            "sp_def": (2 * data["stats"]["sp_def"] + 31) + 5,
            "speed": (2 * data["stats"]["speed"] + 31) + 5
        }
        self.max_hp = self.base_stats["hp"]
        self.hp = self.max_hp
        self.stat_stages = {"attack": 0, "defense": 0, "sp_atk": 0, "sp_def": 0, "speed": 0}
        
        self.moves = []
        type1 = self.types[0]
        self.moves.append(Move(f"{type1} Strike", type1, 80, "Physical"))
        self.moves.append(Move(f"{type1} Beam", type1, 80, "Special"))
        
        # Add a status move for testing stat modifiers
        if self.base_stats["attack"] > self.base_stats["sp_atk"]:
            self.moves.append(Move("Swords Dance", "Normal", 0, "Status", {"stat": "attack", "stages": 2}))
        else:
            self.moves.append(Move("Agility", "Psychic", 0, "Status", {"stat": "speed", "stages": 2}))

        if len(self.types) > 1:
            self.moves.append(Move(f"{self.types[1]} Strike", self.types[1], 80, "Physical"))
        else:
            self.moves.append(Move("Double-Edge", "Normal", 120, "Physical"))

    def get_stat(self, stat_name):
        return int(self.base_stats[stat_name] * get_stat_multiplier(self.stat_stages[stat_name]))

    def modify_stat(self, stat_name, stages):
        self.stat_stages[stat_name] += stages
        # Clamp between -6 and +6
        self.stat_stages[stat_name] = max(-6, min(6, self.stat_stages[stat_name]))
        direction = "rose sharply" if stages > 1 else "rose" if stages > 0 else "fell"
        print(f"{self.name}'s {stat_name} {direction}!")

    def reset_stats(self):
        self.stat_stages = {k: 0 for k in self.stat_stages}

    def take_damage(self, damage):
        self.hp -= damage
        if self.hp < 0: self.hp = 0

    def is_fainted(self): return self.hp <= 0

class Team:
    def __init__(self, name, roster):
        self.name = name
        self.roster = roster
        self.active_idx = 0

    def get_active(self):
        return self.roster[self.active_idx]

    def has_available_pokemon(self):
        return any(not p.is_fainted() for p in self.roster)

    def switch_pokemon(self, new_idx):
        if not self.roster[new_idx].is_fainted() and new_idx != self.active_idx:
            self.get_active().reset_stats() # Reset volatile stats on switch!
            self.active_idx = new_idx
            print(f"\n{self.name} sent out {self.get_active().name}!")
            return True
        return False

    def force_switch(self):
        for i, p in enumerate(self.roster):
            if not p.is_fainted():
                self.switch_pokemon(i)
                return

def calculate_damage(attacker, defender, move):
    if move.category == "Status": return 0, 1.0 # Status moves do 0 direct damage

    if move.category == "Physical":
        a_stat = attacker.get_stat("attack")
        d_stat = defender.get_stat("defense")
    else:
        a_stat = attacker.get_stat("sp_atk")
        d_stat = defender.get_stat("sp_def")

    base_damage = ((42 * move.power * (a_stat / d_stat)) / 50) + 2
    stab = 1.5 if move.type in attacker.types else 1.0
    type_mult = get_multiplier(move.type, defender.types)
    
    return int(base_damage * stab * type_mult), type_mult



def play_game():
    try:
        with open('pokemon_data.json', 'r') as f:
            pokedex = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find pokemon_data.json. Run fetch_data.py first!")
        return

    print("=== POKEMON 6v6 TACTICAL SIMULATOR ===")
    
    player_team = Team("Player", [Pokemon(random.choice(pokedex)) for _ in range(6)])
    ai_team = Team("Rival AI", [Pokemon(random.choice(pokedex)) for _ in range(6)])

    print("\n--- BATTLE START ---")
    print(f"Rival AI sent out {ai_team.get_active().name}!")
    print(f"Go! {player_team.get_active().name}!")

    while player_team.has_available_pokemon() and ai_team.has_available_pokemon():
        p_active = player_team.get_active()
        ai_active = ai_team.get_active()

        print(f"\n[ YOUR {p_active.name.upper()} : {p_active.hp}/{p_active.max_hp} HP ]")
        print(f"[ FOE {ai_active.name.upper()} : {ai_active.hp}/{ai_active.max_hp} HP ]")
        
        # --- PHASE 1: DECISION PHASE ---
        player_action = None
        while not player_action:
            print("\n1. Fight\n2. Switch")
            choice = input("> ")
            
            if choice == "1":
                for i, move in enumerate(p_active.moves):
                    print(f"{i+1}. {move.name} ({move.type} {move.category})")
                try:
                    move_idx = int(input("> ")) - 1
                    player_action = {"type": "attack", "move": p_active.moves[move_idx], "actor": player_team, "prefix": "Your"}
                except: print("Invalid move.")
            elif choice == "2":
                print("\nChoose a Pokemon:")
                for i, p in enumerate(player_team.roster):
                    status = "FNT" if p.is_fainted() else f"{p.hp}/{p.max_hp}"
                    print(f"{i+1}. {p.name} [{status}]")
                try:
                    switch_idx = int(input("> ")) - 1
                    if not player_team.roster[switch_idx].is_fainted() and switch_idx != player_team.active_idx:
                        player_action = {"type": "switch", "target_idx": switch_idx, "actor": player_team, "prefix": "Your"}
                    else: print("Cannot switch to that Pokemon.")
                except: print("Invalid choice.")

        # AI Selection (Greedy Attacker, but accounts for its own buffed stats now)
        best_ai_move = ai_active.moves[0]
        highest_expected_damage = -1
        for m in ai_active.moves:
            exp_dmg, _ = calculate_damage(ai_active, p_active, m)
            if exp_dmg > highest_expected_damage:
                highest_expected_damage = exp_dmg
                best_ai_move = m
        ai_action = {"type": "attack", "move": best_ai_move, "actor": ai_team, "prefix": "Foe's"}

        # --- PHASE 2: TURN RESOLUTION ---
        # Sort actions: Switches (priority 1) go before Attacks (priority 0). Ties broken by Speed.
        actions = [player_action, ai_action]
        def sort_key(action):
            priority = 1 if action["type"] == "switch" else 0
            speed = action["actor"].get_active().get_stat("speed")
            # We add a tiny random float to prevent total ties from crashing the sort
            return (priority, speed + random.random()) 
        
        actions.sort(key=sort_key, reverse=True)

        # Execute Actions
        for action in actions:
            team = action["actor"]
            active_poke = team.get_active()
            prefix = action["prefix"]
            
            # Skip if this Pokemon fainted earlier in the turn
            if active_poke.is_fainted(): continue

            if action["type"] == "switch":
                team.switch_pokemon(action["target_idx"])
                time.sleep(1)
            
            elif action["type"] == "attack":
                move = action["move"]
                # Opposing team is the one that ISN'T the current actor
                defender_team = ai_team if team == player_team else player_team
                defender = defender_team.get_active()

                print(f"\n{prefix} {active_poke.name} used {move.name}!")
                
                if move.category == "Status":
                    active_poke.modify_stat(move.stat_change["stat"], move.stat_change["stages"])
                else:
                    damage, mult = calculate_damage(active_poke, defender, move)
                    if mult > 1.0: print("It's super effective!")
                    elif 0 < mult < 1.0: print("It's not very effective...")
                    elif mult == 0: print(f"It had no effect on {defender.name}!")
                    
                    defender.take_damage(damage)
                
                time.sleep(1)

                # Mid-turn fainting check
                if defender.is_fainted():
                    print(f"{'Your' if defender_team == player_team else 'Foe\'s'} {defender.name} fainted!")
                    if defender_team.has_available_pokemon():
                        # If the player's Pokemon faints mid-turn, pause the loop to let them choose the replacement
                        if defender_team == player_team:
                            print("\nChoose replacement:")
                            for i, p in enumerate(player_team.roster):
                                status = "FNT" if p.is_fainted() else f"{p.hp}/{p.max_hp}"
                                print(f"{i+1}. {p.name} [{status}]")
                            valid_switch = False
                            while not valid_switch:
                                try:
                                    rep_idx = int(input("> ")) - 1
                                    valid_switch = player_team.switch_pokemon(rep_idx)
                                except: print("Invalid. Try again.")
                        else:
                            defender_team.force_switch()
                    
                    if not player_team.has_available_pokemon() or not ai_team.has_available_pokemon():
                        break

    if player_team.has_available_pokemon():
        print("\n*** YOU WON! ***")
    else:
        print("\n*** YOU BLACKED OUT! ***")

if __name__ == "__main__":
    play_game()