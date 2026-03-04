# core/models.py
import random
import json
from core.constants import get_multiplier, get_stat_multiplier, MOVE_DATABASE

with open('data/moves_data.json', 'r') as f:
    MASTER_MOVES_DB = json.load(f)

class Move:
    def __init__(self, name, m_type, power, category, accuracy=100, stat_change=None, status_effect=None):
        self.name = name
        self.type = m_type
        self.power = power
        self.category = category
        self.accuracy = accuracy
        self.stat_change = stat_change
        self.status_effect = status_effect

class Pokemon:
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.types = data["types"]
        self.ability = data["abilities"][0] if data.get("abilities") else None
        
        # Base stats from JSON
        self.base_stats = data["stats"]
        
        # --- Level 100 Perfect IV/EV Math ---
        # HP Formula: ((2 * Base + IV + EV_Bonus) * Level / 100) + Level + 10
        # Assuming Perfect IVs (31) and balanced EVs (85)
        self.max_hp = int(2 * self.base_stats["hp"] + 31 + 85) + 110
        self.hp = self.max_hp
        
        # Other Stats Formula: ((2 * Base + IV + EV_Bonus) * Level / 100) + 5
        self.stats = {
            "attack": int(2 * self.base_stats["attack"] + 31 + 85) + 5,
            "defense": int(2 * self.base_stats["defense"] + 31 + 85) + 5,
            "sp_atk": int(2 * self.base_stats["sp_atk"] + 31 + 85) + 5,
            "sp_def": int(2 * self.base_stats["sp_def"] + 31 + 85) + 5,
            "speed": int(2 * self.base_stats["speed"] + 31 + 85) + 5
        }
        
        # Battle state variables
        self.stat_stages = {
            "attack": 0, "defense": 0, "sp_atk": 0, "sp_def": 0, "speed": 0
        }
        self.status = None
        self.is_confused = False
        
        # --- Smart Random Move Generation ---
        self.moves = []
        
        # 1. Filter all 467 moves to find STAB (Same Type Attack Bonus) or Normal type moves
        valid_move_names = [
            m_name for m_name, m_data in MASTER_MOVES_DB.items() 
            if m_data["type"] in self.types or m_data["type"] == "Normal"
        ]
        
        # 2. Filter out moves with 0 power that aren't status moves (e.g., Splash, Teleport)
        valid_moves = [
            m for m in valid_move_names 
            if MASTER_MOVES_DB[m]["power"] > 0 or MASTER_MOVES_DB[m]["category"] == "Status"
        ]
        
        # 3. Pick up to 4 random unique moves
        selected_names = random.sample(valid_moves, min(4, len(valid_moves)))
        
        # 4. Map the JSON data into your Move objects
        for name in selected_names:
            move_dict = MASTER_MOVES_DB[name]
            
            move_obj = Move(
                name=move_dict["name"],
                m_type=move_dict["type"],
                category=move_dict["category"],
                power=move_dict["power"],
                accuracy=move_dict["accuracy"]
            )
            
            # Safely attach secondary effects if they exist in the database
            if "status_effect" in move_dict:
                move_obj.status_effect = move_dict["status_effect"]
            if "stat_change" in move_dict:
                move_obj.stat_change = move_dict["stat_change"]
                
            self.moves.append(move_obj)

    def get_stat(self, stat_name):
        val = int(self.base_stats[stat_name] * get_stat_multiplier(self.stat_stages[stat_name]))
        if stat_name == "speed" and self.status == "PAR": val //= 4
        return val

    def modify_stat(self, stat_name, stages, source_name=""):
        self.stat_stages[stat_name] += stages
        self.stat_stages[stat_name] = max(-6, min(6, self.stat_stages[stat_name]))
        direction = "rose sharply" if stages > 1 else "rose" if stages > 0 else "fell"
        prefix = f"[{source_name}] " if source_name else ""
        print(f"{prefix}{self.name}'s {stat_name} {direction}!")

    def reset_stats(self):
        self.stat_stages = {k: 0 for k in self.stat_stages}

    def take_damage(self, damage):
        self.hp -= damage
        if self.hp < 0: self.hp = 0

    def apply_status(self, status):
        if self.status is None:
            if status == "BRN" and "Fire" in self.types: return
            if status == "PAR" and "Electric" in self.types: return
            self.status = status
            if status == "BRN": print(f"{self.name} was burned!")
            elif status == "PAR": print(f"{self.name} is paralyzed! It may be unable to move!")
        else: print(f"{self.name} is already {self.status}!")

    def is_fainted(self): return self.hp <= 0

class Team:
    def __init__(self, name, roster):
        self.name = name
        self.roster = roster
        self.active_idx = 0

    def get_active(self): return self.roster[self.active_idx]
    def has_available_pokemon(self): return any(not p.is_fainted() for p in self.roster)
    def get_total_hp(self): return sum(p.hp for p in self.roster)
    def get_max_hp(self): return sum(p.max_hp for p in self.roster)
    def get_alive_count(self): return sum(1 for p in self.roster if not p.is_fainted())

    def switch_pokemon(self, new_idx, opponent=None):
        if not self.roster[new_idx].is_fainted() and new_idx != self.active_idx:
            self.get_active().reset_stats() 
            self.active_idx = new_idx
            new_active = self.get_active()
            print(f"\n{self.name} sent out {new_active.name}!")
            if new_active.ability == "Intimidate" and opponent:
                print(f"[{new_active.name}'s Intimidate]")
                opponent.modify_stat("attack", -1)
            return True
        return False

    def force_switch(self, opponent=None):
        for i, p in enumerate(self.roster):
            if not p.is_fainted():
                self.switch_pokemon(i, opponent)
                return

def calculate_damage(attacker, defender, move):
    if move.category == "Status": return 0, 1.0 
    
    if defender.ability == "Levitate" and move.type == "Ground":
        print(f"[{defender.name}'s Levitate makes Ground moves miss!]")
        return 0, 0.0

    a_stat = attacker.get_stat("attack") if move.category == "Physical" else attacker.get_stat("sp_atk")
    d_stat = defender.get_stat("defense") if move.category == "Physical" else defender.get_stat("sp_def")

    base_damage = ((42 * move.power * (a_stat / d_stat)) / 50) + 2
    
    if attacker.hp <= (attacker.max_hp / 3):
        if attacker.ability == "Blaze" and move.type == "Fire": base_damage *= 1.5
        elif attacker.ability == "Torrent" and move.type == "Water": base_damage *= 1.5
        elif attacker.ability == "Overgrow" and move.type == "Grass": base_damage *= 1.5

    if attacker.status == "BRN" and move.category == "Physical": base_damage //= 2

    stab = 1.5 if move.type in attacker.types else 1.0
    type_mult = get_multiplier(move.type, defender.types)
    return int(base_damage * stab * type_mult), type_mult