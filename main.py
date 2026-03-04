# main.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json
import uuid
import random

from core.models import Pokemon, Team, calculate_damage
from ai.ml_tracker import WinProbabilityModel
from core.constants import LEGACY_TEAMS

app = FastAPI()

# Mount the static folders so the web browser can see them
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/sprites", StaticFiles(directory="data/sprites"), name="sprites")

# Load data into memory when the server starts
with open('data/pokemon_data.json', 'r') as f:
    POKEDEX = json.load(f)

with open('data/moves_data.json', 'r') as f:
    MASTER_MOVES_DB = json.load(f)

ML_TRACKER = WinProbabilityModel()
ACTIVE_BATTLES = {}

class StartBattleRequest(BaseModel):
    player_team_names: list[str]
    opponent_name: str

class ActionRequest(BaseModel):
    battle_id: str
    action_type: str # "init", "attack", "switch", or "forced_switch"
    target_idx: int  

@app.get("/")
def read_root():
    """Serves the main HTML page."""
    return FileResponse("static/index.html")

@app.get("/api/pokedex")
def get_pokedex():
    """Sends the list of Pokemon to the browser for the Drafting Screen."""
    return [{"id": p["id"], "name": p["name"], "types": p["types"]} for p in POKEDEX]

@app.get("/api/legacy_teams")
def get_legacy_teams():
    return list(LEGACY_TEAMS.keys())

@app.post("/api/start_battle")
def start_battle(req: StartBattleRequest):
    """Creates a new battle instance and saves it in memory."""
    p_roster = [Pokemon(next(p for p in POKEDEX if p["name"] == name)) for name in req.player_team_names]
    player_team = Team("Player", p_roster)
    
    # --- THE FIX: Add a Random Team branch! ---
    if req.opponent_name == "Random Team":
        # Ensure we pick 6 unique random Pokemon
        random_picks = random.sample(POKEDEX, 6)
        ai_roster = [Pokemon(p) for p in random_picks]
    else:
        enemy_names = LEGACY_TEAMS.get(req.opponent_name, LEGACY_TEAMS["Ash Ketchum (Kanto Classic)"])
        ai_roster = [Pokemon(next(p for p in POKEDEX if p["name"] == name)) for name in enemy_names]
        
    ai_team = Team(req.opponent_name, ai_roster)
    
    battle_id = str(uuid.uuid4())
    ACTIVE_BATTLES[battle_id] = {"player": player_team, "ai": ai_team}
    
    return {"battle_id": battle_id}

