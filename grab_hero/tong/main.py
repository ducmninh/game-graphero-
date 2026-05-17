"""Grab Hero — main game entry point.

Run:  python main.py
"""
from __future__ import annotations
import os
import sys
import math
import random
import pygame
import time
from pathlib import Path

# Allow `python main.py` from inside this folder
sys.path.insert(0, str(Path(__file__).resolve().parent))

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
    PLAYER_BIKE_DAMAGE, SHAKE_HIT, SHAKE_EXPLODE,
    STARTING_GOLD, FONT_PATH, STORYLINE,
    WORLD_W_TILES, WORLD_H_TILES, TILE,
    GOLD, WHITE, GREEN, GRAY, SOUNDS, WEAPON_SOUNDS
)
from utils import Vec, draw_text, draw_panel, lerp_color, clamp, draw_bar
from camera import Camera
from particles import ParticleSystem
from player import Player
from enemies import Enemy
from weapons import Bullet, Weapon
from hud import HUD
from shop import Shop
from world import World, Pickup, P_GOLD, P_MEDKIT, P_AMMO
from levels import LEVEL_BUILDERS
from saveload import load_save, write_save
from hub import Hub, apply_upgrades_to_player
from pets import Pet


# ============================================================
SCENE_MENU = "menu"
SCENE_HUB = "hub"
SCENE_INTRO = "intro"
SCENE_PLAY = "play"
SCENE_PAUSE = "pause"
SCENE_GAMEOVER = "gameover"
SCENE_LEVEL_DONE = "level_done"
SCENE_VICTORY = "victory"
SCENE_MAP = "map"
SCENE_STORY = "story"
SCENE_BOSS_MODE = "boss_mode"
SCENE_BOSS_RUSH_MENU = "boss_rush_menu"
SCENE_LOBBY = "lobby"
SCENE_HOST_MODE_SELECT = "host_mode_select"
SCENE_WAITING_ROOM = "waiting_room"
SCENE_LEVEL_SELECT = "level_select"
SCENE_CHAR_SELECT = "char_select"
SCENE_SETTINGS = "settings"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.fullscreen = False
        self.clock = pygame.time.Clock()
        self.running = True
        self.t = 0.0
        # Persistent save (gold/upgrades/owned guns + pets)
        self.save = load_save()

        self.scene = SCENE_MENU
        self.dialog_queue = []
        self.waiting_room_error = ""
        self.waiting_room_error_t = 0
        self.dialog_speaker = ""
        self.dialog_text = ""
        self.intro_t = 0.0
        self.menu_blink = 0.0
        self.menu_row = 0 # Added for vertical menu selection
        self.sel_level_idx = 0 # For level selection screen
        self.char_type = self.save.get("char_type", "grab")
        self.char_sel_idx = 0 if self.char_type == "grab" else 1
        
        # Volume settings (0.0 to 1.0)
        self.vol_sfx = self.save.get("vol_sfx", 1.0)
        self.vol_bgm = self.save.get("vol_bgm", 0.5)
        import settings
        settings.SHOW_PATHFINDING = self.save.get("show_pathfinding", True)
        self.settings_sel = 0 # 0: BGM, 1: SFX, 2: Pathfinding, 3: Back
        self.lobby_sel = 0    # 0: Host, 1: Connect, 2: Back
        self.lobby_ip = ""
        self.lobby_connecting = False
        self.lobby_connect_err = ""
        self.lobby_connect_success = False
        self.boss_rush_sel = 0  # 0: Solo, 1: Co-op, 2: Back
        self.host_mode_sel = 0   # 0: Journey, 1: Boss Rush All, 2: Cancel

        from network import NetworkManager
        self.network = NetworkManager(self)

        self.level_idx = 0
        self.level_seed = 0
        self.world: World | None = None
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.players: list[Player] = [] # Changed to list for multiplayer
        self.player_idx = 0 # My player index in the list
        self.network_players = {} # Dummy Player dictionary for peer rendering
        self.camera: Camera | None = None
        self.particles = ParticleSystem()
        self.hud = HUD()
        self.shop: Shop | None = None
        self.level_name = ""
        self.biome = ""
        self.boss_ref: Enemy | None = None
        self.intro_lines: list[str] = []
        self.shop = None
        self.active_pet = None
        self.pvp_enabled = False
        self.pvp_winner = None
        self.pvp_host_score = 0
        self.pvp_client_score = 0
        self.my_id = random.randint(1000, 9999)
        self.pending_pvp_hits = [] # list of {"target": id, "dmg": val}
        self.pending_enemy_hits = [] # list of {"idx": i, "dmg": val} for client zombie hits
        self.last_net_update = 0
        self.outro_t = 0.0
        self.victory_t = 0.0
        self.gameover_t = 0.0
        self.objective_pos = None
        self.dog_radar_path = []
        self.dog_radar_timer = 0.0
        self.boss_radar_path = []
        self.boss_radar_timer = 0.0
        self.autoplay_enabled = False
        self.autoplay_path = []
        self.autoplay_timer = 0.0
        self.rada_enabled = False

        # Persistent save (gold/upgrades/owned guns + pets)
        self.hub: Hub | None = None
        self.active_pet: Pet | None = None

        # Load sounds
        self.sounds = {}
        try:
            pygame.mixer.init()
            for key, filename in WEAPON_SOUNDS.items():
                path = SOUNDS / filename
                if path.exists():
                    self.sounds[key] = pygame.mixer.Sound(str(path))
                    self.sounds[key].set_volume(1.0)
            
            # Load BGM (Will be managed dynamically in run loop)
            bgm_path = SOUNDS / "bgm_journey.wav"
            if bgm_path.exists():
                pygame.mixer.music.load(str(bgm_path))
                pygame.mixer.music.set_volume(self.vol_bgm)
        except Exception as e:
            print(f"Error initializing mixer/sounds: {e}")

    def play_sound(self, key):
        if key in self.sounds:
            self.sounds[key].set_volume(self.vol_sfx)
            self.sounds[key].play()

    def manage_bgm(self):
        """Play BGM only in menu/hub/etc, stop it during gameplay/story."""
        try:
            pygame.mixer.music.set_volume(self.vol_bgm)
            outside_scenes = (SCENE_MENU, SCENE_HUB, SCENE_LOBBY,
                              SCENE_LEVEL_SELECT, SCENE_CHAR_SELECT, SCENE_SETTINGS,
                              SCENE_BOSS_RUSH_MENU, SCENE_HOST_MODE_SELECT)
            if self.scene in outside_scenes:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1)
            else:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
        except:
            pass

    @property
    def player(self):
        """Helper to return my local player."""
        if not self.players: return None
        return self.players[self.player_idx]

    @player.setter
    def player(self, val):
        if not self.players:
            self.players = [val]
            self.player_idx = 0
        else:
            self.players[self.player_idx] = val

    # ==================================================================
    def open_hub(self):
        """Bank the player's current run-gold into the save, then open the
        hub overlay. Resets level progress so the next run starts fresh."""
        if self.player is not None:
            # Bank whatever gold the player ended with into the persistent save
            self.save["gold"] += int(getattr(self.player, "gold", 0))
        write_save(self.save)
        self.level_idx = 0
        self.hub = Hub(self.save)
        self.scene = SCENE_HUB

    def start_run_from_hub(self):
        """Launch a new run from the hub: rebuild the player with hub
        upgrades/owned guns, spawn the equipped pet, load level 0."""
        write_save(self.save)
        self.player = Player(Vec(0, 0), self.char_type)
        self.player.gold = STARTING_GOLD  # run-only gold
        # apply unlocked guns from save
        for key in self.save.get("owned_guns", ["pistol"]):
            if key not in self.player.weapons:
                self.player.add_weapon(key)
        # apply persistent upgrades
        apply_upgrades_to_player(self.player, self.save)
        # spawn pet
        eq = self.save.get("equipped_pet")
        self.active_pet = Pet(eq, Vec(0, 0)) if eq else None
        self.level_idx = 0
        self.load_level(0)
        if self.active_pet is not None:
            self.active_pet.pos = Vec(self.player.pos)
        self.scene = SCENE_STORY
        self.intro_t = 0.0

    def start_new_game(self):
        """Legacy entry: jump to the hub instead of straight into level 1."""
        self.open_hub()

    def load_level(self, idx):
        # Ensure idx is within bounds
        idx = max(0, min(idx, len(LEVEL_BUILDERS) - 1))
        self.pvp_enabled = (idx == 13)
        if self.pvp_enabled:
            self.pvp_host_score = 0
            self.pvp_client_score = 0
            self.pvp_winner = None
        
        # Share and enforce the exact same random seed in multiplayer
        if self.network.running:
            if self.network.is_host:
                self.level_seed = random.randint(10000, 999999)
            random.seed(self.level_seed)
            
        builder = LEVEL_BUILDERS[idx]
        
        # Always create a fresh world to ensure tiles and solids are correctly placed
        # from the builder's logic without any residue from previous levels.
        world, enemies, name, biome = builder()
        self.world = world
            
        self.enemies = enemies
        self.level_name = name
        self.biome = biome
        self.bullets = []
        self.particles = ParticleSystem()
        # find boss
        self.boss_ref = next((e for e in enemies if e.is_boss), None)
        self.hud.clear_boss()
        # set player pos
        if self.player is None:
            self.player = Player(self.world.spawn, self.char_type)
        else:
            self.player.pos = Vec(self.world.spawn)
            self.player.alive = True
            self.player.hp = max(self.player.hp, int(self.player.max_hp * 0.8))
            self.player.invuln_t = 5.0
            self.player.on_bike = False
            self.player.weapon.reloading = False
            self.player.weapon.ammo_in_mag = self.player.weapon.mag_size
        
        # apply hub upgrades + guns
        owned = self.save.get("owned_guns", ["pistol"])
        if len(owned) <= 1:
            self.save = load_save()
            owned = self.save.get("owned_guns", ["pistol"])
        
        last_weapon = owned[-1] if owned else "pistol"
        self.player.switch_weapon(last_weapon)
        for k in self.save.get("owned_guns", []):
            if k not in self.player.weapons:
                self.player.add_weapon(k)
        
        apply_upgrades_to_player(self.player, self.save)
        if self.active_pet is not None:
            self.active_pet.pos = Vec(self.player.pos) + Vec(-40, 30)
            self.active_pet.alive = True

        ww, wh = self.world.pixel_size()
        self.camera = Camera(ww, wh)
        self.camera.offset = Vec(self.player.pos.x - SCREEN_WIDTH // 2,
                                 self.player.pos.y - SCREEN_HEIGHT // 2)

        # Objective marker (boss pos)
        if self.boss_ref:
            self.objective_pos = Vec(self.boss_ref.pos)
        else:
            self.objective_pos = None
        
        self.hud.set_message(name, 3.0)
        self.shop = Shop(idx + 1)

    # ==================================================================
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 1 / 30)  # avoid huge dt
            self.t += dt
            self.handle_events()
            self.manage_bgm()

            # Unified Client scene & level synchronization
            if self.network.running and not self.network.is_host:
                host_status = self.network.peer_data.get("host_status")
                if host_status:
                    # Synchronize mode
                    self._waiting_room_mode = host_status.get("mode", "journey")
                    
                    h_scene = host_status.get("scene")
                    h_level = host_status.get("level_idx", self.level_idx)
                    h_seed = host_status.get("level_seed", 0)
                    
                    # Ensure level is loaded if it hasn't been yet or Host changed levels or seed changed
                    needs_load = (h_level != self.level_idx) or (h_seed != getattr(self, "level_seed", 0)) or (self.world is None or self.camera is None)
                    if needs_load and h_scene in ("story", "play", "level_done", "gameover", "victory"):
                        # Re-create player if needed
                        if not self.player:
                            self.player = Player(Vec(0, 0), self.char_type)
                            apply_upgrades_to_player(self.player, self.save)
                        self.level_idx = h_level
                        self.level_seed = h_seed
                        self.load_level(self.level_idx)
                    
                    if h_scene != self.scene:
                        if h_scene == "victory":
                            self.scene = SCENE_VICTORY
                            self.victory_t = 0
                        elif h_scene == "level_done":
                            self.scene = SCENE_LEVEL_DONE
                            self.outro_t = 0
                        elif h_scene == "gameover":
                            self.scene = SCENE_GAMEOVER
                            self.gameover_t = 0
                        elif h_scene == "story":
                            if not self.player:
                                self.player = Player(Vec(0, 0), self.char_type)
                                apply_upgrades_to_player(self.player, self.save)
                            self.scene = SCENE_STORY
                            self.intro_t = 0
                        elif h_scene == "play":
                            if not self.player:
                                self.player = Player(Vec(0, 0), self.char_type)
                                apply_upgrades_to_player(self.player, self.save)
                            self.scene = SCENE_PLAY
                        elif h_scene == "waiting_room":
                            self.scene = SCENE_WAITING_ROOM

            if self.scene == SCENE_PLAY:
                if getattr(self, "pvp_winner", None):
                    self.update_pvp_end(dt)
                elif self.dialog_queue:
                    # dialog pause: only update handle_events
                    pass
                else:
                    self.update_play(dt)
            elif self.scene == SCENE_MENU:
                self.menu_blink += dt
            elif self.scene == SCENE_HUB:
                if self.hub is not None:
                    self.hub.update(dt)
                    if self.hub.exit_to_play:
                        # Launch a run with applied upgrades + pet
                        self.start_run_from_hub()
            elif self.scene == SCENE_INTRO:
                self.intro_t += dt
                if self.intro_t > 6.0:
                    self.scene = SCENE_PLAY
            elif self.scene == SCENE_PAUSE:
                pass
            elif self.scene == SCENE_GAMEOVER:
                self.gameover_t += dt
            elif self.scene == SCENE_LEVEL_DONE:
                self.outro_t += dt
            elif self.scene == SCENE_VICTORY:
                self.victory_t += dt
            elif self.scene == SCENE_MAP:
                pass
            elif self.scene == SCENE_STORY:
                pass
            elif self.scene == SCENE_LOBBY:
                if getattr(self, 'lobby_connect_success', False):
                    self.lobby_connect_success = False
                    self.lobby_connecting = False
                    self.network.stop_lobby_listener()
                    self.scene = SCENE_WAITING_ROOM
                    continue
            elif self.scene == SCENE_WAITING_ROOM:
                pass

            # Story events check
            if self.scene == SCENE_PLAY:
                self.check_story_events()
                
            # Send network updates for both Host and Client
            if self.network.running:
                now = time.time()
                if not hasattr(self, '_last_net_update_all'): self._last_net_update_all = 0
                if now - self._last_net_update_all > 0.05: # 20fps sync
                    self._last_net_update_all = now
                    if self.network.is_host:
                        # Get list of all player IDs
                        player_ids = [self.my_id]
                        for client_data in list(self.network.peer_data.values()):
                            c_id = client_data.get("id")
                            if c_id and c_id != "host_status":
                                c_id_str = str(c_id)
                                if c_id_str not in [str(x) for x in player_ids]:
                                    player_ids.append(c_id)
                        
                        # Host sends host_status to sync waiting room scene & level index
                        player_data = {
                            "id": "host_status",
                            "scene": self.scene,
                            "mode": getattr(self, '_waiting_room_mode', 'journey'),
                            "level_idx": self.level_idx,
                            "level_seed": getattr(self, "level_seed", 0),
                            "players": player_ids
                        }
                        if self.player:
                            player_data.update({
                                "pos": [self.player.pos.x, self.player.pos.y],
                                "hp": self.player.hp,
                                "max_hp": self.player.max_hp,
                                "gun": self.player.weapon.key if self.player.weapon else "pistol",
                                "facing": [self.player.aim.x, self.player.aim.y],
                                "facing_dir": self.player.facing,
                                "on_bike": self.player.on_bike,
                                "char_type": self.player.char_type,
                                "aim_angle": self.player.aim_angle,
                                "is_shooting": (self.player.weapon.shoot_anim > 0) if self.player.weapon else False,
                                "hits": self.pending_pvp_hits
                             })
                            self.pending_pvp_hits = []
                        # Host broadcasts authoritative enemy states
                        player_data["enemies"] = [
                            {"x": e.pos.x, "y": e.pos.y, "hp": e.hp, "alive": e.alive}
                            for e in self.enemies
                        ]
                        self.network.send_update(player_data)
                    else:
                        # Client sends status/heartbeat
                        if self.scene == SCENE_PLAY and self.player:
                            self.network.send_update({
                                "id": self.my_id,
                                "pos": [self.player.pos.x, self.player.pos.y],
                                "hp": self.player.hp,
                                "max_hp": self.player.max_hp,
                                "gun": self.player.weapon.key if self.player.weapon else "pistol",
                                "facing": [self.player.aim.x, self.player.aim.y],
                                "facing_dir": self.player.facing,
                                "on_bike": self.player.on_bike,
                                "char_type": self.player.char_type,
                                "aim_angle": self.player.aim_angle,
                                "is_shooting": (self.player.weapon.shoot_anim > 0) if self.player.weapon else False,
                                "hits": self.pending_pvp_hits,
                                "enemy_hits": self.pending_enemy_hits
                            })
                            self.pending_pvp_hits = []
                            self.pending_enemy_hits = []
                        else:
                            self.network.send_update({
                                "id": self.my_id,
                                "pos": [0, 0],
                                "hp": 100,
                                "scene": self.scene
                            })

            self.draw()
            pygame.display.flip()
        pygame.quit()

    # ==================================================================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if self.scene == SCENE_PLAY and self.dialog_queue:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.next_dialog()
                continue
            
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_F11, pygame.K_f):
                    self.fullscreen = not self.fullscreen
                    if self.fullscreen:
                        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
                    else:
                        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

            if self.scene == SCENE_MENU:
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    pw, ph = 520, 520
                    px = (SCREEN_WIDTH - pw) // 2
                    py = 205
                    for i in range(9):
                        bx = px + 30
                        by = py + 25 + i * 53
                        btn_rect = pygame.Rect(bx, by, pw - 60, 44)
                        if btn_rect.collidepoint(mx, my):
                            self.menu_row = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        gear_rect = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)
                        if gear_rect.collidepoint(mx, my):
                            self.scene = SCENE_SETTINGS
                        else:
                            pw, ph = 520, 520
                            px = (SCREEN_WIDTH - pw) // 2
                            py = 205
                            for i in range(9):
                                bx = px + 30
                                by = py + 25 + i * 53
                                btn_rect = pygame.Rect(bx, by, pw - 60, 44)
                                if btn_rect.collidepoint(mx, my):
                                    self.menu_row = i
                                    if i == 0:
                                        self.scene = SCENE_LEVEL_SELECT
                                        self.sel_level_idx = 0
                                    elif i == 1:
                                        self.scene = SCENE_LOBBY
                                        self.network.start_lobby_listener()
                                    elif i == 2:
                                        self.scene = SCENE_SETTINGS
                                    elif i == 3:
                                        self.scene = SCENE_BOSS_RUSH_MENU
                                        self.boss_rush_sel = 0
                                    elif i == 4:
                                        self.open_hub()
                                        if self.hub: self.hub.tab = 0
                                    elif i == 5:
                                        self.open_hub()
                                        if self.hub: self.hub.tab = 1
                                    elif i == 6:
                                        self.open_hub()
                                        if self.hub: self.hub.tab = 2
                                    elif i == 7:
                                        self.scene = SCENE_CHAR_SELECT
                                        self.char_sel_idx = 0 if self.char_type == "grab" else 1
                                    elif i == 8:
                                        self.running = False
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.menu_row = (self.menu_row - 1) % 9
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.menu_row = (self.menu_row + 1) % 9
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        # Action based on selected row
                        if self.menu_row == 0: # Journey
                            self.scene = SCENE_LEVEL_SELECT
                            self.sel_level_idx = 0
                        elif self.menu_row == 1: # Multiplayer
                            self.scene = SCENE_LOBBY
                            self.network.start_lobby_listener()
                        elif self.menu_row == 2: # Settings
                            self.scene = SCENE_SETTINGS
                        elif self.menu_row == 3: # Boss Rush
                            self.scene = SCENE_BOSS_RUSH_MENU
                            self.boss_rush_sel = 0
                        elif self.menu_row == 4: # Upgrade
                            self.open_hub()
                            if self.hub: self.hub.tab = 0
                        elif self.menu_row == 5: # Buy Guns
                            self.open_hub()
                            if self.hub: self.hub.tab = 1
                        elif self.menu_row == 6: # Buy Pets
                            self.open_hub()
                            if self.hub: self.hub.tab = 2
                        # 7: Đổi nhân vật
                        elif self.menu_row == 7:
                            self.scene = SCENE_CHAR_SELECT
                            self.char_sel_idx = 0 if self.char_type == "grab" else 1
                        # 8: Thoát
                        elif self.menu_row == 8:
                            self.running = False
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                continue

            if self.scene == SCENE_CHAR_SELECT:
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    bw, bh = 300, 420
                    gap = 60
                    start_x = (SCREEN_WIDTH - (bw * 2 + gap)) // 2
                    for i in range(2):
                        bx = start_x + i * 360
                        rect = pygame.Rect(bx, 180, 300, 420)
                        if rect.collidepoint(mx, my):
                            self.char_sel_idx = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        bw, bh = 300, 420
                        gap = 60
                        start_x = (SCREEN_WIDTH - (bw * 2 + gap)) // 2
                        for i in range(2):
                            bx = start_x + i * 360
                            rect = pygame.Rect(bx, 180, 300, 420)
                            if rect.collidepoint(mx, my):
                                self.char_sel_idx = i
                                self.char_type = "grab" if i == 0 else "shope"
                                self.save["char_type"] = self.char_type
                                write_save(self.save)
                                self.player = None # Force re-init with new character
                                self.scene = SCENE_MENU
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.char_sel_idx = 0
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.char_sel_idx = 1
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.char_type = "grab" if self.char_sel_idx == 0 else "shope"
                        self.save["char_type"] = self.char_type
                        write_save(self.save)
                        self.player = None # Force re-init with new character
                        self.scene = SCENE_MENU
                    elif event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_MENU
                continue

            if self.scene == SCENE_HUB:
                if event.type == pygame.KEYDOWN:
                    # Escape from hub returns to menu (keeps progress saved)
                    if event.key == pygame.K_ESCAPE:
                        write_save(self.save)
                        self.scene = SCENE_MENU
                        continue
                if self.hub is not None:
                    self.hub.handle(event)
                continue

            if self.scene == SCENE_LOBBY:
                if getattr(self, 'lobby_connecting', False):
                    continue
                
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    start_y = 265
                    for i in range(3):
                        rect = pygame.Rect(SCREEN_WIDTH // 2 - 270, start_y + i * 70, 540, 56)
                        if rect.collidepoint(mx, my):
                            self.lobby_sel = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        
                        # Discovered rooms quick connection
                        panel_rect = pygame.Rect(SCREEN_WIDTH // 2 - 300, 135, 600, 110)
                        rooms = list(self.network.discovered_rooms.items())
                        if rooms and panel_rect.collidepoint(mx, my):
                            self.lobby_ip = rooms[0][0]
                            self.lobby_sel = 1
                            
                        start_y = 265
                        for i in range(3):
                            rect = pygame.Rect(SCREEN_WIDTH // 2 - 270, start_y + i * 70, 540, 56)
                            if rect.collidepoint(mx, my):
                                self.lobby_sel = i
                                if i == 0: # Host
                                    ok = self.network.start_host()
                                    if ok:
                                        self.network.stop_lobby_listener()
                                        self.network.start_beacon()
                                        self.host_mode_sel = 0
                                        self.scene = SCENE_HOST_MODE_SELECT
                                elif i == 1: # Connect
                                    if not getattr(self, 'lobby_connecting', False):
                                        ip_to_connect = self.lobby_ip if self.lobby_ip else "127.0.0.1"
                                        self.lobby_connecting = True
                                        self.lobby_connect_err = ""
                                        self.lobby_connect_success = False
                                        
                                        def do_connect_thread():
                                            ok = self.network.connect(ip_to_connect)
                                            if ok:
                                                self.lobby_connect_success = True
                                            else:
                                                self.lobby_connect_err = self.network.host_error or "Kết nối thất bại!"
                                                self.lobby_connecting = False
                                        
                                        import threading
                                        threading.Thread(target=do_connect_thread, daemon=True).start()
                                elif i == 2: # Back
                                    self.scene = SCENE_MENU
                                    self.network.stop_lobby_listener()
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.lobby_sel = (self.lobby_sel - 1) % 3
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.lobby_sel = (self.lobby_sel + 1) % 3
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.lobby_sel == 0: # Host
                            ok = self.network.start_host()
                            if ok:
                                self.network.stop_lobby_listener()
                                self.network.start_beacon()
                                self.host_mode_sel = 0
                                self.scene = SCENE_HOST_MODE_SELECT
                        elif self.lobby_sel == 1: # Connect
                            if not getattr(self, 'lobby_connecting', False):
                                ip_to_connect = self.lobby_ip if self.lobby_ip else "127.0.0.1"
                                self.lobby_connecting = True
                                self.lobby_connect_err = ""
                                self.lobby_connect_success = False
                                
                                def do_connect_thread():
                                    ok = self.network.connect(ip_to_connect)
                                    if ok:
                                        self.lobby_connect_success = True
                                    else:
                                        self.lobby_connect_err = self.network.host_error or "Kết nối thất bại!"
                                        self.lobby_connecting = False
                                
                                import threading
                                threading.Thread(target=do_connect_thread, daemon=True).start()
                        elif self.lobby_sel == 2: # Back
                            self.scene = SCENE_MENU
                            self.network.stop_lobby_listener()
                    elif event.key == pygame.K_BACKSPACE:
                        self.lobby_ip = self.lobby_ip[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_MENU
                        self.network.stop_lobby_listener()
                    else:
                        # Character input for IP
                        allowed_chars = "0123456789.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ:_- "
                        if event.unicode and event.unicode in allowed_chars:
                            if len(self.lobby_ip) < 40:
                                self.lobby_ip += event.unicode
                continue

            if self.scene == SCENE_HOST_MODE_SELECT:
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    start_y = 248
                    for i in range(4):
                        rect = pygame.Rect(SCREEN_WIDTH // 2 - 320, start_y + i * 90, 640, 72)
                        if rect.collidepoint(mx, my):
                            self.host_mode_sel = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        start_y = 248
                        for i in range(4):
                            rect = pygame.Rect(SCREEN_WIDTH // 2 - 320, start_y + i * 90, 640, 72)
                            if rect.collidepoint(mx, my):
                                self.host_mode_sel = i
                                if i == 0: # Journey
                                    self._waiting_room_mode = "journey"
                                    self.scene = SCENE_WAITING_ROOM
                                elif i == 1: # Boss Rush
                                    self._waiting_room_mode = "boss_rush"
                                    self.scene = SCENE_WAITING_ROOM
                                elif i == 2: # PvP Arena
                                    self._waiting_room_mode = "pvp"
                                    self.scene = SCENE_WAITING_ROOM
                                elif i == 3: # Back
                                    self.network.stop()
                                    self.scene = SCENE_LOBBY
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.host_mode_sel = (self.host_mode_sel - 1) % 4
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.host_mode_sel = (self.host_mode_sel + 1) % 4
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        i = self.host_mode_sel
                        if i == 0: # Journey
                            self._waiting_room_mode = "journey"
                            self.scene = SCENE_WAITING_ROOM
                        elif i == 1: # Boss Rush
                            self._waiting_room_mode = "boss_rush"
                            self.scene = SCENE_WAITING_ROOM
                        elif i == 2: # PvP Arena
                            self._waiting_room_mode = "pvp"
                            self.scene = SCENE_WAITING_ROOM
                        elif i == 3: # Back
                            self.network.stop()
                            self.scene = SCENE_LOBBY
                    elif event.key == pygame.K_ESCAPE:
                        self.network.stop()
                        self.scene = SCENE_LOBBY
                continue

            if self.scene == SCENE_WAITING_ROOM:
                # --- Mouse support ---
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        total = len(self.network.clients) + 1
                        cy_base = 140
                        ch_h = 140
                        cgy = 16
                        cy_btm = cy_base + 2*ch_h + 2*cgy + 10
                        btn_y2 = cy_btm + 58
                        
                        cr2 = pygame.Rect(SCREEN_WIDTH//2 - 280, btn_y2, 210, 52)
                        sr2 = pygame.Rect(SCREEN_WIDTH//2 + 70, btn_y2, 210, 52)
                        
                        if cr2.collidepoint(mx, my): # HUY PHONG
                            self.network.stop()
                            self.scene = SCENE_LOBBY
                        elif sr2.collidepoint(mx, my): # BAT DAU
                            if self.network.is_host:
                                m = getattr(self, '_waiting_room_mode', 'journey')
                                if m == "journey":
                                    self.save = load_save()
                                    self.level_idx = -1
                                    self.next_level()
                                elif m == "boss_rush":
                                    self.level_idx = 11
                                    self.next_level()
                                elif m == "pvp":
                                    self.level_idx = 12
                                    self.next_level()
                            else:
                                self.waiting_room_error = "CHỈ CHỦ PHÒNG MỚI CÓ QUYỀN BẮT ĐẦU!"
                                self.waiting_room_error_t = pygame.time.get_ticks()
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.network.is_host:
                            m = getattr(self, '_waiting_room_mode', 'journey')
                            if m == "journey":
                                self.save = load_save()
                                self.level_idx = -1
                                self.next_level()
                            elif m == "boss_rush":
                                self.level_idx = 11
                                self.next_level()
                            elif m == "pvp":
                                self.level_idx = 12
                                self.next_level()
                    elif event.key == pygame.K_ESCAPE:
                        self.network.stop()
                        self.scene = SCENE_LOBBY
                continue

            if self.scene == SCENE_BOSS_RUSH_MENU:
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    start_y = 230
                    for i in range(3):
                        rect = pygame.Rect(SCREEN_WIDTH // 2 - 310, start_y + i * 97, 620, 75)
                        if rect.collidepoint(mx, my):
                            self.boss_rush_sel = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        start_y = 230
                        for i in range(3):
                            rect = pygame.Rect(SCREEN_WIDTH // 2 - 310, start_y + i * 97, 620, 75)
                            if rect.collidepoint(mx, my):
                                self.boss_rush_sel = i
                                if i == 0:  # Solo
                                    self.level_idx = 12
                                    self.load_level(12)
                                    self.scene = SCENE_PLAY
                                    self.intro_t = 0
                                elif i == 1:  # Co-op via Lobby
                                    self.scene = SCENE_LOBBY
                                    self.lobby_sel = 0
                                elif i == 2:  # Back
                                    self.scene = SCENE_MENU
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.boss_rush_sel = (self.boss_rush_sel - 1) % 3
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.boss_rush_sel = (self.boss_rush_sel + 1) % 3
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.boss_rush_sel == 0:  # Solo
                            self.level_idx = 12
                            self.load_level(12)
                            self.scene = SCENE_PLAY
                            self.intro_t = 0
                        elif self.boss_rush_sel == 1:  # Co-op via Lobby
                            self.scene = SCENE_LOBBY
                            self.lobby_sel = 0
                        elif self.boss_rush_sel == 2:  # Back
                            self.scene = SCENE_MENU
                    elif event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_MENU
                continue

            if self.scene == SCENE_INTRO:
                if event.type == pygame.KEYDOWN:
                    self.scene = SCENE_PLAY
                continue

            if self.scene == SCENE_GAMEOVER:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        # RETRY CURRENT LEVEL
                        self.load_level(self.level_idx)
                        self.scene = SCENE_PLAY
                        self.gameover_t = 0
                    elif event.key == pygame.K_h:
                        # Go back to hub (banks gold)
                        self.open_hub()
                        self.gameover_t = 0
                    elif event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_MENU
                        self.gameover_t = 0
                continue

            if self.scene == SCENE_LEVEL_DONE:
                if self.shop and self.shop.open:
                    old_open = self.shop.open
                    self.shop.handle(event, self.player)
                    if old_open and not self.shop.open:
                        # Shop closed -> go to story/next level
                        self.next_level()
                    continue # Skip other keydown checks for this event if shop handled it
                
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        # Go straight to next level (story)
                        self.next_level()
                    elif event.key == pygame.K_s: # Use S for shop
                        if self.shop:
                            self.shop.show()
                    elif event.key == pygame.K_h:
                        self.open_hub()
                continue

            if self.scene == SCENE_STORY:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                        # Client can only skip if not connected in multiplayer, or if they are the Host
                        if not self.network.running or self.network.is_host:
                            self.scene = SCENE_PLAY
                continue

            if self.scene == SCENE_VICTORY:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE,
                                     pygame.K_ESCAPE):
                        # Bank earned gold + clear progress, return to hub
                        self.open_hub()
                continue

            if self.scene == SCENE_PAUSE:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_PLAY
                    elif event.key == pygame.K_q:
                        self.scene = SCENE_MENU
                continue

            if self.scene == SCENE_SETTINGS:
                panel_w, panel_h = 600, 380
                px = (SCREEN_WIDTH - panel_w) // 2
                py = 200
                
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    # Hover highlight selection
                    if pygame.Rect(px + 40, py + 35, 520, 45).collidepoint(mx, my):
                        self.settings_sel = 0
                    elif pygame.Rect(px + 40, py + 115, 520, 45).collidepoint(mx, my):
                        self.settings_sel = 1
                    elif pygame.Rect(px + 40, py + 195, 520, 45).collidepoint(mx, my):
                        self.settings_sel = 2
                    elif pygame.Rect(SCREEN_WIDTH // 2 - 140, py + 275, 280, 50).collidepoint(mx, my):
                        self.settings_sel = 3
                        
                    # Dragging sliders (if left button is down)
                    if event.buttons[0] == 1:
                        if self.settings_sel == 0 and pygame.Rect(px + 300, py + 36, 240, 28).collidepoint(mx, my):
                            self.vol_bgm = max(0.0, min(1.0, (mx - (px + 300)) / 240.0))
                            pygame.mixer.music.set_volume(self.vol_bgm)
                        elif self.settings_sel == 1 and pygame.Rect(px + 300, py + 116, 240, 28).collidepoint(mx, my):
                            self.vol_sfx = max(0.0, min(1.0, (mx - (px + 300)) / 240.0))
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        # Direct slider clicks
                        if pygame.Rect(px + 300, py + 36, 240, 28).collidepoint(mx, my):
                            self.settings_sel = 0
                            self.vol_bgm = max(0.0, min(1.0, (mx - (px + 300)) / 240.0))
                            pygame.mixer.music.set_volume(self.vol_bgm)
                        elif pygame.Rect(px + 300, py + 116, 240, 28).collidepoint(mx, my):
                            self.settings_sel = 1
                            self.vol_sfx = max(0.0, min(1.0, (mx - (px + 300)) / 240.0))
                        # Toggles and Buttons
                        elif pygame.Rect(px + 40, py + 195, 520, 45).collidepoint(mx, my):
                            self.settings_sel = 2
                            import settings
                            settings.SHOW_PATHFINDING = not settings.SHOW_PATHFINDING
                        elif pygame.Rect(SCREEN_WIDTH // 2 - 140, py + 275, 280, 50).collidepoint(mx, my):
                            self.settings_sel = 3
                            import settings
                            self.save["vol_bgm"] = self.vol_bgm
                            self.save["vol_sfx"] = self.vol_sfx
                            self.save["show_pathfinding"] = settings.SHOW_PATHFINDING
                            write_save(self.save)
                            self.scene = SCENE_MENU
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.settings_sel = (self.settings_sel - 1) % 4
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.settings_sel = (self.settings_sel + 1) % 4
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        if self.settings_sel == 0:
                            change = -0.05 if event.key in (pygame.K_LEFT, pygame.K_a) else 0.05
                            self.vol_bgm = max(0.0, min(1.0, self.vol_bgm + change))
                            pygame.mixer.music.set_volume(self.vol_bgm)
                        elif self.settings_sel == 1:
                            change = -0.05 if event.key in (pygame.K_LEFT, pygame.K_a) else 0.05
                            self.vol_sfx = max(0.0, min(1.0, self.vol_sfx + change))
                        elif self.settings_sel == 2:
                            import settings
                            settings.SHOW_PATHFINDING = not settings.SHOW_PATHFINDING
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.settings_sel == 2:
                            import settings
                            settings.SHOW_PATHFINDING = not settings.SHOW_PATHFINDING
                        elif self.settings_sel == 3:
                            import settings
                            self.save["vol_bgm"] = self.vol_bgm
                            self.save["vol_sfx"] = self.vol_sfx
                            self.save["show_pathfinding"] = settings.SHOW_PATHFINDING
                            write_save(self.save)
                            self.scene = SCENE_MENU
                    elif event.key == pygame.K_ESCAPE:
                        import settings
                        self.save["vol_bgm"] = self.vol_bgm
                        self.save["vol_sfx"] = self.vol_sfx
                        self.save["show_pathfinding"] = settings.SHOW_PATHFINDING
                        write_save(self.save)
                        self.scene = SCENE_MENU
                continue

            if self.scene == SCENE_LEVEL_SELECT:
                # --- Mouse support ---
                if event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    island_pos = [
                        (150, 450), (300, 320), (500, 480), (700, 350), 
                        (900, 450), (1050, 300), (1150, 500)
                    ]
                    for i, pos in enumerate(island_pos):
                        rect = pygame.Rect(pos[0] - 50, pos[1] - 80, 100, 140)
                        if rect.collidepoint(mx, my):
                            self.sel_level_idx = i
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mx, my = event.pos
                        island_pos = [
                            (150, 450), (300, 320), (500, 480), (700, 350), 
                            (900, 450), (1050, 300), (1150, 500)
                        ]
                        for i, pos in enumerate(island_pos):
                            rect = pygame.Rect(pos[0] - 50, pos[1] - 80, 100, 140)
                            if rect.collidepoint(mx, my):
                                self.sel_level_idx = i
                                self.save = load_save() # RE-LOAD FROM DISK
                                self.level_idx = i - 1
                                self.player = None # Force clean recreation with all guns
                                self.next_level()
                
                # --- Keyboard support ---
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.sel_level_idx = (self.sel_level_idx - 1) % 7
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.sel_level_idx = (self.sel_level_idx + 1) % 7
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.save = load_save() # RE-LOAD FROM DISK
                        self.level_idx = self.sel_level_idx - 1
                        self.player = None # Force clean recreation with all guns
                        self.next_level()
                    elif event.key == pygame.K_ESCAPE:
                        self.scene = SCENE_MENU
                continue

            if self.scene == SCENE_MAP:
                if event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_TAB, pygame.K_ESCAPE):
                    self.scene = SCENE_PLAY
                continue

            # PLAY
            if self.scene != SCENE_PLAY:
                continue

            if self.shop and self.shop.open:
                self.shop.handle(event, self.player)
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.scene = SCENE_PAUSE
                elif event.key == pygame.K_TAB:
                    self.scene = SCENE_MAP
                elif event.key == pygame.K_r:
                    self.player.reload()
                elif event.key == pygame.K_SPACE:
                    keys = pygame.key.get_pressed()
                    dx = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
                    dy = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
                    self.player.start_dodge(dx, dy)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3,
                                   pygame.K_4, pygame.K_5, pygame.K_6,
                                   pygame.K_7):
                    idx = event.key - pygame.K_1
                    if idx < len(self.player.weapon_order):
                        self.player.switch_weapon(self.player.weapon_order[idx])
                elif event.key == pygame.K_q:
                    self.player.cycle_weapon(-1)
                elif event.key == pygame.K_e:
                    # interact: shop trigger
                    if self.shop and self.world.shop_rect and \
                            self.world.shop_rect.colliderect(self.player.rect.inflate(40, 40)):
                        self.shop.show()
                    else:
                        self.player.cycle_weapon(1)
                elif event.key == pygame.K_g:
                    import settings
                    if not settings.SHOW_PATHFINDING:
                        self.particles.text(self.player.pos + Vec(0, -24),
                                            "BẬT HIỂN THỊ THUẬT TOÁN TRONG CÀI ĐẶT!",
                                            color=(255, 100, 100))
                    else:
                        self.rada_enabled = not self.rada_enabled
                        self.particles.text(self.player.pos + Vec(0, -24),
                                            "RADA: BẬT" if self.rada_enabled else "RADA: TẮT",
                                            color=(100, 255, 255) if self.rada_enabled else (255, 100, 100))
                elif event.key == pygame.K_h:
                    self.autoplay_enabled = not self.autoplay_enabled
                    self.particles.text(self.player.pos + Vec(0, -36),
                                        "TỰ ĐỘNG (A*): BẬT" if self.autoplay_enabled else "TỰ ĐỘNG (A*): TẮT",
                                        color=(80, 255, 80) if self.autoplay_enabled else (255, 80, 80))
                elif event.key == pygame.K_b:
                    nearest = None
                    best = 9999
                    for s in self.world.solids:
                        if s.kind == "parked_bike" and s.alive:
                            d = (Vec(s.rect.center) - self.player.pos).length()
                            if d < best:
                                best = d
                                nearest = s
                    self.player.toggle_bike(nearest)
            elif event.type == pygame.MOUSEWHEEL:
                self.player.cycle_weapon(-event.y)

    # ==================================================================
    def update_play(self, dt):
        # Client synchronizes enemies from Host
        if self.network.running and not self.network.is_host:
            host_status = self.network.peer_data.get("host_status")
            if host_status:
                h_enemies = host_status.get("enemies", [])
                for i, he in enumerate(h_enemies):
                    if i < len(self.enemies):
                        e = self.enemies[i]
                        e.pos.x = he["x"]
                        e.pos.y = he["y"]
                        e.hp = he["hp"]
                        
                        # If zombie died on Host, kill it on Client and trigger effects
                        if not he["alive"] and e.alive:
                            e.alive = False
                            self.particles.blood(e.pos, count=15)
                            self.camera.add_shake(SHAKE_HIT if not e.is_boss else SHAKE_EXPLODE)
                
                # Synchronize PvP scores and winner
                self.pvp_host_score = host_status.get("host_score", self.pvp_host_score)
                self.pvp_client_score = host_status.get("client_score", self.pvp_client_score)
                self.pvp_winner = host_status.get("pvp_winner", None)
                
                if host_status.get("host_died", False):
                    # Show indicator that peer died
                    self.particles.text(self.player.pos, "ĐỐI THỦ ĐÃ HẠ GỤC!", color=(255, 60, 60), life=2.0)

        keys = pygame.key.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        mouse_world = self.camera.screen_to_world(*mouse_pos)
        mouse_buttons = pygame.mouse.get_pressed()
        auto_shoot = False

        # Autoplay variables overriding keys, mouse_world, mouse_buttons
        if self.autoplay_enabled:
            alive_enemies = [e for e in self.enemies if e.alive]
            target_pos = None
            target_enemy = None
            if alive_enemies:
                target_enemy = min(alive_enemies, key=lambda e: (e.pos - self.player.pos).length_squared())
                target_pos = pygame.Vector2(target_enemy.pos.x, target_enemy.pos.y)
            elif self.world.dog_rect:
                target_pos = pygame.Vector2(self.world.dog_rect.centerx, self.world.dog_rect.centery)
            elif self.world.exit_rect:
                target_pos = pygame.Vector2(self.world.exit_rect.centerx, self.world.exit_rect.centery)

            if target_pos:
                self.autoplay_timer += dt
                if self.autoplay_timer >= 0.2 or not self.autoplay_path:
                    self.autoplay_timer = 0.0
                    try:
                        from pathfinding import Pathfinder
                        pf = Pathfinder(self.world, ignore_boss_gates=True)
                        start_v = pygame.Vector2(self.player.pos.x, self.player.pos.y)
                        self.autoplay_path = pf.a_star(start_v, target_pos)
                    except:
                        self.autoplay_path = []

                dx = dy = 0
                if self.autoplay_path:
                    next_pt = self.autoplay_path[0]
                    if (next_pt - self.player.pos).length() < 18:
                        self.autoplay_path.pop(0)
                        if self.autoplay_path:
                            next_pt = self.autoplay_path[0]
                    
                    diff = next_pt - self.player.pos
                    if diff.length() > 0:
                        diff = diff.normalize()
                        dx = 1 if diff.x > 0.25 else (-1 if diff.x < -0.25 else 0)
                        dy = 1 if diff.y > 0.25 else (-1 if diff.y < -0.25 else 0)
                else:
                    diff = target_pos - self.player.pos
                    if diff.length() > 6:
                        diff = diff.normalize()
                        dx = 1 if diff.x > 0.25 else (-1 if diff.x < -0.25 else 0)
                        dy = 1 if diff.y > 0.25 else (-1 if diff.y < -0.25 else 0)

                class AutoplayKeys:
                    def __init__(self, x_dir, y_dir):
                        self.x_dir = x_dir
                        self.y_dir = y_dir
                    def __getitem__(self, key):
                        if key in (pygame.K_a, pygame.K_LEFT) and self.x_dir < 0: return True
                        if key in (pygame.K_d, pygame.K_RIGHT) and self.x_dir > 0: return True
                        if key in (pygame.K_w, pygame.K_UP) and self.y_dir < 0: return True
                        if key in (pygame.K_s, pygame.K_DOWN) and self.y_dir > 0: return True
                        return False

                keys = AutoplayKeys(dx, dy)

                if target_enemy:
                    mouse_world = target_enemy.pos
                    dist = (target_enemy.pos - self.player.pos).length()
                    if dist < 420:
                        auto_shoot = True
                    if self.player.weapon.ammo_in_mag == 0 and not self.player.weapon.reloading:
                        self.player.reload()
                else:
                    mouse_world = target_pos

        # Shop overlay handling: still update HUD, freeze world
        if self.shop and self.shop.open:
            self.shop.update(dt)
            self.hud.update(dt)
            return

        # Trigger boss dialog when near gate
        if self.world.boss_gate_rect and not self.world.boss_dialog_triggered:
            dist_to_gate = self.player.pos.distance_to(Vec(self.world.boss_gate_rect.center))
            if dist_to_gate < 150:
                self.trigger_boss_dialog()

        # Player update
        self.player.update(dt, keys, mouse_world, self.world, self.particles)
        
        # SAFETY SYNC: Ensure player has all owned guns
        owned = self.save.get("owned_guns", ["pistol"])
        if len(self.player.weapon_order) < len(owned):
            for k in owned:
                if k not in self.player.weapons:
                    self.player.add_weapon(k)

        # Pet update (follows player, attacks enemies)
        if self.active_pet is not None and self.active_pet.alive:
            self.active_pet.update(dt, self.player, self.enemies,
                                   self.world, self.bullets,
                                   self.particles, self.t, self.sounds)

        # Firing (auto if button held or autoplay shooting)
        if (mouse_buttons[0] or (self.autoplay_enabled and auto_shoot)) and not self.player.on_bike:
            bullets = self.player.try_fire(self.world)
            if bullets:
                self.bullets.extend(bullets)
                # Play weapon sound
                s_key = self.player.weapon.key
                self.play_sound(s_key)
                
                muzzle = self.player.pos + Vec(
                    math.cos(self.player.aim_angle),
                    math.sin(self.player.aim_angle)) * 26
                self.particles.muzzle(muzzle, self.player.aim_angle)
                self.camera.add_shake(2)

        # Bike runover damage
        if self.player.on_bike:
            for i, e in enumerate(self.enemies):
                if e.alive and self.player.rect.inflate(8, 8).colliderect(e.rect):
                    if not e.is_boss and e.kind in ("zombie", "zombie_fast",
                                                    "wild_dog"):
                        if self.network.running and not self.network.is_host:
                            self.pending_enemy_hits.append({"idx": i, "dmg": PLAYER_BIKE_DAMAGE})
                        else:
                            e.take_damage(PLAYER_BIKE_DAMAGE,
                                          self.player.aim)
                        self.particles.blood(e.pos)
                        self.player.take_damage(2)

        # Bullets
        new_bullets = []
        for b in self.bullets:
            if not b.update(dt):
                # AOE on expire if grenade
                if b.aoe:
                    self.aoe_explode(b)
                continue
            # collide world solids
            hit_solid = None
            for s in self.world.solids:
                if s.alive and s.kind in ("wall", "house", "container",
                                          "machine", "rubble", "fence",
                                          "crate"):
                    if s.rect.collidepoint(b.pos):
                        hit_solid = s
                        break
            if hit_solid:
                # If crate -> drop loot
                if hit_solid.kind == "crate":
                    hit_solid.alive = False
                    self.particles.explosion(Vec(hit_solid.rect.center),
                                             color=(180, 130, 60), count=12)
                    if random.random() < 0.5:
                        self.world.add_pickup(Pickup(
                            Vec(hit_solid.rect.center), P_GOLD, 25))
                    else:
                        self.world.add_pickup(Pickup(
                            Vec(hit_solid.rect.center), P_AMMO))
                if b.aoe:
                    self.aoe_explode(b)
                continue
            # collide drums (explode chain)
            drum_hit = None
            for s in self.world.solids:
                if s.alive and s.kind == "drum" and s.rect.collidepoint(b.pos):
                    drum_hit = s
                    break
            if drum_hit:
                self.drum_explode(drum_hit)
                continue
            # collide enemies (player bullets) / player (enemy bullets)
            consumed = False
            if b.owner == "player":
                # Check hits on other players if PvP is active
                if self.pvp_enabled:
                    for p_id, data in self.network.peer_data.items():
                        # Simple radius check for peers
                        p_pos = Vec(data["pos"][0], data["pos"][1])
                        dist = (b.pos - p_pos).length()
                        if dist < 24: # Peer radius
                            self.pending_pvp_hits.append({"target": str(p_id), "dmg": b.damage})
                            self.particles.blood(b.pos, count=10)
                            if b.aoe: self.aoe_explode(b)
                            consumed = True
                            break
                    if consumed: continue

                for i, e in enumerate(self.enemies):
                    if e.alive and e.rect.collidepoint(b.pos):
                        dirv = b.vel.normalize() if b.vel.length() > 0 else Vec(1, 0)
                        if self.network.running and not self.network.is_host:
                            self.pending_enemy_hits.append({"idx": i, "dmg": b.damage})
                            self.particles.blood(b.pos, count=8)
                        else:
                            e.take_damage(b.damage, dirv)
                            self.particles.blood(b.pos, count=8)
                        if b.aoe:
                            self.aoe_explode(b)
                        consumed = True
                        break
                if consumed:
                    continue
            else:
                if not self.player.dodging and self.player.invuln_t <= 0:
                    if self.player.rect.collidepoint(b.pos):
                        self.player.take_damage(b.damage)
                        self.particles.blood(b.pos, (220, 60, 60), 6)
                        if b.aoe:
                            self.aoe_explode(b)
                        continue
            new_bullets.append(b)
        self.bullets = new_bullets

        # Enemies update (Only Host or solo player updates AI)
        if not self.network.running or self.network.is_host:
            for e in self.enemies:
                if e.alive:
                    e.update(dt, self.player, self.world, self.particles,
                             self.enemies, self.bullets, self.t, self.sounds)

        # Drop gold/medkit on death (Only Host or solo player generates drops)
        if not self.network.running or self.network.is_host:
            for e in list(self.enemies):
                if not e.alive and not getattr(e, "_dropped", False):
                    e._dropped = True
                    self.camera.add_shake(SHAKE_HIT if not e.is_boss else SHAKE_EXPLODE)
                    self.particles.blood(e.pos, count=20)
                    gold = random.randint(*e.gold_drop) if e.gold_drop[1] > 0 else 0
                    if gold > 0:
                        self.world.add_pickup(Pickup(Vec(e.pos), P_GOLD, gold))
                        self.particles.text(e.pos + Vec(0, -16),
                                            f"+{gold}", color=(255, 215, 0))
                    if random.random() < 0.18 or e.is_boss:
                        self.world.add_pickup(Pickup(Vec(e.pos + Vec(20, 10)),
                                                     P_MEDKIT))
                    if random.random() < 0.22:
                        self.world.add_pickup(Pickup(Vec(e.pos + Vec(-20, 10)),
                                                     P_AMMO))
                    # Boss death unlocks exit
                    if e.is_boss:
                        self.world.exit_locked = False
                        self.hud.set_message("CỔNG ĐÃ MỞ — đi tới cuối map!",
                                             duration=4.0)

        # Boss bar
        if self.boss_ref and self.boss_ref.alive:
            self.hud.set_boss(self.boss_ref, self.boss_ref.spec["name"])
        else:
            self.hud.clear_boss()

        # Pickups
        for p in self.world.pickups:
            if not p.alive:
                continue
            p.update(dt, self.t)
            if (Vec(p.pos) - self.player.pos).length() < 28:
                if p.kind == P_GOLD:
                    self.player.add_gold(p.amount)
                    self.particles.text(p.pos, f"+{p.amount}$",
                                        color=(255, 215, 0))
                    self.particles.pickup(p.pos)
                elif p.kind == P_MEDKIT:
                    self.player.heal(40)
                    self.particles.text(p.pos, "+40 HP",
                                        color=(80, 220, 80))
                    self.particles.pickup(p.pos, color=(100, 230, 100))
                elif p.kind == P_AMMO:
                    # add ammo to non-pistol weapons
                    for k, w in self.player.weapons.items():
                        if w.spec.get("ammo_reserve", 9999) < 9999:
                            w.ammo_reserve = min(
                                w.ammo_reserve + 30,
                                int(w.spec.get("ammo_reserve", 30) * 1.5))
                    self.particles.text(p.pos, "+AMMO",
                                        color=(255, 220, 90))
                    self.particles.pickup(p.pos, color=(255, 220, 90))
                p.alive = False

        # Camera follow
        self.camera.follow(self.player.pos, dt, lerp=8)

        # Particles
        self.particles.update(dt)

        # HUD update
        self.hud.update(dt)

        # Network Sync
        if self.network.running:
            # Check if any peer hit ME
            for p_id, data in self.network.peer_data.items():
                remote_hits = data.get("hits", [])
                for h in remote_hits:
                    target_id = h.get("target")
                    is_me = (str(target_id) == str(self.my_id)) or (self.network.is_host and str(target_id) == "host_status")
                    if is_me:
                        self.player.take_damage(h.get("dmg", 10))
                        self.particles.blood(self.player.pos, (220, 60, 60), 10)
                
                # Clear hits from data so we don't process them again on subsequent frames
                data["hits"] = []
                
                # Host processes Client's enemy hits
                if self.network.is_host:
                    enemy_hits = data.get("enemy_hits", [])
                    for eh in enemy_hits:
                        idx = eh.get("idx")
                        dmg = eh.get("dmg", 10)
                        if idx is not None and 0 <= idx < len(self.enemies):
                            e = self.enemies[idx]
                            if e.alive:
                                e.take_damage(dmg, Vec(1, 0))
                                self.particles.blood(e.pos, count=8)
                    # Clear enemy_hits from client data so we don't process twice
                    data["enemy_hits"] = []
                    
                    if data.get("client_died", False):
                        self.pvp_host_score += 1
                        data["client_died"] = False
                
                # Clear hits from data so we don't process twice (simple way)
                data["hits"] = []

            # Consolidating updates in run() loop
            pass

        # Check PvP victory conditions
        if self.pvp_enabled and not getattr(self, "pvp_winner", None):
            if self.pvp_host_score >= 10:
                self.pvp_winner = "host"
            elif self.pvp_client_score >= 10:
                self.pvp_winner = "client"

        # Death check
        if not self.player.alive:
            if self.pvp_enabled:
                if self.network.is_host:
                    self.pvp_client_score += 1
                    self._host_died_tick = True
                else:
                    self.pvp_host_score += 1
                    self._client_died_tick = True
                
                # Perform instant respawn
                self.player.alive = True
                self.player.hp = self.player.max_hp
                self.player.invuln_t = 3.0
                self.player.on_bike = False
                
                # Find random safe spawn
                ww, wh = self.world.pixel_size()
                spawn_pos = Vec(random.randint(200, ww - 200), random.randint(200, wh - 200))
                for _ in range(50):
                    collides = False
                    for s in self.world.solids:
                        if s.rect.collidepoint(spawn_pos.x, spawn_pos.y):
                            collides = True
                            break
                    if not collides:
                        break
                    spawn_pos = Vec(random.randint(200, ww - 200), random.randint(200, wh - 200))
                
                self.player.pos = spawn_pos
                self.particles.text(self.player.pos, "HỒI SINH!", color=(100, 240, 100), life=2.0)
            else:
                if not self.network.running or self.network.is_host:
                    self.scene = SCENE_GAMEOVER
                    self.gameover_t = 0
                    return

        # Update BFS dog cage radar path
        if self.world.dog_rect:
            self.dog_radar_timer += dt
            if self.dog_radar_timer >= 0.3 or not self.dog_radar_path:
                self.dog_radar_timer = 0.0
                try:
                    from pathfinding import Pathfinder
                    pf = Pathfinder(self.world, ignore_boss_gates=True)
                    start_v = pygame.Vector2(self.player.pos.x, self.player.pos.y)
                    target_v = pygame.Vector2(self.world.dog_rect.centerx, self.world.dog_rect.centery)
                    self.dog_radar_path = pf.bfs(start_v, target_v)
                except:
                    self.dog_radar_path = []
        else:
            self.dog_radar_path = []

        # Update BFS boss radar path
        if self.boss_ref and self.boss_ref.alive:
            self.boss_radar_timer += dt
            if self.boss_radar_timer >= 0.3 or not self.boss_radar_path:
                self.boss_radar_timer = 0.0
                try:
                    from pathfinding import Pathfinder
                    pf = Pathfinder(self.world, ignore_boss_gates=True)
                    start_v = pygame.Vector2(self.player.pos.x, self.player.pos.y)
                    target_v = pygame.Vector2(self.boss_ref.pos.x, self.boss_ref.pos.y)
                    self.boss_radar_path = pf.bfs(start_v, target_v)
                except:
                    self.boss_radar_path = []
        else:
            self.boss_radar_path = []

        # Only Host or solo player checks level complete / exit / victory triggers
        if not self.network.running or self.network.is_host:
            # Rescue Dog -> next level
            if self.world.dog_rect:
                if self.world.dog_rect.colliderect(self.player.rect.inflate(20, 20)):
                    if self.level_idx == len(LEVEL_BUILDERS) - 1:
                        self.scene = SCENE_VICTORY
                        self.victory_t = 0
                    else:
                        self.scene = SCENE_LEVEL_DONE
                        self.outro_t = 0
                    return

            # Boss kill check for Boss Rush maps (idx >= 7)
            if self.level_idx >= 7 and not self.pvp_enabled:
                bosses_alive = [e for e in self.enemies if e.alive and e.is_boss]
                if not bosses_alive:
                    # All bosses defeated -> Victory!
                    if self.level_idx == len(LEVEL_BUILDERS) - 1:
                        self.scene = SCENE_VICTORY
                        self.victory_t = 0
                    else:
                        self.scene = SCENE_LEVEL_DONE
                        self.outro_t = 0
                    return

            # Exit -> next level
            if not self.world.exit_locked and self.world.exit_rect:
                if self.world.exit_rect.colliderect(self.player.rect.inflate(8, 8)):
                    if self.level_idx == len(LEVEL_BUILDERS) - 1:
                        self.scene = SCENE_VICTORY
                        self.victory_t = 0
                    else:
                        self.scene = SCENE_LEVEL_DONE
                        self.outro_t = 0

    # ==================================================================
    def aoe_explode(self, b: Bullet):
        r = b.aoe or 100
        self.particles.explosion(b.pos, count=40, big=True)
        self.play_sound("sniper") # Explosion sound
        self.camera.add_shake(SHAKE_EXPLODE)
        for e in self.enemies:
            if e.alive and (Vec(e.pos) - b.pos).length() < r:
                dirv = (Vec(e.pos) - b.pos).normalize() \
                    if (Vec(e.pos) - b.pos).length() > 0.1 else Vec(1, 0)
                e.take_damage(b.damage, dirv)
                self.particles.blood(e.pos, count=8)
        # chain drums
        for s in self.world.solids:
            if s.alive and s.kind == "drum" and \
                    (Vec(s.rect.center) - b.pos).length() < r:
                s.alive = False
                self.particles.explosion(Vec(s.rect.center),
                                         color=(255, 140, 40), count=30, big=True)

    def drum_explode(self, drum):
        drum.alive = False
        self.play_sound("sniper") # Explosion sound
        self.camera.add_shake(SHAKE_EXPLODE)
        self.particles.explosion(Vec(drum.rect.center),
                                 color=(255, 140, 40), count=40, big=True)
        # damage enemies in radius
        r = 140
        for e in self.enemies:
            if e.alive and (Vec(e.pos) - Vec(drum.rect.center)).length() < r:
                dirv = (Vec(e.pos) - Vec(drum.rect.center))
                if dirv.length() > 0.1:
                    dirv = dirv.normalize()
                else:
                    dirv = Vec(1, 0)
                e.take_damage(80, dirv)
                self.particles.blood(e.pos, count=6)
        # damage player if close
        if (self.player.pos - Vec(drum.rect.center)).length() < r:
            self.player.take_damage(30)

    # ==================================================================
    def next_level(self, level_idx=None):
        if level_idx is not None: self.level_idx = level_idx
        else: self.level_idx += 1
        
        # Enable PvP if it's the arena map (index 13)
        self.pvp_enabled = (self.level_idx == 13)
        if self.pvp_enabled:
            self.pvp_host_score = 0
            self.pvp_client_score = 0
            self.pvp_winner = None
        
        if self.level_idx >= len(LEVEL_BUILDERS):
            self.scene = SCENE_VICTORY
            return
        self.load_level(self.level_idx)
        self.scene = SCENE_STORY
        self.intro_t = 0

    # ==================================================================
    def update_pvp_end(self, dt):
        # Allow them to click a button to return to Waiting Room
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Click return button
                    mx, my = pygame.mouse.get_pos()
                    my_y = SCREEN_HEIGHT // 2 - 280 // 2
                    btn_rect = pygame.Rect(SCREEN_WIDTH // 2 - 120, my_y + 190, 240, 45)
                    if btn_rect.collidepoint(mx, my):
                        if self.network.is_host:
                            # Reset pvp state
                            self.pvp_host_score = 0
                            self.pvp_client_score = 0
                            self.pvp_winner = None
                            self.scene = SCENE_WAITING_ROOM
                            
    def draw_pvp_end_overlay(self):
        # Draw blurred glassmorphic overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 15, 25, 220))
        self.screen.blit(overlay, (0, 0))
        
        # Modal box
        mw, mh = 420, 280
        mx = SCREEN_WIDTH // 2 - mw // 2
        my = SCREEN_HEIGHT // 2 - mh // 2
        
        # Outer glow border
        pygame.draw.rect(self.screen, (255, 215, 0) if self.pvp_winner == ("host" if self.network.is_host else "client") else (255, 60, 80), 
                         (mx, my, mw, mh), width=3, border_radius=16)
        # Inner dark fill
        box_surf = pygame.Surface((mw, mh), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (20, 25, 35, 240), (0, 0, mw, mh), border_radius=16)
        self.screen.blit(box_surf, (mx, my))
        
        # Title text
        is_my_victory = (self.pvp_winner == "host" and self.network.is_host) or (self.pvp_winner == "client" and not self.network.is_host)
        
        if is_my_victory:
            title_text = "BẠN ĐÃ CHIẾN THẮNG!"
            title_color = (80, 255, 120)
        else:
            title_text = "BẠN ĐÃ THẤT BẠI!"
            title_color = (255, 80, 80)
            
        draw_text(self.screen, title_text, (SCREEN_WIDTH // 2, my + 40), size=28, color=title_color, bold=True, center=True)
        
        # Scores details
        score_text = f"Tỉ số chung cuộc: {self.pvp_host_score} - {self.pvp_client_score}"
        draw_text(self.screen, score_text, (SCREEN_WIDTH // 2, my + 100), size=20, color=WHITE, center=True)
        
        # Winner text details
        winner_name = "Chủ phòng" if self.pvp_winner == "host" else "Người chơi"
        draw_text(self.screen, f"Người thắng cuộc: {winner_name}", (SCREEN_WIDTH // 2, my + 140), size=18, color=(255, 215, 0), center=True)
        
        # Action button
        btn_rect = pygame.Rect(SCREEN_WIDTH // 2 - 120, my + 190, 240, 45)
        
        if self.network.is_host:
            # Host sees exit button
            pygame.draw.rect(self.screen, (255, 215, 0), btn_rect, border_radius=8)
            draw_text(self.screen, "QUAY LẠI PHÒNG CHỜ", (btn_rect.centerx, btn_rect.centery), size=16, color=(20, 20, 20), bold=True, center=True)
        else:
            # Client sees waiting label
            pygame.draw.rect(self.screen, (40, 50, 60), btn_rect, border_radius=8)
            draw_text(self.screen, "CHỜ CHỦ PHÒNG BẮT ĐẦU LẠI...", (btn_rect.centerx, btn_rect.centery), size=14, color=WHITE, bold=True, center=True)

    def draw(self):
        if self.scene == SCENE_MENU:
            self.draw_menu()
        elif self.scene == SCENE_CHAR_SELECT:
            self.draw_char_select()
        elif self.scene == SCENE_HUB:
            if self.hub is not None:
                self.hub.draw(self.screen)
            else:
                self.screen.fill((10, 16, 14))
        elif self.scene == SCENE_INTRO:
            self.draw_play()
            self.draw_intro_overlay()
        elif self.scene in (SCENE_PLAY, SCENE_PAUSE, SCENE_MAP):
            self.draw_play()
            if self.dialog_queue:
                self.draw_dialog()
            if self.scene == SCENE_PAUSE:
                self.draw_pause_overlay()
            if self.scene == SCENE_MAP:
                self.draw_big_map()
            if self.shop and self.shop.open:
                self.shop.draw(self.screen, self.player)
            if getattr(self, "pvp_winner", None):
                self.draw_pvp_end_overlay()
        elif self.scene == SCENE_GAMEOVER:
            self.draw_play()
            self.draw_gameover_overlay()
        elif self.scene == SCENE_LEVEL_DONE:
            self.draw_play()
            self.draw_level_done_overlay()
        elif self.scene == SCENE_VICTORY:
            self.draw_play()
            self.draw_victory()
        elif self.scene == SCENE_STORY:
            self.draw_story()
        elif self.scene == SCENE_LOBBY:
            self.draw_lobby()
        elif self.scene == SCENE_LEVEL_SELECT:
            self.draw_level_select()
        elif self.scene == SCENE_SETTINGS:
            self.draw_settings()
        elif self.scene == SCENE_BOSS_RUSH_MENU:
            self.draw_boss_rush_menu()
        elif self.scene == SCENE_HOST_MODE_SELECT:
            self.draw_host_mode_select()
        elif self.scene == SCENE_WAITING_ROOM:
            self.draw_waiting_room()

    # ==================================================================
    def draw_play(self):
        self.world.draw_bg(self.screen, self.camera)
        
        # Calculate view boundary for culling (with a small margin)
        view_rect = pygame.Rect(self.camera.offset.x - 100, self.camera.offset.y - 100, 
                                SCREEN_WIDTH + 200, SCREEN_HEIGHT + 200)

        # decals and pickups under entities (already culled in draw_bg for decals)
        # cull pickups
        for p in self.world.pickups:
            if p.alive and view_rect.collidepoint(p.pos.x, p.pos.y):
                p.draw(self.screen, self.camera)

        # solids and entities sorted by y to give depth
        items = []
        for s in self.world.solids:
            if s.alive and view_rect.colliderect(s.rect):
                items.append((s.rect.bottom, "solid", s))
        for e in self.enemies:
            if e.alive and view_rect.collidepoint(e.pos.x, e.pos.y):
                items.append((e.pos.y, "enemy", e))
        
        items.append((self.player.pos.y, "player", self.player))
        if self.active_pet is not None and self.active_pet.alive:
            items.append((self.active_pet.pos.y, "pet", self.active_pet))
        
        items.sort(key=lambda x: x[0])
        for _, kind, obj in items:
            if kind == "solid":
                obj.draw(self.screen, self.camera)
            elif kind == "enemy":
                obj.draw(self.screen, self.camera, self.t, self.particles)
            elif kind == "player":
                obj.draw(self.screen, self.camera, self.t)
            elif kind == "pet":
                obj.draw(self.screen, self.camera, self.t)

        # bullets above sprites
        for b in self.bullets:
            if view_rect.collidepoint(b.pos.x, b.pos.y):
                b.draw(self.screen, self.camera)

        # particles
        # Draw Other Players (Multiplayer)
        for p_id, data in self.network.peer_data.items():
            if "pos" not in data:
                continue
            pos = Vec(data["pos"][0], data["pos"][1])
            if view_rect.collidepoint(pos.x, pos.y):
                # Maintain dummy player for peer drawing
                if p_id not in self.network_players:
                    self.network_players[p_id] = Player(pos, char_type=data.get("char_type", "grab"))
                
                p_obj = self.network_players[p_id]
                p_obj.pos = pos
                p_obj.facing = data.get("facing_dir", "down")
                p_obj.on_bike = data.get("on_bike", False)
                p_obj.char_type = data.get("char_type", "grab")
                p_obj.aim_angle = data.get("aim_angle", 0.0)
                p_obj.aim = Vec(data.get("facing", [1, 0])[0], data.get("facing", [1, 0])[1])
                
                # Sync gun key (add if not present in dummy player's arsenal)
                gun_key = data.get("gun", "pistol")
                if gun_key not in p_obj.weapons:
                    p_obj.add_weapon(gun_key)
                p_obj.current = gun_key
                
                # Force reload sync if shooting
                if data.get("is_shooting", False):
                    p_obj.weapon.shoot_anim = 0.1
                
                # Draw the actual animated player sprite!
                p_obj.draw(self.screen, self.camera, self.t)
                
                # Draw Health bar and Name tag above them
                p_scr = self.camera.apply(pos)
                p_hp = data.get("hp", 100)
                p_max = data.get("max_hp", 100)
                bw, bh = 40, 5
                bx, by = p_scr[0] - bw // 2, p_scr[1] - 35
                pygame.draw.rect(self.screen, (40, 10, 10), (bx, by, bw, bh))
                if p_max > 0:
                    fill = int(bw * (p_hp / p_max))
                    pygame.draw.rect(self.screen, (255, 50, 50), (bx, by, fill, bh))

                peer_name = "Chủ phòng" if p_id == "host_status" else f"Player {p_id}"
                draw_text(self.screen, peer_name, (int(p_scr[0]), int(p_scr[1]) - 45), size=14, color=WHITE, center=True)

        self.particles.draw(self.screen, self.camera)

        # exit
        self.world.draw_exit_marker(self.screen, self.camera, self.t)

        # dog (visible target in level 4)
        if self.world.dog_rect is not None and self.level_idx == 3:
            self.draw_dog_cage()

        # shop area hint
        if self.shop and self.world.shop_rect:
            if (Vec(self.world.shop_rect.center) - self.player.pos).length() < 90:
                rect = self.camera.apply_rect(self.world.shop_rect)
                pygame.draw.rect(self.screen, (255, 215, 0),
                                 rect.inflate(10, 10), 3)
                draw_text(self.screen, "[E] SHOP NÂNG CẤP",
                          (rect.centerx, rect.top - 16), size=18,
                          color=(255, 215, 0), bold=True, center=True)

        # Draw BFS dog radar path
        import settings
        if settings.SHOW_PATHFINDING and self.rada_enabled and hasattr(self, "dog_radar_path") and self.dog_radar_path:
            pts = [self.camera.apply(pygame.Vector2(pt)) for pt in self.dog_radar_path]
            pts.insert(0, self.camera.apply(self.player.pos))
            if len(pts) > 1:
                # Golden/Cyan radar path using glowing dots
                for idx in range(len(pts) - 1):
                    p1 = pygame.Vector2(pts[idx])
                    p2 = pygame.Vector2(pts[idx + 1])
                    dist = (p2 - p1).length()
                    step = 12
                    num_dots = max(1, int(dist // step))
                    for d in range(num_dots):
                        t_ratio = d / num_dots
                        dot_pos = p1 + (p2 - p1) * t_ratio
                        rad = int(3 + math.sin(self.t * 10 + idx) * 1)
                        # Outer glow
                        pygame.draw.circle(self.screen, (0, 200, 255, 100), (int(dot_pos.x), int(dot_pos.y)), rad + 2)
                        # Inner bright core
                        pygame.draw.circle(self.screen, (100, 255, 255), (int(dot_pos.x), int(dot_pos.y)), max(1, rad - 1))
                
                # Holographic radar target label at the end
                end_pt = pygame.Vector2(pts[-1])
                pulse = (math.sin(self.t * 8) + 1) * 0.5
                pygame.draw.circle(self.screen, (255, 215, 0), (int(end_pt.x), int(end_pt.y)), int(20 + pulse * 10), 2)
                dist_m = len(self.dog_radar_path)
                draw_text(self.screen, f"RADA BFS: {dist_m}m", (int(end_pt.x), int(end_pt.y) - 30), 
                          size=16, color=(255, 215, 0), bold=True, center=True)

        # Draw BFS boss radar path
        if settings.SHOW_PATHFINDING and self.rada_enabled and hasattr(self, "boss_radar_path") and self.boss_radar_path:
            pts = [self.camera.apply(pygame.Vector2(pt)) for pt in self.boss_radar_path]
            pts.insert(0, self.camera.apply(self.player.pos))
            if len(pts) > 1:
                # Glowing Neon Orange/Red dots for Boss radar
                for idx in range(len(pts) - 1):
                    p1 = pygame.Vector2(pts[idx])
                    p2 = pygame.Vector2(pts[idx + 1])
                    dist = (p2 - p1).length()
                    step = 12
                    num_dots = max(1, int(dist // step))
                    for d in range(num_dots):
                        t_ratio = d / num_dots
                        dot_pos = p1 + (p2 - p1) * t_ratio
                        rad = int(3 + math.sin(self.t * 10 + idx) * 1)
                        # Outer glow (Red/Orange)
                        pygame.draw.circle(self.screen, (255, 80, 0, 100), (int(dot_pos.x), int(dot_pos.y)), rad + 2)
                        # Inner core
                        pygame.draw.circle(self.screen, (255, 180, 100), (int(dot_pos.x), int(dot_pos.y)), max(1, rad - 1))
                
                # Target Hologram circle at the Boss position
                end_pt = pygame.Vector2(pts[-1])
                pulse = (math.sin(self.t * 8) + 1) * 0.5
                pygame.draw.circle(self.screen, (255, 50, 50), (int(end_pt.x), int(end_pt.y)), int(20 + pulse * 10), 2)
                dist_m = len(self.boss_radar_path)
                draw_text(self.screen, f"TRÙM: {dist_m}m", (int(end_pt.x), int(end_pt.y) - 30), 
                          size=16, color=(255, 80, 80), bold=True, center=True)

        # objective arrow
        self.draw_objective_arrow()

        # crosshair
        if self.scene == SCENE_PLAY and not (self.shop and self.shop.open):
            mx, my = pygame.mouse.get_pos()
            pygame.draw.circle(self.screen, (255, 255, 255), (mx, my), 8, 1)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (mx - 12, my), (mx - 4, my), 1)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (mx + 4, my), (mx + 12, my), 1)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (mx, my - 12), (mx, my - 4), 1)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (mx, my + 4), (mx, my + 12), 1)

        # HUD
        self.hud.draw(self.screen, self.player, self.level_name,
                      self.world, self.enemies, self.t)
                      
        if self.pvp_enabled:
            # Draw elegant scoreboard at top center
            sb_w, sb_h = 320, 50
            sb_x = SCREEN_WIDTH // 2 - sb_w // 2
            sb_y = 15
            
            # Semi-transparent dark glass backing
            sb_surf = pygame.Surface((sb_w, sb_h), pygame.SRCALPHA)
            pygame.draw.rect(sb_surf, (15, 20, 30, 200), (0, 0, sb_w, sb_h), border_radius=12)
            # Glowing neon red/blue border
            pygame.draw.rect(sb_surf, (255, 60, 80, 150), (0, 0, sb_w, sb_h), width=2, border_radius=12)
            self.screen.blit(sb_surf, (sb_x, sb_y))
            
            # Draw labels
            draw_text(self.screen, "CHỦ PHÒNG", (sb_x + 60, sb_y + 10), size=12, color=(255, 120, 120), center=True, bold=True)
            draw_text(self.screen, "NGƯỜI CHƠI", (sb_x + sb_w - 60, sb_y + 10), size=12, color=(120, 180, 255), center=True, bold=True)
            
            # Draw score numbers
            draw_text(self.screen, str(self.pvp_host_score), (sb_x + 60, sb_y + 24), size=24, color=(255, 60, 80), center=True, bold=True)
            draw_text(self.screen, ":", (sb_x + sb_w // 2, sb_y + 18), size=22, color=WHITE, center=True, bold=True)
            draw_text(self.screen, str(self.pvp_client_score), (sb_x + sb_w - 60, sb_y + 24), size=24, color=(60, 160, 255), center=True, bold=True)
            
            # Draw win target progress bar
            bar_w, bar_h = 280, 4
            bar_x = SCREEN_WIDTH // 2 - bar_w // 2
            bar_y = sb_y + sb_h - 8
            # Backing
            pygame.draw.rect(self.screen, (30, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
            # Host score fill (center to left)
            host_ratio = min(1.0, self.pvp_host_score / 10)
            host_fill = int((bar_w // 2) * host_ratio)
            pygame.draw.rect(self.screen, (255, 60, 80), (bar_x + bar_w // 2 - host_fill, bar_y, host_fill, bar_h), border_radius=2)
            # Client score fill (center to right)
            client_ratio = min(1.0, self.pvp_client_score / 10)
            client_fill = int((bar_w // 2) * client_ratio)
            pygame.draw.rect(self.screen, (60, 160, 255), (bar_x + bar_w // 2, bar_y, client_fill, bar_h), border_radius=2)

    # ==================================================================
    def draw_objective_arrow(self):
        target = None
        if self.world.exit_locked and self.boss_ref and self.boss_ref.alive:
            target = self.boss_ref.pos
        elif self.world.exit_rect and not self.world.exit_locked:
            target = Vec(self.world.exit_rect.center)
        if target is None:
            return
        sp = self.camera.apply(target)
        # if on screen, skip arrow
        if 60 < sp[0] < SCREEN_WIDTH - 60 and 90 < sp[1] < SCREEN_HEIGHT - 90:
            return
        # clamp to screen edge
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        dx, dy = sp[0] - cx, sp[1] - cy
        # find intersection with screen rect
        max_dx = SCREEN_WIDTH / 2 - 80
        max_dy = SCREEN_HEIGHT / 2 - 80
        scale = max(abs(dx) / max_dx, abs(dy) / max_dy)
        if scale == 0:
            return
        ax = cx + dx / scale
        ay = cy + dy / scale
        angle = math.atan2(dy, dx)
        col = (255, 80, 80) if self.world.exit_locked else (90, 220, 100)
        pts = []
        for a in (0, 2.5, -2.5):
            pts.append((ax + math.cos(angle + a) * 18,
                        ay + math.sin(angle + a) * 18))
        pygame.draw.polygon(self.screen, col, pts)
        pygame.draw.polygon(self.screen, (0, 0, 0), pts, 2)

    # ==================================================================
    def draw_dog_cage(self):
        r = self.camera.apply_rect(self.world.dog_rect)
        # cage frame
        pygame.draw.rect(self.screen, (90, 70, 50), r)
        pygame.draw.rect(self.screen, (40, 30, 20), r, 3)
        # bars
        for x in range(r.left + 6, r.right - 4, 8):
            pygame.draw.line(self.screen, (60, 50, 40),
                             (x, r.top), (x, r.bottom), 2)
        # dog inside (simple cute pixel dog)
        cx, cy = r.center
        bob = math.sin(self.t * 4) * 2
        pygame.draw.ellipse(self.screen, (190, 140, 90),
                            (cx - 22, cy - 8 + bob, 44, 24))
        pygame.draw.circle(self.screen, (190, 140, 90),
                           (cx + 18, cy - 6 + int(bob)), 12)
        pygame.draw.polygon(self.screen, (140, 100, 60), [
            (cx + 22, cy - 16 + int(bob)),
            (cx + 30, cy - 22 + int(bob)),
            (cx + 28, cy - 8 + int(bob)),
        ])
        pygame.draw.circle(self.screen, (0, 0, 0),
                           (cx + 22, cy - 6 + int(bob)), 1)
        # tail wag
        wag = math.sin(self.t * 8) * 6
        pygame.draw.line(self.screen, (190, 140, 90),
                         (cx - 22, cy), (cx - 30, cy - 10 + int(wag)), 4)
        # "?" while locked, "!" when freed (boss dead)
        if self.boss_ref and not self.boss_ref.alive:
            draw_text(self.screen, "FREE!", (cx, r.top - 14),
                      size=20, color=(80, 220, 80),
                      bold=True, center=True)
        else:
            draw_text(self.screen, "HELP!", (cx, r.top - 14),
                      size=20, color=(255, 180, 60),
                      bold=True, center=True)

    # ==================================================================
    def draw_menu(self):
        # Premium dark forest/neon hybrid background with dynamic animations
        self.screen.fill((10, 16, 12))
        
        # Parallax moving neon grids/lines for high-tech premium gaming look
        for i in range(15):
            y_line = int((i * 60 + self.t * 15) % SCREEN_HEIGHT)
            alpha = int(25 + 15 * math.sin(self.t + i))
            line_surf = pygame.Surface((SCREEN_WIDTH, 1), pygame.SRCALPHA)
            line_surf.fill((0, 200, 100, alpha))
            self.screen.blit(line_surf, (0, y_line))

        # Floating green/gold neon fireflies
        for i in range(45):
            x = (i * 137 + int(self.t * 22)) % SCREEN_WIDTH
            y = (i * 79 + int(self.t * 12)) % SCREEN_HEIGHT
            r = int(2 + 2 * math.sin(self.t * 1.5 + i))
            pulse = int(120 + 80 * math.sin(self.t * 3 + i))
            s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            col = (0, 255, 100) if i % 2 == 0 else (255, 215, 0)
            pygame.draw.circle(s, (*col, pulse // 4), (r * 2, r * 2), r * 2)
            pygame.draw.circle(s, (*col, pulse), (r * 2, r * 2), r)
            self.screen.blit(s, (x - r * 2, y - r * 2))

        # Main Title (GRAB HERO with dynamic glowing split style)
        title_y = 48
        # Glow shadow
        for ox, oy in [(-3, -3), (3, 3), (-3, 3), (3, -3)]:
            draw_text(self.screen, "GRAB HERO", (SCREEN_WIDTH // 2 + ox, title_y + oy), 
                      size=86, color=(8, 30, 15), bold=True, center=True)
        draw_text(self.screen, "GRAB HERO", (SCREEN_WIDTH // 2, title_y), 
                  size=86, color=GOLD, bold=True, center=True)
                  
        # Subtitle
        draw_text(self.screen, "GIẢI CỨU CHÚ CHÓ", (SCREEN_WIDTH // 2, title_y + 64), 
                  size=24, color=(180, 240, 200), bold=True, center=True)

        # Central Panel (Premium Cyberpunk Grab-themed Glassmorphism Panel)
        pw, ph = 520, 520
        px = (SCREEN_WIDTH - pw) // 2
        py = title_y + 102
        panel_rect = pygame.Rect(px, py, pw, ph)
        
        # 1. Multi-layered dynamic neon glow shadow behind the panel (soft green-gold aura)
        for layer in range(6):
            glow_rect = panel_rect.inflate(layer * 6, layer * 6)
            glow_alpha = max(0, int((12 - layer * 2) * (1.0 + 0.2 * math.sin(self.t * 5))))
            glow_surf = pygame.Surface((glow_rect.w, glow_rect.h), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (0, 200, 100, glow_alpha), (0, 0, glow_rect.w, glow_rect.h), border_radius=26 + layer)
            self.screen.blit(glow_surf, glow_rect.topleft)

        # 2. Glassmorphism Body: Rich semi-transparent dark obsidian backdrop
        body_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        body_surf.fill((8, 16, 12, 240)) # Very dark forest base
        self.screen.blit(body_surf, (px, py))
        
        # 3. Outer Premium Gold Border & Inner Cyber Grab Green Border
        pygame.draw.rect(self.screen, (0, 175, 81), panel_rect, 2, border_radius=22)
        pygame.draw.rect(self.screen, GOLD, panel_rect.inflate(6, 6), 2, border_radius=24)

        # 4. Exquisite Futuristic Sci-Fi Corner Brackets
        ca = 22
        cb_col = GOLD
        cg_col = (0, 255, 130)
        # Top-Left Bracket
        pygame.draw.line(self.screen, cb_col, (panel_rect.left - 3, panel_rect.top - 3), (panel_rect.left - 3 + ca, panel_rect.top - 3), 3)
        pygame.draw.line(self.screen, cb_col, (panel_rect.left - 3, panel_rect.top - 3), (panel_rect.left - 3, panel_rect.top - 3 + ca), 3)
        pygame.draw.line(self.screen, cg_col, (panel_rect.left + 3, panel_rect.top + 3), (panel_rect.left + 3 + ca - 4, panel_rect.top + 3), 1)
        pygame.draw.line(self.screen, cg_col, (panel_rect.left + 3, panel_rect.top + 3), (panel_rect.left + 3, panel_rect.top + 3 + ca - 4), 1)

        # Top-Right Bracket
        pygame.draw.line(self.screen, cb_col, (panel_rect.right + 3, panel_rect.top - 3), (panel_rect.right + 3 - ca, panel_rect.top - 3), 3)
        pygame.draw.line(self.screen, cb_col, (panel_rect.right + 3, panel_rect.top - 3), (panel_rect.right + 3, panel_rect.top - 3 + ca), 3)
        pygame.draw.line(self.screen, cg_col, (panel_rect.right - 3, panel_rect.top + 3), (panel_rect.right - 3 - ca + 4, panel_rect.top + 3), 1)
        pygame.draw.line(self.screen, cg_col, (panel_rect.right - 3, panel_rect.top + 3), (panel_rect.right - 3, panel_rect.top + 3 + ca - 4), 1)

        # Bottom-Left Bracket
        pygame.draw.line(self.screen, cb_col, (panel_rect.left - 3, panel_rect.bottom + 3), (panel_rect.left - 3 + ca, panel_rect.bottom + 3), 3)
        pygame.draw.line(self.screen, cb_col, (panel_rect.left - 3, panel_rect.bottom + 3), (panel_rect.left - 3, panel_rect.bottom + 3 - ca), 3)
        pygame.draw.line(self.screen, cg_col, (panel_rect.left + 3, panel_rect.bottom - 3), (panel_rect.left + 3 + ca - 4, panel_rect.bottom - 3), 1)
        pygame.draw.line(self.screen, cg_col, (panel_rect.left + 3, panel_rect.bottom - 3), (panel_rect.left + 3, panel_rect.bottom - 3 - ca + 4), 1)

        # Bottom-Right Bracket
        pygame.draw.line(self.screen, cb_col, (panel_rect.right + 3, panel_rect.bottom + 3), (panel_rect.right + 3 - ca, panel_rect.bottom + 3), 3)
        pygame.draw.line(self.screen, cb_col, (panel_rect.right + 3, panel_rect.bottom + 3), (panel_rect.right + 3, panel_rect.bottom + 3 - ca), 3)
        pygame.draw.line(self.screen, cg_col, (panel_rect.right - 3, panel_rect.bottom - 3), (panel_rect.right - 3 - ca + 4, panel_rect.bottom - 3), 1)
        pygame.draw.line(self.screen, cg_col, (panel_rect.right - 3, panel_rect.bottom - 3), (panel_rect.right - 3, panel_rect.bottom - 3 - ca + 4), 1)

        # Buttons
        options = [
            "HÀNH TRÌNH CỨU CHÓ",
            "CHƠI MẠNG (WIFI)",
            "CÀI ĐẶT CHUNG",
            "ĐẠI CHIẾN BOSS RUSH",
            "NÂNG CẤP NHÂN VẬT",
            "MUA SÚNG MỚI",
            "CỬA HÀNG THÚ CƯNG",
            "CHỌN NHÂN VẬT",
            "THOÁT GAME"
        ]
        
        btn_h = 44
        btn_w = pw - 60
        for i, opt in enumerate(options):
            if i == 7:
                cur = "GRAB" if self.char_type == "grab" else "SHOPEE"
                opt = f"CHỌN NHÂN VẬT ({cur})"
            
            bx = px + 30
            by = py + 25 + i * (btn_h + 9)
            btn_rect = pygame.Rect(bx, by, btn_w, btn_h)
            
            is_sel = (self.menu_row == i)
            
            if is_sel:
                # Glowing selection panel with multi-layered gradient golden rounded backplate
                btn_surf = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
                for layer in range(4):
                    alpha = int(220 - layer * 30)
                    pygame.draw.rect(btn_surf, (255, 200 - layer * 15, 30, alpha), (layer, layer, btn_w - layer * 2, btn_h - layer * 2), border_radius=14 - layer)
                self.screen.blit(btn_surf, (bx, by))
                
                # Outer gold highlight with heartbeat pulse
                pulse_amt = int(4 + 2 * math.sin(self.t * 8))
                pygame.draw.rect(self.screen, GOLD, btn_rect.inflate(pulse_amt, pulse_amt), 2, border_radius=14 + pulse_amt // 2)
                text_color = (15, 25, 20)
                
                # Active selection indicators on both sides
                pulse_dot = int(4 + 2 * math.sin(self.t * 10))
                pygame.draw.circle(self.screen, (0, 255, 100), (bx + 15, by + btn_h // 2), pulse_dot)
                pygame.draw.circle(self.screen, (0, 255, 100), (bx + btn_w - 15, by + btn_h // 2), pulse_dot)
            else:
                # Sleek transparent dark buttons
                pygame.draw.rect(self.screen, (12, 24, 18, 160), btn_rect, border_radius=14)
                pygame.draw.rect(self.screen, (30, 65, 45), btn_rect, 1, border_radius=14)
                text_color = (200, 235, 210)
            
            draw_text(self.screen, opt, btn_rect.center, size=20, 
                      color=text_color, bold=True, center=True)

        # Help text
        draw_text(self.screen, "↑ / ↓ : Chọn    ENTER : Xác nhận", 
                  (SCREEN_WIDTH // 2, py + ph + 35), size=18, 
                  color=(160, 200, 175), center=True)
        
        self.draw_settings_button()

    # ==================================================================
    def draw_intro_overlay(self):
        # darkening overlay with intro text typing
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        self.screen.blit(dim, (0, 0))
        title = self.level_name
        draw_text(self.screen, title, (SCREEN_WIDTH // 2, 200),
                  size=48, color=(255, 215, 0), bold=True, center=True)
        for i, line in enumerate(self.intro_lines):
            # type effect
            tt = self.intro_t - i * 1.0
            if tt < 0:
                continue
            chars = int(tt * 28)
            shown = line[:chars]
            draw_text(self.screen, shown,
                      (SCREEN_WIDTH // 2, 320 + i * 50),
                      size=24, color=(240, 240, 240), bold=True, center=True)
        draw_text(self.screen, "[ Nhấn phím bất kỳ để bỏ qua ]",
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60),
                  size=16, color=(200, 200, 200), center=True)

    # ==================================================================
    def draw_pause_overlay(self):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        self.screen.blit(dim, (0, 0))
        draw_text(self.screen, "TẠM DỪNG", (SCREEN_WIDTH // 2, 240),
                  size=64, color=(255, 215, 0), bold=True, center=True)
        draw_text(self.screen, "ESC để tiếp tục   |   Q để về menu",
                  (SCREEN_WIDTH // 2, 340), size=24,
                  color=(220, 220, 220), bold=True, center=True)

    # ==================================================================
    def draw_gameover_overlay(self):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        a = min(220, int(self.gameover_t * 200))
        dim.fill((0, 0, 0, a))
        self.screen.blit(dim, (0, 0))
        draw_text(self.screen, "BẠN ĐÃ NGÃ XUỐNG",
                  (SCREEN_WIDTH // 2, 260), size=64,
                  color=(220, 50, 50), bold=True, center=True)
        draw_text(self.screen, "Chú chó vẫn đang chờ bạn quay lại...",
                  (SCREEN_WIDTH // 2, 340), size=24,
                  color=(220, 200, 200), center=True)
        if int(self.t * 2) % 2 == 0:
            draw_text(self.screen, "ENTER để chơi lại màn này    H về Hub (Lưu vàng)",
                      (SCREEN_WIDTH // 2, 440), size=20,
                      color=(255, 255, 255), bold=True, center=True)
            draw_text(self.screen, "ESC về menu chính",
                      (SCREEN_WIDTH // 2, 480), size=18,
                      color=(200, 200, 200), center=True)

    # ==================================================================
    def draw_level_done_overlay(self):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 40, 0, 200))
        self.screen.blit(dim, (0, 0))
        draw_text(self.screen, "HOÀN THÀNH LEVEL!",
                  (SCREEN_WIDTH // 2, 220), size=58,
                  color=(90, 230, 110), bold=True, center=True)
        draw_text(self.screen, self.level_name, (SCREEN_WIDTH // 2, 290),
                  size=28, color=(255, 215, 0), bold=True, center=True)
        
        draw_text(self.screen, f"Vàng tích luỹ: {self.player.gold}",
                  (SCREEN_WIDTH // 2, 350), size=22,
                  color=(255, 230, 90), bold=True, center=True)
        draw_text(self.screen, f"HP còn: {int(self.player.hp)}/{self.player.max_hp}",
                  (SCREEN_WIDTH // 2, 380), size=22,
                  color=(255, 255, 255), center=True)
        if int(self.t * 2) % 2 == 0:
            draw_text(self.screen, "ENTER để qua Level tiếp theo",
                      (SCREEN_WIDTH // 2, 460), size=22,
                      color=(255, 255, 255), bold=True, center=True)
            if self.shop:
                draw_text(self.screen, "Nhấn 'S' để vào Shop nâng cấp",
                          (SCREEN_WIDTH // 2, 500), size=20,
                          color=(255, 215, 0), bold=True, center=True)

    # ==================================================================
    def draw_settings_button(self):
        # Top right gear/settings button icon
        btn_r = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)
        pygame.draw.rect(self.screen, (40, 30, 10), btn_r, border_radius=5)
        pygame.draw.rect(self.screen, GOLD, btn_r, 2, border_radius=5)
        cx, cy = btn_r.center
        for i in range(8):
            ang = i * (math.tau / 8) + self.t
            p1 = (cx + math.cos(ang) * 5, cy + math.sin(ang) * 5)
            p2 = (cx + math.cos(ang) * 13, cy + math.sin(ang) * 13)
            pygame.draw.line(self.screen, GOLD, p1, p2, 3)
        pygame.draw.circle(self.screen, GOLD, (cx, cy), 6, 2)

    def draw_settings(self):
        # Settings UI
        self.screen.fill((15, 22, 15))
        # animation background
        for i in range(30):
            x = (i * 150 + int(self.t * 10)) % SCREEN_WIDTH
            y = (i * 90 + int(self.t * 8)) % SCREEN_HEIGHT
            pygame.draw.circle(self.screen, (20, 35, 25), (x, y), 2)

        draw_text(self.screen, "CÀI ĐẶT CHUNG", (SCREEN_WIDTH // 2, 120), 
                  size=64, color=GOLD, bold=True, center=True)
        
        panel_w, panel_h = 600, 380
        px = (SCREEN_WIDTH - panel_w) // 2
        py = 200
        panel_rect = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(self.screen, (40, 30, 15), panel_rect, border_radius=20)
        pygame.draw.rect(self.screen, GOLD, panel_rect, 4, border_radius=20)

        sel_col = (255, 255, 255)

        # BGM Slider
        bgm_y = py + 50
        draw_text(self.screen, "ÂM NHẠC (BGM)", (px + 60, bgm_y), size=28, color=sel_col if self.settings_sel == 0 else (180, 180, 180), bold=self.settings_sel == 0)
        draw_bar(self.screen, px + 300, bgm_y, 240, 28, self.vol_bgm, fg=GOLD, bg=(20, 20, 20))
        draw_text(self.screen, f"{int(self.vol_bgm*100)}%", (px + 560, bgm_y), size=20, color=GOLD)

        # SFX Slider
        sfx_y = py + 130
        draw_text(self.screen, "HIỆU ỨNG (SFX)", (px + 60, sfx_y), size=28, color=sel_col if self.settings_sel == 1 else (180, 180, 180), bold=self.settings_sel == 1)
        draw_bar(self.screen, px + 300, sfx_y, 240, 28, self.vol_sfx, fg=GOLD, bg=(20, 20, 20))
        draw_text(self.screen, f"{int(self.vol_sfx*100)}%", (px + 560, sfx_y), size=20, color=GOLD)

        # Pathfinding Toggle
        import settings
        path_y = py + 210
        is_path_sel = (self.settings_sel == 2)
        draw_text(self.screen, "HIỆN THUẬT TOÁN", (px + 60, path_y), size=28, color=sel_col if is_path_sel else (180, 180, 180), bold=is_path_sel)
        status_txt = "[ BẬT ]" if settings.SHOW_PATHFINDING else "[ TẮT ]"
        status_col = (50, 255, 50) if settings.SHOW_PATHFINDING else (255, 50, 50)
        draw_text(self.screen, status_txt, (px + 300, path_y), size=28, color=status_col, bold=True)

        # Back Button
        back_y = py + 300
        is_back = (self.settings_sel == 3)
        btn_c = GOLD if is_back else (150, 150, 150)
        draw_text(self.screen, "LƯU & QUAY LẠI", (SCREEN_WIDTH // 2, back_y), 
                  size=32, color=btn_c, bold=True, center=True)
        if is_back:
            pygame.draw.rect(self.screen, GOLD, (SCREEN_WIDTH // 2 - 140, back_y - 25, 280, 50), 2, border_radius=10)

        draw_text(self.screen, "← / → / ENTER : Thay đổi    ↑ / ↓ : Chọn    ESC : Thoát", 
                  (SCREEN_WIDTH // 2, py + panel_h + 60), size=18, color=(160, 160, 160), center=True)

    # ==================================================================
    def draw_victory(self):
        self.screen.fill((20, 8, 30))
        # fireworks
        for i in range(20):
            t = self.victory_t + i * 0.3
            r = int(10 + (t * 200) % 180)
            cx = (i * 73 + 200) % SCREEN_WIDTH
            cy = (i * 53 + 200) % (SCREEN_HEIGHT - 200) + 100
            col = [(255, 100, 150), (100, 200, 255),
                   (250, 220, 100), (180, 240, 120)][i % 4]
            pygame.draw.circle(self.screen, col, (cx, cy), r, 2)

        draw_text(self.screen, "CHIẾN THẮNG!",
                  (SCREEN_WIDTH // 2, 180), size=88,
                  color=(255, 215, 0), bold=True, center=True)
        draw_text(self.screen, "Bạn đã giải cứu được CHÓ MẸ và đàn con!",
                  (SCREEN_WIDTH // 2, 290), size=32,
                  color=(255, 255, 255), bold=True, center=True)
        # Big happy dog
        cx, cy = SCREEN_WIDTH // 2, 440
        bob = math.sin(self.victory_t * 4) * 8
        pygame.draw.ellipse(self.screen, (200, 150, 100),
                            (cx - 60, cy - 20 + bob, 120, 70))
        pygame.draw.circle(self.screen, (200, 150, 100),
                           (cx + 50, cy - 10 + int(bob)), 36)
        pygame.draw.polygon(self.screen, (140, 100, 60), [
            (cx + 60, cy - 40 + int(bob)),
            (cx + 80, cy - 60 + int(bob)),
            (cx + 76, cy - 22 + int(bob)),
        ])
        pygame.draw.circle(self.screen, (0, 0, 0),
                           (cx + 60, cy - 10 + int(bob)), 4)
        pygame.draw.circle(self.screen, (255, 255, 255),
                           (cx + 62, cy - 12 + int(bob)), 2)
        wag = math.sin(self.victory_t * 10) * 14
        pygame.draw.line(self.screen, (200, 150, 100),
                         (cx - 60, cy + bob),
                         (cx - 80, cy - 18 + int(wag)), 8)

        draw_text(self.screen, f"Vàng cuối: {self.player.gold} $",
                  (SCREEN_WIDTH // 2, 570), size=26,
                  color=(255, 220, 90), bold=True, center=True)
        if int(self.t * 2) % 2 == 0:
            draw_text(self.screen, "ENTER để về menu",
                      (SCREEN_WIDTH // 2, 640), size=22,
                      color=(255, 255, 255), bold=True, center=True)

    # ==================================================================
    def draw_big_map(self):
        # full screen minimap
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        self.screen.blit(dim, (0, 0))
        ww, wh = self.world.pixel_size()
        size_w = SCREEN_WIDTH - 160
        size_h = SCREEN_HEIGHT - 160
        sx = size_w / ww
        sy = size_h / wh
        s = pygame.Surface((size_w, size_h)).convert()
        s.fill((30, 30, 40))
        # tiles
        from world import (T_ROAD_H, T_ROAD_V, T_ROAD_X,
                           T_CONCRETE, T_DIRT, T_ASH, T_GRASS_DARK,
                           T_FLOOR_TILE)
        for j in range(self.world.h):
            for i in range(self.world.w):
                t = self.world.tiles[j][i]
                col = None
                if t in (T_ROAD_H, T_ROAD_V, T_ROAD_X):
                    col = (95, 95, 100)
                elif t == T_CONCRETE:
                    col = (140, 140, 140)
                elif t == T_DIRT:
                    col = (120, 90, 60)
                elif t == T_ASH:
                    col = (60, 60, 65)
                elif t == T_GRASS_DARK:
                    col = (50, 90, 50)
                elif t == T_FLOOR_TILE:
                    col = (200, 200, 210)
                if col:
                    pygame.draw.rect(s, col,
                                     (int(i * self.world.tile_size * sx),
                                      int(j * self.world.tile_size * sy),
                                      max(2, int(self.world.tile_size * sx)),
                                      max(2, int(self.world.tile_size * sy))))
        # solids
        for sol in self.world.solids:
            if not sol.alive:
                continue
            if sol.kind in ("house", "wall", "container", "machine", "rubble"):
                r = sol.rect
                pygame.draw.rect(s, (180, 140, 90),
                                 (int(r.left * sx), int(r.top * sy),
                                  max(2, int(r.w * sx)),
                                  max(2, int(r.h * sy))))
        # enemies
        for e in self.enemies:
            if not e.alive:
                continue
            col = (255, 80, 80) if not e.is_boss else (255, 30, 180)
            r = 5 if e.is_boss else 3
            pygame.draw.circle(s, col,
                               (int(e.pos.x * sx),
                                int(e.pos.y * sy)), r)
        # exit
        if self.world.exit_rect:
            r = self.world.exit_rect
            col = (220, 220, 220) if self.world.exit_locked else (60, 220, 100)
            pygame.draw.rect(s, col,
                             (int(r.left * sx), int(r.top * sy),
                              max(3, int(r.w * sx)),
                              max(3, int(r.h * sy))), 2)
        # player
        pygame.draw.circle(s, (90, 220, 90),
                           (int(self.player.pos.x * sx),
                            int(self.player.pos.y * sy)), 6)
        self.screen.blit(s, (80, 80))
        pygame.draw.rect(self.screen, (255, 215, 0),
                         (80, 80, size_w, size_h), 4)
        draw_text(self.screen, f"BẢN ĐỒ — {self.level_name}",
                  (SCREEN_WIDTH // 2, 50), size=28,
                  color=(255, 215, 0), bold=True, center=True)
        if int(self.t * 2) % 2 == 0:
            draw_text(self.screen, "TAB / ESC để đóng",
                      (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40),
                      size=18, color=(220, 220, 220), bold=True, center=True)

    # ==================================================================
    def draw_level_select(self):
        # Cosmic background
        self.screen.fill((10, 5, 25))
        # Stars
        for i in range(100):
            x = (i * 137 + int(self.t * 10)) % SCREEN_WIDTH
            y = (i * 91) % SCREEN_HEIGHT
            pygame.draw.circle(self.screen, (200, 200, 255), (x, y), 1)

        draw_text(self.screen, "CHỌN MÀN CHƠI", (SCREEN_WIDTH // 2, 60), 
                  size=48, color=GOLD, bold=True, center=True)

        # Islands / Nodes
        # Positions in a zigzag or arc
        island_pos = [
            (150, 450), (300, 320), (500, 480), (700, 350), 
            (900, 450), (1050, 300), (1150, 500)
        ]
        
        # Draw path
        for i in range(len(island_pos) - 1):
            pygame.draw.line(self.screen, (60, 60, 100), island_pos[i], island_pos[i+1], 3)

        for i, pos in enumerate(island_pos):
            is_sel = (self.sel_level_idx == i)
            # Floating effect
            bob = math.sin(self.t * 3 + i) * 10
            draw_pos = (pos[0], pos[1] + int(bob))
            
            # Rock/Island
            rect = pygame.Rect(0, 0, 100, 60)
            rect.center = draw_pos
            pygame.draw.ellipse(self.screen, (60, 40, 80), rect) # Dark purple rock
            pygame.draw.ellipse(self.screen, (30, 20, 40), rect, 4)
            
            # Highlight selected
            if is_sel:
                pygame.draw.ellipse(self.screen, GOLD, rect.inflate(15, 15), 3)
                # Glow effect
                glow_r = int(70 + math.sin(self.t * 6) * 10)
                s = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 215, 0, 60), (glow_r, glow_r), glow_r)
                self.screen.blit(s, (draw_pos[0] - glow_r, draw_pos[1] - glow_r))

            # Level circle/number
            pygame.draw.circle(self.screen, (255, 150, 50), (draw_pos[0], draw_pos[1] - 40), 25)
            pygame.draw.circle(self.screen, (200, 100, 0), (draw_pos[0], draw_pos[1] - 40), 25, 3)
            draw_text(self.screen, str(i + 1), (draw_pos[0], draw_pos[1] - 40), 
                      size=24, color=WHITE, bold=True, center=True)
            
            # Stars (Dummy for now, but ready for save data)
            star_y = draw_pos[1] - 80
            for dx in (-25, 0, 25):
                star_col = GOLD if i < self.save.get("best_level", 0) else (60, 60, 60)
                pygame.draw.polygon(self.screen, star_col, [
                    (draw_pos[0] + dx, star_y - 8),
                    (draw_pos[0] + dx + 5, star_y + 4),
                    (draw_pos[0] + dx - 5, star_y + 4),
                ])

        draw_text(self.screen, "Dùng phím Mũi tên để chọn    ENTER để chơi", 
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60), size=20, color=GRAY, center=True)
        draw_text(self.screen, "ESC quay lại Menu", (30, 30), size=16, color=GRAY)

    # ==================================================================
    def draw_story(self):
        """Draw the storyline screen between levels."""
        self.screen.fill((10, 14, 12))
        # Draw background gradient
        for y in range(0, SCREEN_HEIGHT, 10):
            t = y / SCREEN_HEIGHT
            col = (int(10 + t * 20), int(14 + t * 20), int(12 + t * 25))
            pygame.draw.rect(self.screen, col, (0, y, SCREEN_WIDTH, 10))

        # Get current story based on level_idx
        idx = min(self.level_idx, len(STORYLINE) - 1)
        story = STORYLINE[idx]
        draw_text(self.screen, story["title"], (SCREEN_WIDTH // 2, 120),
                  size=48, color=(255, 215, 0), bold=True, center=True)
        
        y = 260
        for line in story["text"]:
            draw_text(self.screen, line, (SCREEN_WIDTH // 2, y),
                      size=28, color=(240, 240, 240), center=True)
            y += 60

        if int(self.t * 2) % 2 == 0:
            draw_text(self.screen, "Nhấn SPACE hoặc ENTER để bắt đầu!",
                      (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120),
                      size=22, color=(255, 255, 255), bold=True, center=True)

    def draw_lobby(self):
        # Cyberpunk dark lobby background with neon grid and floating nodes
        self.screen.fill((8, 6, 20))
        
        # Grid lines
        grid_color = (15, 12, 45)
        grid_spacing = 60
        offset_x = int(self.t * 15) % grid_spacing
        offset_y = int(self.t * 8) % grid_spacing
        for x in range(-grid_spacing + offset_x, SCREEN_WIDTH + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(-grid_spacing + offset_y, SCREEN_HEIGHT + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (0, y), (SCREEN_WIDTH, y), 1)

        # Title
        draw_text(self.screen, "CHẾ ĐỘ MULTIPLAYER", (SCREEN_WIDTH // 2, 70), size=54, color=GOLD, bold=True, center=True)

        # Tự động lấy IP của phòng tìm thấy đầu tiên nếu chưa gõ gì
        if self.network.discovered_rooms and not self.lobby_ip:
            self.lobby_ip = list(self.network.discovered_rooms.keys())[0]

        # ----------------------------------------------------
        # TOP PANEL: PHÒNG PHÁT HIỆN TỰ ĐỘNG (ROOM DISCOVERY) / ĐANG KẾT NỐI
        # ----------------------------------------------------
        panel_w, panel_h = 600, 110
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = 135
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        
        # Draw top panel background
        pygame.draw.rect(self.screen, (12, 10, 32), panel_rect, border_radius=12)
        
        rooms = list(self.network.discovered_rooms.items())
        if rooms:
            # Active host found!
            pygame.draw.rect(self.screen, (0, 200, 100), panel_rect, 2, border_radius=12)
            # Corner glowing lights
            pygame.draw.circle(self.screen, (0, 255, 130), (panel_x + 15, panel_y + 15), 6)
            
            draw_text(self.screen, "🟢 PHÁT HIỆN PHÒNG ONLINE CỦA BẠN BÈ! TỰ ĐỘNG ĐIỀN IP:", 
                      (panel_x + 35, panel_y + 18), size=14, color=(100, 255, 180), bold=True)
            
            ip, info = rooms[0]
            draw_text(self.screen, f"IP PHÒNG:  {ip}  |  Bản đồ: {info['level']}", 
                      (SCREEN_WIDTH // 2, panel_y + 50), size=24, color=GOLD, bold=True, center=True)
            draw_text(self.screen, "Bấm ENTER ở ô 'Vào phòng' bên dưới để kết nối ngay lập tức!", 
                      (SCREEN_WIDTH // 2, panel_y + 84), size=13, color=(160, 200, 180), center=True)
        else:
            # Check if there was a connection error
            if getattr(self, 'lobby_connect_err', ""):
                pygame.draw.rect(self.screen, (100, 30, 40), panel_rect, 2, border_radius=12)
                pygame.draw.circle(self.screen, (255, 60, 80), (panel_x + 20, panel_y + 22), 6)
                draw_text(self.screen, "❌ LỖI KẾT NỐI ĐẾN PHÒNG BẠN BÈ:", 
                          (panel_x + 35, panel_y + 18), size=14, color=(255, 100, 120), bold=True)
                draw_text(self.screen, self.lobby_connect_err, 
                          (SCREEN_WIDTH // 2, panel_y + 54), size=18, color=(255, 150, 160), bold=True, center=True)
                draw_text(self.screen, "Hãy kiểm tra lại Radmin VPN hoặc chắc chắn IP chính xác!", 
                          (SCREEN_WIDTH // 2, panel_y + 84), size=12, color=(200, 150, 150), center=True)
            else:
                # No host found yet -> "Đang kết nối..." as requested!
                pygame.draw.rect(self.screen, (40, 30, 80), panel_rect, 2, border_radius=12)
                
                # Pulsating "Đang kết nối..." or "Đang quét..." dot
                pulse_alpha = int(120 + 100 * math.sin(self.t * 6))
                pygame.draw.circle(self.screen, (0, 180, 255), (panel_x + 20, panel_y + 22), 6)
                
                draw_text(self.screen, "🔍 ĐANG QUÉT TÌM PHÒNG TRONG MẠNG...", 
                          (panel_x + 35, panel_y + 18), size=14, color=(0, 200, 255), bold=True)
                
                draw_text(self.screen, "ĐANG KẾT NỐI...", 
                          (SCREEN_WIDTH // 2, panel_y + 54), size=28, color=(140, 150, 180), bold=True, center=True)
                
                draw_text(self.screen, "Hãy bảo bạn của bạn bấm 'Làm chủ phòng' để bắt đầu phát tín hiệu!", 
                          (SCREEN_WIDTH // 2, panel_y + 84), size=12, color=(120, 120, 150), center=True)

        # ----------------------------------------------------
        # MENU OPTIONS (HOST, CONNECT, BACK) BELOW THE DISCOVERY PANEL
        # ----------------------------------------------------
        options = ["LÀM CHỦ PHÒNG (HOST)", "VÀO PHÒNG (CONNECT LOCAL)", "QUAY LẠI"]
        bw, bh = 540, 56
        start_y = 265
        for i, opt in enumerate(options):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - bw // 2, start_y + i * (bh + 14), bw, bh)
            is_sel = (self.lobby_sel == i)
            
            # Styling options
            if is_sel:
                pygame.draw.rect(self.screen, (30, 80, 50), rect, border_radius=10)
                pulse_amt = int(4 + 2 * math.sin(self.t * 8))
                pygame.draw.rect(self.screen, GOLD, rect.inflate(pulse_amt, pulse_amt), 2, border_radius=10 + pulse_amt // 2)
                text_color = GOLD
                
                # Selection bullet indicators
                pygame.draw.circle(self.screen, GOLD, (rect.left + 22, rect.centery), 4)
                pygame.draw.circle(self.screen, GOLD, (rect.right - 22, rect.centery), 4)
            else:
                pygame.draw.rect(self.screen, (15, 20, 35, 200), rect, border_radius=10)
                pygame.draw.rect(self.screen, (50, 60, 90), rect, 1, border_radius=10)
                text_color = (200, 220, 240)

            # Fill selected option background
            if is_sel:
                pygame.draw.rect(self.screen, GOLD, rect, border_radius=10)
                text_color = (15, 25, 20)

            draw_text(self.screen, opt, rect.center, size=22, color=text_color, bold=True, center=True)

        # IP Input Display below VÀO PHÒNG button
        if self.lobby_ip:
            display_text = f"NHẬP IP: {self.lobby_ip}"
            text_color = GOLD if self.lobby_sel == 1 else WHITE
        else:
            display_text = "NHẬP IP: (Gõ IP máy Host...)" if self.lobby_sel == 1 else "NHẬP IP: (Trống)"
            text_color = (130, 130, 140) if self.lobby_sel != 1 else GOLD
            
        draw_text(self.screen, display_text, (SCREEN_WIDTH // 2, start_y + 1 * (bh + 14) + 38), 
                  size=18, color=text_color, center=True)
                  
        if self.lobby_sel == 1 and int(self.t * 2) % 2 == 0:
            # Cursor blink
            tw = len(display_text) * 9
            pygame.draw.line(self.screen, GOLD, (SCREEN_WIDTH // 2 + tw // 2 + 5, start_y + 1 * (bh + 14) + 28), 
                             (SCREEN_WIDTH // 2 + tw // 2 + 5, start_y + 1 * (bh + 14) + 48), 2)

        # IP display (Local IP)
        import socket
        try:
            my_ip = socket.gethostbyname(socket.gethostname())
        except: my_ip = "unknown"
        draw_text(self.screen, f"IP của bạn: {my_ip}", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90), size=16, color=GRAY, center=True)
        draw_text(self.screen, "Dùng phím số để nhập IP - BACKSPACE để xóa - ENTER để vào phòng", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 55), size=14, color=(140, 140, 140), center=True)
        
        # List peers
        y = 520
        for p_id in self.network.peer_data:
            draw_text(self.screen, f"Đã kết nối: Player {p_id}", (SCREEN_WIDTH // 2, y), size=16, color=GREEN, center=True)
            y += 25

        # Connecting loading overlay
        if getattr(self, 'lobby_connecting', False):
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200)) # Dark transparent dim
            self.screen.blit(overlay, (0, 0))
            
            # Glowing dialog box in the center
            dw, dh = 480, 180
            dx = SCREEN_WIDTH // 2 - dw // 2
            dy = SCREEN_HEIGHT // 2 - dh // 2
            pygame.draw.rect(self.screen, (15, 12, 35), (dx, dy, dw, dh), border_radius=14)
            pygame.draw.rect(self.screen, (0, 180, 255), (dx, dy, dw, dh), 3, border_radius=14)
            
            # Spinning loader indicator
            spinner_angle = self.t * 6
            spinner_r = 25
            scx, scy = SCREEN_WIDTH // 2, dy + 50
            for i in range(8):
                angle = spinner_angle + i * (math.tau / 8)
                lx = int(scx + spinner_r * math.cos(angle))
                ly = int(scy + spinner_r * math.sin(angle))
                pygame.draw.circle(self.screen, (0, 200, 255), (lx, ly), 4)
                
            draw_text(self.screen, "ĐANG KẾT NỐI ĐẾN PHÒNG...", (SCREEN_WIDTH // 2, dy + 105), 
                      size=18, color=GOLD, bold=True, center=True)
            draw_text(self.screen, "Vui lòng chờ giây lát...", (SCREEN_WIDTH // 2, dy + 135), 
                      size=14, color=(160, 180, 200), center=True)


    def draw_waiting_room(self):
        """Cyberpunk-style waiting room: neon grid, vertical player cards, side panels."""
        # === BACKGROUND: dark purple-black + neon grid ===
        self.screen.fill((8, 6, 20))
        # Animated neon grid lines
        grid_color = (30, 20, 80)
        grid_spacing = 60
        offset_x = int(self.t * 20) % grid_spacing
        offset_y = int(self.t * 10) % grid_spacing
        for x in range(-grid_spacing + offset_x, SCREEN_WIDTH + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(-grid_spacing + offset_y, SCREEN_HEIGHT + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (0, y), (SCREEN_WIDTH, y), 1)

        # Floating neon orbs
        for i in range(12):
            ox = int(SCREEN_WIDTH * 0.5 + math.sin(self.t * 0.7 + i * 1.1) * 300)
            oy = int(SCREEN_HEIGHT * 0.5 + math.cos(self.t * 0.5 + i * 0.9) * 200)
            alpha = int(30 + 20 * math.sin(self.t * 2 + i))
            orb_s = pygame.Surface((40, 40), pygame.SRCALPHA)
            orb_col = [(180, 0, 255), (0, 200, 255), (255, 0, 150)][i % 3]
            pygame.draw.circle(orb_s, (*orb_col, alpha), (20, 20), 20)
            self.screen.blit(orb_s, (ox - 20, oy - 20))

        # === MODE & IP INFO ===
        mode_map = {"journey": "HANH TRINH CUU CHO", "boss_rush": "DAI CHIEN BOSS RUSH", "pvp": "DAU TRUONG PvP"}
        mode = getattr(self, '_waiting_room_mode', 'journey')
        mode_name = mode_map.get(mode, "??")
        mode_colors = {"journey": (80, 255, 180), "boss_rush": (255, 120, 30), "pvp": (255, 60, 80)}
        mode_color = mode_colors.get(mode, (200, 200, 200))

        import socket as _sock
        try: my_ip = _sock.gethostbyname(_sock.gethostname())
        except: my_ip = "unknown"

        # === TITLE (neon glow) ===
        glow_t = math.sin(self.t * 3)
        glow_r = int(200 + 55 * glow_t)
        glow_g = int(80 + 40 * math.sin(self.t * 2))
        title_col = (glow_r, glow_g, 255)
        # Glow shadow
        for offset in [(2,2),(3,3)]:
            draw_text(self.screen, "SANH CHO ONLINE",
                      (SCREEN_WIDTH//2 + offset[0], 46 + offset[1]),
                      size=54, color=(50, 0, 120), bold=True, center=True)
        draw_text(self.screen, "SANH CHO ONLINE",
                  (SCREEN_WIDTH//2, 46), size=54, color=title_col, bold=True, center=True)

        # Mode badge below title
        badge_w = 340
        badge_rect = pygame.Rect(SCREEN_WIDTH//2 - badge_w//2, 100, badge_w, 30)
        pygame.draw.rect(self.screen, (20, 10, 50), badge_rect, border_radius=6)
        pygame.draw.rect(self.screen, mode_color, badge_rect, 2, border_radius=6)
        draw_text(self.screen, "CHE DO: " + mode_name, badge_rect.center,
                  size=15, color=mode_color, bold=True, center=True)

        # === LEFT SIDE PANEL: SERVER INFO ===
        lp_rect = pygame.Rect(30, 140, 220, 380)
        pygame.draw.rect(self.screen, (10, 8, 30), lp_rect, border_radius=12)
        pygame.draw.rect(self.screen, (80, 0, 200), lp_rect, 2, border_radius=12)
        # Corner accents
        acc = 16
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.left, lp_rect.top), (lp_rect.left+acc, lp_rect.top), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.left, lp_rect.top), (lp_rect.left, lp_rect.top+acc), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.right, lp_rect.bottom), (lp_rect.right-acc, lp_rect.bottom), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.right, lp_rect.bottom), (lp_rect.right, lp_rect.bottom-acc), 3)

        draw_text(self.screen, "SERVER INFO", (lp_rect.centerx, lp_rect.top+20),
                  size=16, color=(180, 0, 255), bold=True, center=True)
        pygame.draw.line(self.screen, (80, 0, 150), (lp_rect.left+10, lp_rect.top+38), (lp_rect.right-10, lp_rect.top+38), 1)

        # Resolve players list
        players = []
        if self.network.running:
            if self.network.is_host:
                players.append(self.my_id)
                for client_data in list(self.network.peer_data.values()):
                    c_id = client_data.get("id")
                    if c_id and c_id != "host_status":
                        c_id_str = str(c_id)
                        if c_id_str not in [str(x) for x in players]:
                            players.append(c_id)
            else:
                host_status = self.network.peer_data.get("host_status")
                if host_status:
                    players = host_status.get("players", [])
                else:
                    players = [self.my_id] # Fallback
        else:
            players = [self.my_id]
        
        total = len(players)
        info_items = [
            ("IP", my_ip),
            ("CONG", "5555"),
            ("NGUOI CHOI", str(total) + "/4"),
            ("TRANG THAI", "ONLINE" if self.network.running else "OFFLINE"),
        ]
        for ii, (label, val) in enumerate(info_items):
            iy = lp_rect.top + 58 + ii * 55
            draw_text(self.screen, label, (lp_rect.left+14, iy), size=11, color=(130, 100, 200))
            val_col = (100, 255, 100) if label in ("TRANG THAI", "NGUOI CHOI") else (220, 220, 255)
            if label == "NGUOI CHOI" and total >= 2: val_col = (100, 255, 100)
            elif label == "NGUOI CHOI": val_col = GOLD
            draw_text(self.screen, val, (lp_rect.left+14, iy+18), size=15, color=val_col, bold=True)
            pygame.draw.line(self.screen, (40, 30, 80),
                             (lp_rect.left+10, iy+38), (lp_rect.right-10, iy+38), 1)

        # Scan indicator
        pulse_r = int(6 + 3 * math.sin(self.t * 6))
        scan_col = (100, 255, 100) if self.network.running else (200, 60, 60)
        pygame.draw.circle(self.screen, scan_col, (lp_rect.left+20, lp_rect.bottom-22), pulse_r)
        draw_text(self.screen, "PHAT HIEU BEACON...",
                  (lp_rect.left+34, lp_rect.bottom-22), size=11, color=scan_col)

        # === RIGHT SIDE PANEL: TIPS ===
        rp_rect = pygame.Rect(SCREEN_WIDTH - 250, 140, 220, 380)
        pygame.draw.rect(self.screen, (10, 20, 10), rp_rect, border_radius=12)
        pygame.draw.rect(self.screen, (0, 180, 100), rp_rect, 2, border_radius=12)
        acc2 = 16
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.left, rp_rect.top), (rp_rect.left+acc2, rp_rect.top), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.left, rp_rect.top), (rp_rect.left, rp_rect.top+acc2), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.right, rp_rect.bottom), (rp_rect.right-acc2, rp_rect.bottom), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.right, rp_rect.bottom), (rp_rect.right, rp_rect.bottom-acc2), 3)

        draw_text(self.screen, "HUONG DAN", (rp_rect.centerx, rp_rect.top+20),
                  size=16, color=(0, 220, 120), bold=True, center=True)
        pygame.draw.line(self.screen, (0, 100, 60), (rp_rect.left+10, rp_rect.top+38), (rp_rect.right-10, rp_rect.top+38), 1)
        tips = [
            "1. Ban be tai game",
            "   GrabHero.exe",
            "2. Bat Radmin VPN",
            "3. Tham gia cung",
            "   mang Radmin",
            "4. Vao Multiplayer",
            "5. Chon Ket Noi",
            "6. Phat hien phong",
            "   tu dong!",
            "",
            "ENTER: Bat dau",
            "ESC:   Huy phong",
        ]
        for ti, tip in enumerate(tips):
            tc = (0, 200, 120) if tip.startswith(("ENTER", "ESC")) else (160, 220, 180)
            draw_text(self.screen, tip, (rp_rect.left+12, rp_rect.top+50+ti*24), size=12, color=tc)

        # === CENTER: 4 PLAYER CARDS (vertical 2x2 compact) ===
        cw, ch_h = 320, 140
        cgx, cgy = 20, 16
        cx_base = SCREEN_WIDTH//2 - cw - cgx//2
        cy_base = 140
        positions = [
            (cx_base, cy_base),
            (cx_base + cw + cgx, cy_base),
            (cx_base, cy_base + ch_h + cgy),
            (cx_base + cw + cgx, cy_base + ch_h + cgy),
        ]

        for idx, (sx, sy) in enumerate(positions):
            rect = pygame.Rect(sx, sy, cw, ch_h)
            is_host = (idx == 0)
            is_occ  = (idx < len(players))

            # Card background gradient effect
            if is_host:
                card_bg = (18, 14, 45)
                card_border = (200, 160, 0)
                card_accent = GOLD
            elif is_occ:
                card_bg = (10, 28, 18)
                card_border = (0, 200, 100)
                card_accent = (0, 255, 130)
            else:
                card_bg = (12, 12, 22)
                card_border = (40, 35, 80)
                card_accent = (60, 55, 110)

            # Shadow
            shadow = rect.move(5, 5)
            s_surf = pygame.Surface((shadow.w, shadow.h), pygame.SRCALPHA)
            s_surf.fill((0, 0, 0, 80))
            self.screen.blit(s_surf, shadow.topleft)

            pygame.draw.rect(self.screen, card_bg, rect, border_radius=10)
            pygame.draw.rect(self.screen, card_border, rect, 2, border_radius=10)

            # Corner line accents
            ca = 12
            pygame.draw.line(self.screen, card_accent, rect.topleft, (rect.left+ca, rect.top), 2)
            pygame.draw.line(self.screen, card_accent, rect.topleft, (rect.left, rect.top+ca), 2)
            pygame.draw.line(self.screen, card_accent, rect.bottomright, (rect.right-ca, rect.bottom), 2)
            pygame.draw.line(self.screen, card_accent, rect.bottomright, (rect.right, rect.bottom-ca), 2)

            # Slot number tag
            tag_rect = pygame.Rect(rect.left+8, rect.top+8, 56, 18)
            pygame.draw.rect(self.screen, card_border, tag_rect, border_radius=4)
            draw_text(self.screen, "SLOT " + str(idx+1), tag_rect.center, size=10,
                      color=(8,6,20), bold=True, center=True)

            if is_host:
                # HOST badge
                host_tag = pygame.Rect(rect.right-72, rect.top+8, 64, 18)
                pygame.draw.rect(self.screen, GOLD, host_tag, border_radius=4)
                draw_text(self.screen, "HOST", host_tag.center, size=10,
                          color=(20,15,5), bold=True, center=True)
                # Avatar hex shape (simulate with polygon)
                av_cx, av_cy = rect.left + 52, rect.centery + 4
                av_r = 26
                hex_pts = [(int(av_cx + av_r * math.cos(math.radians(a))),
                            int(av_cy + av_r * math.sin(math.radians(a)))) for a in range(0,360,60)]
                pygame.draw.polygon(self.screen, (50, 40, 10), hex_pts)
                pygame.draw.polygon(self.screen, GOLD, hex_pts, 2)
                draw_text(self.screen, "H", (av_cx, av_cy), size=22, color=GOLD, bold=True, center=True)
                # Info
                host_name = "Bạn (Host)" if self.network.is_host else "Chủ phòng"
                draw_text(self.screen, host_name, (rect.left+94, rect.top+36), size=17, color=WHITE, bold=True)
                draw_text(self.screen, mode_name[:16], (rect.left+94, rect.top+58), size=11, color=(200,160,60))
                # Status bar
                bar_rect2 = pygame.Rect(rect.left+8, rect.bottom-24, rect.width-16, 14)
                pygame.draw.rect(self.screen, (40,35,10), bar_rect2, border_radius=4)
                pygame.draw.rect(self.screen, GOLD, bar_rect2, border_radius=4)
                draw_text(self.screen, "READY - DA VAO PHONG", bar_rect2.center, size=9, color=(20,15,5), bold=True, center=True)

            elif is_occ:
                p_id = players[idx]
                # Avatar
                av_cx2, av_cy2 = rect.left + 52, rect.centery + 4
                hex_pts2 = [(int(av_cx2 + 26 * math.cos(math.radians(a))),
                             int(av_cy2 + 26 * math.sin(math.radians(a)))) for a in range(0,360,60)]
                pygame.draw.polygon(self.screen, (5, 30, 18), hex_pts2)
                pygame.draw.polygon(self.screen, (0, 200, 100), hex_pts2, 2)
                draw_text(self.screen, str(idx+1), (av_cx2, av_cy2), size=22, color=(0,255,130), bold=True, center=True)
                peer_label = f"Player {p_id}"
                if str(p_id) == str(self.my_id):
                    peer_label = "Bạn (Đã vào)"
                draw_text(self.screen, peer_label, (rect.left+94, rect.top+36), size=17, color=WHITE, bold=True)
                draw_text(self.screen, "DA KET NOI", (rect.left+94, rect.top+58), size=11, color=(0,220,120))
                bar_rect3 = pygame.Rect(rect.left+8, rect.bottom-24, rect.width-16, 14)
                pygame.draw.rect(self.screen, (5,35,18), bar_rect3, border_radius=4)
                pygame.draw.rect(self.screen, (0,200,100), bar_rect3, border_radius=4)
                draw_text(self.screen, "READY", bar_rect3.center, size=9, color=(5,20,10), bold=True, center=True)

            else:
                # Empty slot - animated scan line
                scan_y2 = rect.top + int((self.t * 50 + idx * 40) % rect.height)
                scan_surf = pygame.Surface((rect.width, 3), pygame.SRCALPHA)
                scan_surf.fill((80, 60, 180, 60))
                self.screen.blit(scan_surf, (rect.left, scan_y2))
                draw_text(self.screen, "--- TRONG ---", (rect.centerx, rect.centery-14),
                          size=18, color=(50,45,90), bold=True, center=True)
                draw_text(self.screen, "Cho nguoi choi...",
                          (rect.centerx, rect.centery+12), size=12, color=(40,38,72), center=True)

        # === BOTTOM: counter + buttons ===
        cy_btm = cy_base + 2*ch_h + 2*cgy + 10
        count_col2 = (100, 255, 100) if total >= 2 else GOLD
        count_str = str(total) + "/4 nguoi choi tham gia"
        draw_text(self.screen, count_str, (SCREEN_WIDTH//2, cy_btm),
                  size=20, color=count_col2, bold=True, center=True)

        ready_msg = ">> NHAN ENTER DE BAT DAU! <<" if total >= 2 else "Can them " + str(2-total) + " nguoi choi nua..."
        ready_col = (0, 255, 130) if total >= 2 else (160, 140, 60)
        draw_text(self.screen, ready_msg, (SCREEN_WIDTH//2, cy_btm+26), size=14, color=ready_col, center=True)

        # HUY PHONG button
        btn_y2 = cy_btm + 58
        cr2 = pygame.Rect(SCREEN_WIDTH//2 - 280, btn_y2, 210, 52)
        pygame.draw.rect(self.screen, (0,0,0), cr2.move(4,4), border_radius=10)
        for layer, (col, inset) in enumerate([((120,30,60),0),((200,50,90),2)]):
            pygame.draw.rect(self.screen, col, cr2.inflate(-inset*2,-inset*2), border_radius=10)
        pygame.draw.rect(self.screen, (255,80,130), cr2, 2, border_radius=10)
        draw_text(self.screen, "[ ESC ] HUY PHONG", cr2.center, size=18, color=WHITE, bold=True, center=True)

        # BAT DAU button (glowing)
        pulse_v = math.sin(self.t * 5)
        sr2 = pygame.Rect(SCREEN_WIDTH//2 + 70, btn_y2, 210, 52)
        pygame.draw.rect(self.screen, (0,0,0), sr2.move(4,4), border_radius=10)
        btn_g = int(180 + 50*pulse_v)
        pygame.draw.rect(self.screen, (0, int(100+40*pulse_v), 40), sr2, border_radius=10)
        pygame.draw.rect(self.screen, (0, btn_g, 80), sr2, 3, border_radius=10)
        # Glow effect
        glow_surf = pygame.Surface((sr2.w+20, sr2.h+20), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (0, btn_g, 80, int(40+20*pulse_v)),
                         (10, 10, sr2.w, sr2.h), border_radius=10)
        self.screen.blit(glow_surf, (sr2.left-10, sr2.top-10))
        draw_text(self.screen, "[ ENTER ] BAT DAU!", sr2.center, size=18, color=WHITE, bold=True, center=True)

        # Show client error warning if present
        wr_err = getattr(self, 'waiting_room_error', '')
        wr_err_t = getattr(self, 'waiting_room_error_t', 0)
        if wr_err and pygame.time.get_ticks() - wr_err_t < 3000:
            draw_text(self.screen, wr_err, (SCREEN_WIDTH//2, btn_y2 - 20), size=14, color=RED, bold=True, center=True)

        # Footer scan line
        pygame.draw.line(self.screen, (40, 30, 100),
                         (0, SCREEN_HEIGHT-40), (SCREEN_WIDTH, SCREEN_HEIGHT-40), 1)
        draw_text(self.screen, "IP: " + my_ip + "   PORT: 5555   |   Radmin VPN / LAN",
                  (SCREEN_WIDTH//2, SCREEN_HEIGHT-24), size=13, color=(80,70,130), center=True)


    def draw_host_mode_select(self):
        """Host has started server — pick game mode before launching."""
        self.screen.fill((10, 18, 28))
        # Animated background dots
        for i in range(50):
            x = (i * 191 + int(self.t * 25)) % SCREEN_WIDTH
            y = (i * 113 + int(self.t * 18)) % SCREEN_HEIGHT
            r = int(3 + 2 * math.sin(self.t + i))
            pygame.draw.circle(self.screen, (30, 80, 140), (x, y), r)

        # Title
        draw_text(self.screen, "🌐 SERVER ĐÃ SẴN SÀNG!",
                  (SCREEN_WIDTH // 2, 70), size=54, color=(100, 220, 255), bold=True, center=True)

        # Show IP so friends can connect
        import socket as _sock
        try:
            ip = _sock.gethostbyname(_sock.gethostname())
        except:
            ip = "unknown"
        draw_text(self.screen, f"IP của bạn:  {ip}  :  5555",
                  (SCREEN_WIDTH // 2, 140), size=22, color=GOLD, bold=True, center=True)

        # Connected count
        n_clients = len(self.network.clients)
        client_txt = f"Bạn bè đã vào: {n_clients} người" if n_clients else "Đang chờ bạn bè kết nối..."
        draw_text(self.screen, client_txt,
                  (SCREEN_WIDTH // 2, 185), size=20,
                  color=GREEN if n_clients else (180, 180, 180), center=True)

        # Error message if any
        if self.network.host_error:
            draw_text(self.screen, self.network.host_error,
                      (SCREEN_WIDTH // 2, 215), size=18, color=(255, 80, 80), center=True)

        # Mode options
        modes = [
            ("🗺  HÀNH TRÌNH CỨU CHÓ", "Bắt đầu chiến dịch từ màn 1 — hợp tác cùng bạn bè!"),
            ("⚔  ĐẠI CHIẾN BOSS RUSH",  "Map khổng lồ — tất cả 7 Boss — cùng nhau hạ gục!"),
            ("🔥  ĐẤU TRƯỜNG PvP",      "Chiến đấu sinh tồn — tiêu diệt lẫn nhau để tìm kẻ mạnh nhất!"),
            ("✖  HỦY / QUAY LẠI",        ""),
        ]
        bw, bh = 640, 72
        start_y = 248
        for i, (title, sub) in enumerate(modes):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - bw // 2, start_y + i * (bh + 18), bw, bh)
            is_sel = (self.host_mode_sel == i)

            pygame.draw.rect(self.screen, (0, 0, 0), rect.move(4, 4), border_radius=14)
            if is_sel:
                pygame.draw.rect(self.screen, (20, 60, 100), rect, border_radius=14)
                pygame.draw.rect(self.screen, (100, 200, 255), rect, 3, border_radius=14)
            else:
                pygame.draw.rect(self.screen, (20, 30, 45), rect, border_radius=14)
                pygame.draw.rect(self.screen, (60, 100, 140), rect, 2, border_radius=14)

            tc = (180, 230, 255) if is_sel else (140, 180, 210)
            ty = rect.centery - (12 if sub else 0)
            draw_text(self.screen, title, (rect.centerx, ty),
                      size=26, color=tc, bold=is_sel, center=True)
            if sub:
                draw_text(self.screen, sub, (rect.centerx, ty + 26),
                          size=16, color=(100, 150, 190), center=True)

        draw_text(self.screen, "Mũi tên ↑↓ chọn — ENTER bắt đầu — ESC hủy server",
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 45),
                  size=16, color=(80, 120, 160), center=True)

    def draw_boss_rush_menu(self):
        """Boss Rush mode selection: Solo or Co-op."""
        # Dark crimson background with animated particles
        self.screen.fill((12, 6, 6))
        for i in range(60):
            x = (i * 173 + int(self.t * 30)) % SCREEN_WIDTH
            y = (i * 97 + int(self.t * 20)) % SCREEN_HEIGHT
            alpha_pulse = int(80 + 60 * math.sin(self.t * 2 + i))
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 60, 0, alpha_pulse), (3, 3), 3)
            self.screen.blit(s, (x, y))

        # Title
        glow_col = (255, int(120 + 80 * math.sin(self.t * 3)), 0)
        draw_text(self.screen, "⚡ ĐẠI CHIẾN BOSS RUSH ⚡",
                  (SCREEN_WIDTH // 2, 90), size=62, color=glow_col, bold=True, center=True)
        draw_text(self.screen, "MAP 200x150 • Tất cả 7 Boss • Đầy đủ vũ khí và máu",
                  (SCREEN_WIDTH // 2, 165), size=20, color=(200, 160, 120), center=True)

        # Options
        options = [
            ("⚔  CHƠI MỘT MÌNH  (SOLO)",  "Thữ thách bản thân — đánh bại tất cả 7 Boss!"),
            ("👥  CHƠI VỚI BẠN  (CO-OP)", "Kết nối WiFi — Bạn bè cùng chiến boss!"),
            ("  QUAY LẠI MENU",              ""),
        ]
        bw, bh = 620, 75
        start_y = 230
        for i, (title, subtitle) in enumerate(options):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - bw // 2, start_y + i * (bh + 22), bw, bh)
            is_sel = (self.boss_rush_sel == i)

            # Shadow
            shadow_rect = rect.move(4, 4)
            pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect, border_radius=14)

            # Body
            if is_sel:
                bg = (90, 25, 10)
                border = (255, 120, 0)
                border_w = 3
            else:
                bg = (35, 15, 10)
                border = (120, 60, 30)
                border_w = 2
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            pygame.draw.rect(self.screen, border, rect, border_w, border_radius=14)

            tc = (255, 220, 100) if is_sel else (200, 170, 130)
            ty = rect.centery - (12 if subtitle else 0)
            draw_text(self.screen, title, (rect.centerx, ty),
                      size=26, color=tc, bold=is_sel, center=True)
            if subtitle:
                draw_text(self.screen, subtitle, (rect.centerx, ty + 26),
                          size=16, color=(160, 140, 110), center=True)
        draw_text(self.screen, "Mũi tên ↑↓ chọn — ENTER xác nhận — ESC quay lại",
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50),
                  size=16, color=(130, 110, 90), center=True)

    def draw_char_select(self):
        from settings import SPRITES
        # reuse menu background
        self.screen.fill((15, 22, 15))
        for i in range(40):
            x = (i * 123 + int(self.t * 20)) % SCREEN_WIDTH
            y = (i * 87 + int(self.t * 15)) % SCREEN_HEIGHT
            pygame.draw.circle(self.screen, (25, 45, 30), (x, y), (i % 4) + 1)

        draw_text(self.screen, "CHỌN NHÂN VẬT", (SCREEN_WIDTH // 2, 100), 
                  size=64, color=GOLD, bold=True, center=True)

        # Draw 2 Boxes
        bw, bh = 300, 420
        gap = 60
        start_x = (SCREEN_WIDTH - (bw * 2 + gap)) // 2
        y_pos = 180

        chars = [
            ("GRAB HERO", "grab_down.png", "grab"),
            ("SHOPEE HERO", "shope.png", "shope")
        ]

        for i, (name, img_name, ctype) in enumerate(chars):
            bx = start_x + i * (bw + gap)
            rect = pygame.Rect(bx, y_pos, bw, bh)
            
            is_hover = (self.char_sel_idx == i)
            is_active = (self.char_type == ctype)
            
            # Box background
            bg_color = (60, 50, 30) if is_hover else (40, 35, 25)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=15)
            # Border
            border_color = GOLD if is_hover else (100, 100, 100)
            pygame.draw.rect(self.screen, border_color, rect, 4, border_radius=15)

            # Character Image
            path = SPRITES / img_name
            if path.exists():
                try:
                    img = pygame.image.load(str(path)).convert()
                    bg_color = img.get_at((0, 0))
                    if sum(bg_color[:3]) < 20:
                        img.set_colorkey(bg_color)
                    img = img.convert_alpha()
                    # Scale to fit box
                    ratio = 220 / max(img.get_width(), img.get_height())
                    img = pygame.transform.smoothscale(img, (int(img.get_width() * ratio), int(img.get_height() * ratio)))
                    self.screen.blit(img, (bx + bw // 2 - img.get_width() // 2, y_pos + 40))
                except:
                    pass
            
            # Name
            draw_text(self.screen, name, (bx + bw // 2, y_pos + 300), size=36, color=WHITE, bold=True, center=True)

            # Status Label / Button
            btn_y = y_pos + 350
            btn_rect = pygame.Rect(bx + 40, btn_y, bw - 80, 45)
            if is_active:
                pygame.draw.rect(self.screen, (40, 180, 40), btn_rect, border_radius=10)
                draw_text(self.screen, "ĐÃ CHỌN", (bx + bw // 2, btn_y + 10), size=22, color=WHITE, bold=True, center=True)
            else:
                btn_color = (180, 140, 40) if is_hover else (80, 80, 80)
                pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=10)
                draw_text(self.screen, "CHỌN", (bx + bw // 2, btn_y + 10), size=22, color=WHITE, bold=True, center=True)

        draw_text(self.screen, "Mũi tên TRÁI/PHẢI để di chuyển - ENTER để xác nhận", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60), 
                  size=22, color=(200, 200, 200), center=True)

# ============================================================
    def next_dialog(self):
        """Advances to the next message in the queue."""
        if self.dialog_queue:
            self.dialog_speaker, self.dialog_text = self.dialog_queue.pop(0)
        else:
            self.dialog_speaker = ""
            self.dialog_text = ""

    def queue_dialog(self, speaker, text):
        """Adds a message to the queue and starts it if nothing is playing."""
        self.dialog_queue.append((speaker, text))
        if not self.dialog_text:
            self.next_dialog()

    def check_story_events(self):
        """Triggers dialogues based on level progress or special conditions."""
        if not self.world or not self.player: return
        
        # Trigger Boss Dialog when near boss and not already triggered
        if self.boss_ref and self.boss_ref.alive:
            dist = (self.player.pos - self.boss_ref.pos).length()
            if dist < 650 and not getattr(self.world, "boss_dialog_triggered", False):
                self.world.boss_dialog_triggered = True
                # Trigger the boss dialog logic
                self.trigger_boss_dialog()
        
        # Level specific flavor text (only once per level)
        prog = self.player.pos.x / (self.world.w * TILE)
        if prog > 0.45 and not getattr(self, f"_lvl{self.level_idx}_flavor", False):
            setattr(self, f"_lvl{self.level_idx}_flavor", True)
            if self.level_idx == 0:
                self.queue_dialog("GRAB HERO", "Nơi này thật hoang vắng, mình phải cẩn thận.")
            elif self.level_idx == 2:
                self.queue_dialog("RADIO", "Hổ Vương đang ở rất gần, hãy sẵn sàng chiến đấu!")

    def trigger_boss_dialog(self):
        # Open gate when dialog starts
        self.world.boss_gate_active = False
        for s in self.world.solids:
            if s.kind == "boss_gate":
                s.alive = False

        p_name = self.player.char_type.upper()
        b_name = getattr(self.boss_ref, "name", "BOSS")
        
        msgs = [
            (b_name, "Mày nghĩ mày có thể cứu được nó sao?"),
            (p_name, "Dừng lại đi, mày không thể làm hại sinh vật vô tội này!"),
            (b_name, "Quá muộn rồi. Bây giờ hãy xem bản lĩnh của mày tới đâu!")
        ]
        if self.level_idx == 6: # Final boss
            msgs[1] = (p_name, "Tao sẽ phá hủy toàn bộ cơ sở này để cứu Chó Mẹ!")
            
        for s, t in msgs: self.queue_dialog(s, t)

    def draw_dialog_panel(self):
        """Draws the beautiful cinematic dialogue panel."""
        if not self.dialog_text:
            return
            
        bh = 145
        rect = pygame.Rect(60, SCREEN_HEIGHT - bh - 40, SCREEN_WIDTH - 120, bh)
        
        # Background Panel with border
        pygame.draw.rect(self.screen, (20, 20, 25, 200), rect.move(5, 5), border_radius=15)
        pygame.draw.rect(self.screen, (45, 50, 65), rect, border_radius=15)
        pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=15)
        
        # Speaker Box
        name_w = 200
        name_rect = pygame.Rect(rect.left + 40, rect.top - 20, name_w, 40)
        pygame.draw.rect(self.screen, (35, 35, 45), name_rect, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, name_rect, 2, border_radius=8)
        draw_text(self.screen, self.dialog_speaker, name_rect.center, 
                  size=22, color=GOLD, bold=True, center=True)
                  
        # Wrap and draw text
        words = self.dialog_text.split(' ')
        lines = []
        cur = ""
        for w in words:
            if len(cur + w) < 55: cur += w + " "
            else:
                lines.append(cur)
                cur = w + " "
        lines.append(cur)
        
        for i, line in enumerate(lines[:3]):
            draw_text(self.screen, line, (rect.left + 50, rect.top + 45 + i * 32), 
                      size=24, color=WHITE)
                      
        # Next prompt
        if int(self.t * 3) % 2 == 0:
            draw_text(self.screen, "Nhấn SPACE để tiếp tục ▼", (rect.right - 180, rect.bottom - 25), 
                      size=16, color=GOLD)

    def draw_dialog(self):
        """Main entry for drawing dialogues during play."""
        self.draw_dialog_panel()

if __name__ == "__main__":
    # Removed dummy SDL_AUDIODRIVER to allow real sound output
    Game().run()
