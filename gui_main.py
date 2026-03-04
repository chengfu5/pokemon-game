# gui_main.py
import pygame
import sys
import json
import random
import time

from core.models import Pokemon, Team, calculate_damage
from ai.ml_tracker import WinProbabilityModel

# --- PYGAME SETUP ---
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pokemon AI Simulator")
clock = pygame.time.Clock()

# --- COLORS & FONTS ---
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
GRAY, DARK_GRAY = (220, 220, 220), (100, 100, 100)
GREEN, YELLOW, RED = (50, 200, 50), (220, 200, 0), (220, 50, 50)
BLUE, PURPLE = (50, 100, 200), (150, 50, 200)

font = pygame.font.SysFont("Arial", 24, bold=True)
small_font = pygame.font.SysFont("Arial", 18)
large_font = pygame.font.SysFont("Arial", 32, bold=True)

# --- UI STATES ---
MAIN_MENU = "main"
FIGHT_MENU = "fight"
SWITCH_MENU = "switch"
MESSAGE_STATE = "message"
PROCESS_TURN = "process_turn"
GAME_OVER = "game_over"

class BattleGUI:
    def __init__(self, player_team, ai_team):
        self.player_team = player_team
        self.ai_team = ai_team
        self.ml_tracker = WinProbabilityModel()
        self.sprite_cache = {}
        
        self.state = MAIN_MENU
        self.post_message_state = MAIN_MENU
        self.forced_switch = False
        
        self.turn_actions = []
        self.end_of_turn_pending = False
        
        self.msg_queue = []
        self.current_msg = ""
        self.msg_timer = 0
        self.MSG_DURATION = 90 # 1.5 seconds at 60fps
        
        self.btn_fight = pygame.Rect(450, 480, 150, 50)
        self.btn_switch = pygame.Rect(610, 480, 150, 50)
        self.btn_back = pygame.Rect(610, 540, 150, 50)
        self.move_btns = [
            pygame.Rect(50, 480, 350, 50), pygame.Rect(410, 480, 350, 50),
            pygame.Rect(50, 540, 350, 50), pygame.Rect(410, 540, 350, 50)
        ]
        self.switch_btns = [pygame.Rect(80 + (i % 2) * 330, 100 + (i // 2) * 110, 310, 90) for i in range(6)]

        self.queue_msg(f"Rival AI sent out {ai_team.get_active().name}!")
        self.queue_msg(f"Go! {player_team.get_active().name}!")
        self.trigger_entry_hazards(player_team.get_active(), ai_team.get_active())
        self.trigger_entry_hazards(ai_team.get_active(), player_team.get_active())

    def queue_msg(self, text):
        self.msg_queue.append(text)
        if self.state != MESSAGE_STATE:
            self.post_message_state = self.state
            self.state = MESSAGE_STATE

    def trigger_entry_hazards(self, entrant, opponent):
        if entrant.ability == "Intimidate":
            self.queue_msg(f"[{entrant.name}'s Intimidate]")
            opponent.modify_stat("attack", -1)
            self.queue_msg(f"{opponent.name}'s attack fell!")

    def execute_single_action(self, action):
        # --- THE FIX: DELAYED AI SWITCHING ---
        if action["type"] == "ai_forced_switch":
            team = action["team"]
            team.force_switch() # Now the backend updates exactly when the text begins!
            self.queue_msg(f"Foe sent out {team.get_active().name}!")
            opponent = self.player_team.get_active()
            self.trigger_entry_hazards(team.get_active(), opponent)
            return
            
        team = action["actor"]
        original_user = action["user"]
        
        if original_user.is_fainted() or (action["type"] == "attack" and team.get_active() != original_user):
            return

        active_poke = team.get_active()
        prefix = action["prefix"]
        defender_team = self.ai_team if team == self.player_team else self.player_team
        defender = defender_team.get_active()

        if action["type"] == "switch":
            team.switch_pokemon(action["target_idx"])
            self.queue_msg(f"{'You' if team == self.player_team else 'Foe'} sent out {team.get_active().name}!")
            self.trigger_entry_hazards(team.get_active(), defender)
            
        elif action["type"] == "attack":
            if active_poke.status == "PAR" and random.random() < 0.25:
                self.queue_msg(f"{prefix} {active_poke.name} is paralyzed! It can't move!")
                return

            move = action["move"]
            self.queue_msg(f"{prefix} {active_poke.name} used {move.name}!")
            
            if move.category == "Status":
                if move.status_effect: 
                    defender.apply_status(move.status_effect)
                    self.queue_msg(f"{defender.name} was inflicted with {move.status_effect}!")
                elif move.stat_change: 
                    active_poke.modify_stat(move.stat_change["stat"], move.stat_change["stages"])
                    self.queue_msg(f"{active_poke.name}'s stats changed!")
            else:
                damage, mult = calculate_damage(active_poke, defender, move)
                defender.take_damage(damage)
                if mult > 1.0: self.queue_msg("It's super effective!")
                elif 0 < mult < 1.0: self.queue_msg("It's not very effective...")
                elif mult == 0: self.queue_msg(f"It had no effect on {defender.name}!")
            
            if defender.is_fainted():
                self.queue_msg(f"{defender.name} fainted!")
                
                if not defender_team.has_available_pokemon():
                    self.queue_msg("*** BATTLE OVER ***")
                    self.post_message_state = GAME_OVER
                    return
                
                if defender_team == self.player_team:
                    self.forced_switch = True
                    self.post_message_state = SWITCH_MENU
                else:
                    # THE FIX: Queue the AI switch instead of executing it instantly
                    self.turn_actions.insert(0, {"type": "ai_forced_switch", "team": defender_team})

    def execute_end_of_turn(self):
        for team in [self.player_team, self.ai_team]:
            active = team.get_active()
            if not active.is_fainted() and active.status == "BRN":
                active.take_damage(active.max_hp // 8)
                self.queue_msg(f"{active.name} was hurt by its burn!")
                
                if active.is_fainted():
                    self.queue_msg(f"{active.name} fainted!")
                    if not team.has_available_pokemon():
                        self.queue_msg("*** BATTLE OVER ***")
                        self.post_message_state = GAME_OVER
                        return
                    if team == self.player_team:
                        self.forced_switch = True
                        self.post_message_state = SWITCH_MENU
                    else:
                        # THE FIX: Handle end-of-turn burn AI faints properly
                        self.turn_actions.insert(0, {"type": "ai_forced_switch", "team": team})
                        self.post_message_state = PROCESS_TURN

    def handle_click(self, pos):
        if self.state == MAIN_MENU:
            if self.btn_fight.collidepoint(pos): self.state = FIGHT_MENU
            elif self.btn_switch.collidepoint(pos): 
                self.forced_switch = False
                self.state = SWITCH_MENU
                
        elif self.state == FIGHT_MENU:
            if self.btn_back.collidepoint(pos): self.state = MAIN_MENU
            else:
                p_active = self.player_team.get_active()
                for i, btn in enumerate(self.move_btns):
                    if i < len(p_active.moves) and btn.collidepoint(pos):
                        ai_active = self.ai_team.get_active()
                        ai_action = {"type": "attack", "move": random.choice(ai_active.moves), "actor": self.ai_team, "prefix": "Foe's", "user": ai_active}
                        p_action = {"type": "attack", "move": p_active.moves[i], "actor": self.player_team, "prefix": "Your", "user": p_active}
                        
                        self.turn_actions = sorted([p_action, ai_action], key=lambda a: (1 if a["type"] == "switch" else 0, a["actor"].get_active().get_stat("speed") + random.random()), reverse=True)
                        self.end_of_turn_pending = True
                        self.state = PROCESS_TURN
                        
        elif self.state == SWITCH_MENU:
            if not self.forced_switch and self.btn_back.collidepoint(pos):
                self.state = MAIN_MENU
            else:
                for i, btn in enumerate(self.switch_btns):
                    if btn.collidepoint(pos) and i != self.player_team.active_idx:
                        if not self.player_team.roster[i].is_fainted():
                            if self.forced_switch:
                                self.player_team.switch_pokemon(i)
                                self.state = PROCESS_TURN 
                                self.queue_msg(f"You sent out {self.player_team.get_active().name}!")
                                self.trigger_entry_hazards(self.player_team.get_active(), self.ai_team.get_active())
                                self.forced_switch = False
                            else:
                                ai_active = self.ai_team.get_active()
                                ai_action = {"type": "attack", "move": random.choice(ai_active.moves), "actor": self.ai_team, "prefix": "Foe's", "user": ai_active}
                                p_action = {"type": "switch", "target_idx": i, "actor": self.player_team, "prefix": "Your", "user": self.player_team.get_active()}
                                
                                self.turn_actions = sorted([p_action, ai_action], key=lambda a: (1 if a["type"] == "switch" else 0, a["actor"].get_active().get_stat("speed") + random.random()), reverse=True)
                                self.end_of_turn_pending = True
                                self.state = PROCESS_TURN

    def update(self):
        if self.state == MESSAGE_STATE:
            if self.msg_timer <= 0:
                if self.msg_queue:
                    self.current_msg = self.msg_queue.pop(0)
                    self.msg_timer = self.MSG_DURATION
                else:
                    self.state = self.post_message_state
            else:
                self.msg_timer -= 1
                
        elif self.state == PROCESS_TURN:
            if self.turn_actions:
                action = self.turn_actions.pop(0)
                self.execute_single_action(action)
            elif self.end_of_turn_pending:
                self.execute_end_of_turn()
                self.end_of_turn_pending = False
            else:
                self.state = MAIN_MENU

    def get_sprite(self, poke_id, is_player):
        cache_key = f"{poke_id}_{is_player}"
        if cache_key not in self.sprite_cache:
            folder = "back" if is_player else "front"
            path = f"data/sprites/{folder}/{poke_id}.png"
            try:
                img = pygame.image.load(path).convert_alpha()
                scale = 3 if is_player else 2.5
                img = pygame.transform.scale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
                self.sprite_cache[cache_key] = img
            except Exception:
                img = pygame.Surface((150, 150))
                img.fill(BLUE if is_player else RED)
                self.sprite_cache[cache_key] = img
        return self.sprite_cache[cache_key]

    def draw_hp_bar(self, x, y, current_hp, max_hp, is_player):
        width, height = 200, 15
        pct = max(0.0, current_hp / max_hp)
        color = GREEN if pct > 0.5 else YELLOW if pct > 0.2 else RED
            
        pygame.draw.rect(screen, DARK_GRAY, (x, y, width, height))
        pygame.draw.rect(screen, color, (x, y, int(width * pct), height))
        pygame.draw.rect(screen, BLACK, (x, y, width, height), 2)

        if is_player:
            hp_text = small_font.render(f"{int(current_hp)} / {max_hp}", True, BLACK)
            screen.blit(hp_text, (x + 120, y + 20))

    def draw_ml_tracker(self):
        current_state = {
            "p_total_hp": self.player_team.get_total_hp(), "p_max_hp": self.player_team.get_max_hp(),
            "p_alive": self.player_team.get_alive_count(), "ai_total_hp": self.ai_team.get_total_hp(),
            "ai_max_hp": self.ai_team.get_max_hp(), "ai_alive": self.ai_team.get_alive_count()
        }
        win_prob = self.ml_tracker.predict_win_probability(current_state) * 100
        box = pygame.Rect(WIDTH//2 - 120, 10, 240, 40)
        pygame.draw.rect(screen, PURPLE, box, border_radius=10)
        pygame.draw.rect(screen, BLACK, box, 2, border_radius=10)
        screen.blit(font.render(f"ML Win Prob: {win_prob:.1f}%", True, WHITE), (box.x + 15, box.y + 7))

    def draw_scene(self):
        screen.fill(WHITE)
        p_active = self.player_team.get_active()
        ai_active = self.ai_team.get_active()

        if self.state != SWITCH_MENU:
            # Enemy (Top Right)
            if not ai_active.is_fainted():
                pygame.draw.ellipse(screen, GRAY, (550, 220, 180, 40)) 
                screen.blit(self.get_sprite(ai_active.id, is_player=False), (550, 60)) 
            
            pygame.draw.rect(screen, GRAY, (30, 30, 300, 80), border_radius=10)
            pygame.draw.rect(screen, BLACK, (30, 30, 300, 80), 3, border_radius=10)
            
            # Explicitly draw Name on the left, Level on the right
            status_txt = f" [{ai_active.status}]" if ai_active.status else ""
            screen.blit(font.render(ai_active.name.upper() + status_txt, True, BLACK), (50, 40))
            screen.blit(small_font.render("Lv.100", True, BLACK), (265, 45)) # Right-aligned
            
            self.draw_hp_bar(50, 75, ai_active.hp, ai_active.max_hp, is_player=False)

            # Player (Bottom Left)
            if not p_active.is_fainted():
                pygame.draw.ellipse(screen, GRAY, (100, 380, 220, 50))
                screen.blit(self.get_sprite(p_active.id, is_player=True), (100, 160))
            
            pygame.draw.rect(screen, GRAY, (450, 320, 300, 100), border_radius=10)
            pygame.draw.rect(screen, BLACK, (450, 320, 300, 100), 3, border_radius=10)
            
            # Explicitly draw Name on the left, Level on the right
            status_txt = f" [{p_active.status}]" if p_active.status else ""
            screen.blit(font.render(p_active.name.upper() + status_txt, True, BLACK), (470, 330))
            screen.blit(small_font.render("Lv.100", True, BLACK), (685, 335)) # Right-aligned
            
            self.draw_hp_bar(470, 365, p_active.hp, p_active.max_hp, is_player=True)
            
            self.draw_ml_tracker()

            # BOTTOM MENU BOX
            pygame.draw.rect(screen, GRAY, (0, 450, WIDTH, 150))
            pygame.draw.rect(screen, BLACK, (0, 450, WIDTH, 150), 5)

            if self.state == MAIN_MENU:
                screen.blit(font.render(f"What will {p_active.name} do?", True, BLACK), (40, 490))
                pygame.draw.rect(screen, RED, self.btn_fight, border_radius=5)
                screen.blit(font.render("FIGHT", True, WHITE), (self.btn_fight.x + 40, self.btn_fight.y + 10))
                pygame.draw.rect(screen, BLUE, self.btn_switch, border_radius=5)
                screen.blit(font.render("SWITCH", True, WHITE), (self.btn_switch.x + 30, self.btn_switch.y + 10))

            elif self.state == FIGHT_MENU:
                for i, move in enumerate(p_active.moves):
                    btn = self.move_btns[i]
                    pygame.draw.rect(screen, WHITE, btn, border_radius=5)
                    pygame.draw.rect(screen, BLACK, btn, 2, border_radius=5)
                    screen.blit(font.render(move.name, True, BLACK), (btn.x + 20, btn.y + 5))
                    screen.blit(small_font.render(f"{move.type} | Pwr: {move.power}", True, DARK_GRAY), (btn.x + 20, btn.y + 30))

                pygame.draw.rect(screen, DARK_GRAY, self.btn_back, border_radius=5)
                screen.blit(font.render("BACK", True, WHITE), (self.btn_back.x + 40, self.btn_back.y + 10))

            elif self.state == MESSAGE_STATE:
                screen.blit(large_font.render(self.current_msg, True, BLACK), (40, 500))
                
            elif self.state == GAME_OVER:
                msg = "YOU WON!" if self.player_team.has_available_pokemon() else "YOU BLACKED OUT!"
                screen.blit(large_font.render(msg, True, BLACK), (40, 500))

        elif self.state == SWITCH_MENU:
            screen.blit(large_font.render("Choose a Pokemon", True, BLACK), (50, 30))
            for i, p in enumerate(self.player_team.roster):
                btn = self.switch_btns[i]
                color = RED if p.is_fainted() else GREEN if i == self.player_team.active_idx else WHITE
                pygame.draw.rect(screen, color, btn, border_radius=10)
                pygame.draw.rect(screen, BLACK, btn, 3, border_radius=10)
                
                screen.blit(font.render(p.name, True, BLACK), (btn.x + 20, btn.y + 10))
                stat = "FNT" if p.is_fainted() else f"Lv.100  |  HP: {p.hp}/{p.max_hp}  {p.status or ''}"
                screen.blit(small_font.render(stat, True, BLACK), (btn.x + 20, btn.y + 50))
                
            if not self.forced_switch:
                pygame.draw.rect(screen, DARK_GRAY, self.btn_back, border_radius=5)
                screen.blit(font.render("BACK", True, WHITE), (self.btn_back.x + 40, self.btn_back.y + 10))

def main():
    try:
        with open('data/pokemon_data.json', 'r') as f:
            pokedex = json.load(f)
    except FileNotFoundError:
        print("Error: Run fetch_data.py first!")
        sys.exit()

    random.seed(time.time()) 
    player_team = Team("Player", [Pokemon(random.choice(pokedex)) for _ in range(6)])
    ai_team = Team("Rival AI", [Pokemon(random.choice(pokedex)) for _ in range(6)])
    
    gui = BattleGUI(player_team, ai_team)

    while True:
        gui.update() 
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and gui.state not in [MESSAGE_STATE, PROCESS_TURN]:
                if event.button == 1: 
                    gui.handle_click(event.pos)

        gui.draw_scene()
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()