@app.post("/api/action")
def play_action(req: ActionRequest):
    """The core game loop. Calculates a turn and returns step-by-step snapshots."""
    if req.battle_id not in ACTIVE_BATTLES:
        raise HTTPException(status_code=404)
        
    battle = ACTIVE_BATTLES[req.battle_id]
    p_team, ai_team = battle["player"], battle["ai"]
    events = []

    def add_event(msg):
        """Takes a perfect snapshot of the board state for the UI to draw."""
        p_active, ai_active = p_team.get_active(), ai_team.get_active()
        ml_state = {
            "p_total_hp": p_team.get_total_hp(), "p_max_hp": p_team.get_max_hp(), "p_alive": p_team.get_alive_count(),
            "ai_total_hp": ai_team.get_total_hp(), "ai_max_hp": ai_team.get_max_hp(), "ai_alive": ai_team.get_alive_count()
        }
        win_prob = ML_TRACKER.predict_win_probability(ml_state) * 100
        
        events.append({
            "text": msg,
            "ml_prob": round(win_prob, 1),
            "p": {"name": p_active.name, "id": p_active.id, "hp": p_active.hp, "max": p_active.max_hp, "fainted": p_active.is_fainted(), "status": p_active.status},
            "e": {"name": ai_active.name, "id": ai_active.id, "hp": ai_active.hp, "max": ai_active.max_hp, "fainted": ai_active.is_fainted(), "status": ai_active.status},
            "game_over": not p_team.has_available_pokemon() or not ai_team.has_available_pokemon(),
            "p_moves": [{"name": m.name, "type": m.type, "power": m.power} for m in p_active.moves],
            "p_roster": [{"name": p.name, "hp": p.hp, "max": p.max_hp, "fainted": p.is_fainted(), "status": p.status} for p in p_team.roster],
            "p_active_idx": p_team.active_idx
        })

    # --- 1. HANDLE UI INITIALIZATION ---
    if req.action_type == "init":
        add_event(f"Go! {p_team.get_active().name}!")
        return {"events": events, "require_switch": False}

    # --- 2. HANDLE FORCED MID-TURN SWITCHES ---
    if req.action_type == "forced_switch":
        p_team.switch_pokemon(req.target_idx)
        add_event(f"You sent out {p_team.get_active().name}!")
        if p_team.get_active().ability == "Intimidate":
            ai_team.get_active().modify_stat("attack", -1)
            add_event(f"Foe {ai_team.get_active().name}'s attack fell!")
        return {"events": events, "require_switch": False}

    # --- 3. STANDARD TURN QUEUE ---
    p_active = p_team.get_active()
    p_action = {"type": req.action_type, "target_idx": req.target_idx, "actor": p_team, "user": p_active, "prefix": "Your"}
    if req.action_type == "attack": 
        p_action["move"] = p_active.moves[req.target_idx]

    ai_active = ai_team.get_active()
    ai_action = {"type": "attack", "move": random.choice(ai_active.moves), "actor": ai_team, "user": ai_active, "prefix": "Foe's"}

    # Sort by speed (Switches always go first)
    actions = sorted([p_action, ai_action], key=lambda a: (1 if a["type"] == "switch" else 0, a["actor"].get_active().get_stat("speed") + random.random()), reverse=True)

    require_switch = False

    # --- 4. EXECUTE ACTIONS ---
    for action in actions:
        team, user, prefix = action["actor"], action["user"], action["prefix"]
        
        # Skip if the user died before their turn, or was swapped out
        if user.is_fainted() or (action["type"] == "attack" and team.get_active() != user): 
            continue

        active_poke = team.get_active()
        defender_team = ai_team if team == p_team else p_team
        defender = defender_team.get_active()

        if req.action_type == "forced_switch":
            p_team.get_active().is_confused = False # Cure volatile status!
            p_team.switch_pokemon(req.target_idx)
            add_event(f"You sent out {p_team.get_active().name}!")
            if p_team.get_active().ability == "Intimidate":
                ai_team.get_active().modify_stat("attack", -1)
                add_event(f"Foe {ai_team.get_active().name}'s attack fell!")
            return {"events": events, "require_switch": False}

        if action["type"] == "switch":
            active_poke.is_confused = False # Cure volatile status!
            team.switch_pokemon(action["target_idx"])
            add_event(f"{prefix} sent out {team.get_active().name}!")
            
        elif action["type"] == "attack":
            # 1. Sleep Check
            if active_poke.status == "SLP":
                if random.random() < 0.33:
                    active_poke.status = None
                    add_event(f"{active_poke.name} woke up!")
                else:
                    add_event(f"{active_poke.name} is fast asleep.")
                    continue

            # 2. Confusion Check (Happens before Paralysis!)
            if getattr(active_poke, "is_confused", False):
                # 50% chance to snap out
                if random.random() < 0.50:
                    active_poke.is_confused = False
                    add_event(f"{active_poke.name} snapped out of its confusion!")
                else:
                    add_event(f"{active_poke.name} is confused!")
                    # 50% chance to hit themselves
                    if random.random() < 0.50:
                        # Authentic Level 100 typeless self-damage (40 Base Power)
                        atk = active_poke.get_stat("attack")
                        dfn = active_poke.get_stat("defense")
                        self_damage = max(1, int(((42 * 40 * (atk / dfn)) / 50) + 2))
                        
                        active_poke.take_damage(self_damage)
                        add_event("It hurt itself in its confusion!")
                        
                        # Check if self-damage killed them
                        if active_poke.is_fainted():
                            add_event(f"{active_poke.name} fainted!")
                            if team == p_team and p_team.has_available_pokemon():
                                require_switch = True
                                break 
                            elif team == ai_team and ai_team.has_available_pokemon():
                                ai_team.force_switch()
                                add_event(f"Foe sent out {ai_team.get_active().name}!")
                        continue # Skip the actual move!

            # 3. Paralysis Turn-Skip Check
            if active_poke.status == "PAR" and random.random() < 0.25:
                add_event(f"{prefix} {active_poke.name} is paralyzed! It can't move!")
                continue

            move = action["move"]
            
            # 4. Pure Status Moves
            if move.category == "Status":
                add_event(f"{prefix} {active_poke.name} used {move.name}!")
                if getattr(move, "status_effect", None): 
                    # --- THE FIX: Separate Confusion from Primary Statuses ---
                    if move.status_effect == "Confusion":
                        if not getattr(defender, "is_confused", False):
                            defender.is_confused = True
                            add_event(f"{defender.name} became confused!")
                        else:
                            add_event("But it failed!")
                    else:
                        if not defender.status:
                            defender.apply_status(move.status_effect)
                            add_event(f"{defender.name} was inflicted with {move.status_effect}!")
                        else:
                            add_event("But it failed!")
                        
                elif getattr(move, "stat_change", None): 
                    stat_name = move.stat_change["stat"]
                    stages = move.stat_change["stages"]
                    target = active_poke if stages > 0 else defender
                    target.modify_stat(stat_name, stages)
                    
                    display_stat = stat_name.replace("_", " ").title()
                    if stages == 1: change_text = "rose!"
                    elif stages >= 2: change_text = "rose sharply!"
                    elif stages == -1: change_text = "fell!"
                    elif stages <= -2: change_text = "harshly fell!"
                    else: change_text = "changed!"
                        
                    add_event(f"{target.name}'s {display_stat} {change_text}")
                else:
                    add_event("But it failed!")
            
            # 5. Damaging Moves
            else:
                damage, mult = calculate_damage(active_poke, defender, move)
                defender.take_damage(damage)
                
                add_event(f"{prefix} {active_poke.name} used {move.name}!")
                
                if mult > 1.0: add_event("It's super effective!")
                elif 0 < mult < 1.0: add_event("It's not very effective...")
                elif mult == 0: add_event("It had no effect...")
                
                # Secondary Status Effects
                if mult > 0 and not defender.is_fainted() and getattr(move, "status_effect", None):
                    if move.status_effect == "Confusion":
                        if not getattr(defender, "is_confused", False) and random.random() < 0.20: 
                            defender.is_confused = True
                            add_event(f"{defender.name} became confused!")
                    else:
                        if not defender.status and random.random() < 0.20: 
                            defender.apply_status(move.status_effect)
                            add_event(f"{defender.name} was inflicted with {move.status_effect}!")
            if defender.is_fainted():
                add_event(f"{defender.name} fainted!")
                if defender_team == p_team and p_team.has_available_pokemon():
                    require_switch = True
                    break # Halt turn resolution so player can pick a new Pokemon
                elif defender_team == ai_team and ai_team.has_available_pokemon():
                    ai_team.force_switch()
                    add_event(f"Foe sent out {ai_team.get_active().name}!")

    # --- 5. END OF TURN EFFECTS ---
    if not require_switch:
        for team in [p_team, ai_team]:
            active = team.get_active()
            if not active.is_fainted() and active.status in ["BRN", "PSN"]:
                active.take_damage(active.max_hp // 8)
                effect = "burn" if active.status == "BRN" else "poison"
                add_event(f"{active.name} was hurt by its {effect}!")
                
                if active.is_fainted():
                    add_event(f"{active.name} fainted!")
                    if team == p_team and p_team.has_available_pokemon():
                        require_switch = True
                        break 
                    elif team == ai_team and ai_team.has_available_pokemon():
                        ai_team.force_switch()
                        add_event(f"Foe sent out {ai_team.get_active().name}!")

    return {"events": events, "require_switch": require_switch}