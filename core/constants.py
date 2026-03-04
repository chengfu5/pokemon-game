# core/constants.py

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

def get_stat_multiplier(stage):
    if stage > 0: return (2 + stage) / 2.0
    elif stage < 0: return 2.0 / (2 - stage)
    return 1.0

# --- THE MASTER MOVE DATABASE ---
# If a Pokemon authentically learns a move on this list, it becomes available to them.
MOVE_DATABASE = {
    "Earthquake": {"type": "Ground", "power": 100, "category": "Physical"},
    "Flamethrower": {"type": "Fire", "power": 90, "category": "Special", "status_effect": "BRN"},
    "Ice Beam": {"type": "Ice", "power": 90, "category": "Special"},
    "Thunderbolt": {"type": "Electric", "power": 90, "category": "Special", "status_effect": "PAR"},
    "Swords Dance": {"type": "Normal", "power": 0, "category": "Status", "stat_change": {"stat": "attack", "stages": 2}},
    "Will O Wisp": {"type": "Fire", "power": 0, "category": "Status", "status_effect": "BRN"},
    "Thunder Wave": {"type": "Electric", "power": 0, "category": "Status", "status_effect": "PAR"},
    "Close Combat": {"type": "Fighting", "power": 120, "category": "Physical", "stat_change": {"stat": "defense", "stages": -1}},
    "Shadow Ball": {"type": "Ghost", "power": 80, "category": "Special"},
    "Surf": {"type": "Water", "power": 90, "category": "Special"},
    "Energy Ball": {"type": "Grass", "power": 90, "category": "Special"},
    "Psychic": {"type": "Psychic", "power": 90, "category": "Special"},
    "Dark Pulse": {"type": "Dark", "power": 80, "category": "Special"},
    "Dragon Claw": {"type": "Dragon", "power": 80, "category": "Physical"},
    "Iron Head": {"type": "Steel", "power": 80, "category": "Physical"},
    "Stone Edge": {"type": "Rock", "power": 100, "category": "Physical"},
    "X Scissor": {"type": "Bug", "power": 80, "category": "Physical"},
    "Brave Bird": {"type": "Flying", "power": 120, "category": "Physical"},
    "Return": {"type": "Normal", "power": 102, "category": "Physical"}
}

LEGACY_TEAMS = {
    "Cynthia (Sinnoh Champion)": ["Spiritomb", "Roserade", "Gastrodon", "Lucario", "Milotic", "Garchomp"],
    "Ash Ketchum (Kanto Classic)": ["Pikachu", "Charizard", "Squirtle", "Bulbasaur", "Pidgeot", "Snorlax"],
    "Ash Ketchum (Sinnoh)": ["Pikachu", "Infernape", "Torterra", "Staraptor", "Buizel", "Gliscor"],
    "Gary Oak": ["Pidgeot", "Alakazam", "Rhydon", "Exeggutor", "Arcanine", "Blastoise"],
    "Red (Mt. Silver)": ["Pikachu", "Espeon", "Snorlax", "Venusaur", "Charizard", "Blastoise"],
    "Lance (Johto Champion)": ["Gyarados", "Flygon", "Aerodactyl", "Salamence", "Charizard", "Dragonite"]
}