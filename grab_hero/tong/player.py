"""Player: walk/run/dodge, ride bike, shoot, take damage, swap weapons."""
from __future__ import annotations
import math
import pygame
from utils import Vec, load_sprite_keep_alpha_nearest, draw_text, clamp
from settings import (
    SPRITES, PLAYER_MAX_HP, PLAYER_WALK_SPEED, PLAYER_RUN_SPEED,
    PLAYER_BIKE_SPEED, PLAYER_BIKE_DAMAGE, DODGE_SPEED, DODGE_DURATION,
    DODGE_COOLDOWN, STAMINA_MAX, STAMINA_DRAIN, STAMINA_REGEN,
    PLAYER_SIZE, BIKE_SIZE, STARTING_GOLD,
)
from weapons import Weapon, Bullet


class Player:
    def __init__(self, pos: Vec, char_type: str = "grab"):
        self.pos = Vec(pos)
        self.char_type = char_type
        self.vel = Vec(0, 0)
        self.facing = "down"   # for walking sprite
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.max_stamina = STAMINA_MAX
        self.armor = 0
        self.max_armor = 100
        self.gold = STARTING_GOLD
        self.alive = True
        self.aim = Vec(1, 0)
        self.aim_angle = 0.0

        # Permanent hub upgrade multipliers (applied via
        # hub.apply_upgrades_to_player). Defaults preserve vanilla balance.
        self.upgrade_speed_mult = 1.0
        self.upgrade_fr_mult = 1.0
        self.upgrade_dmg_mult = 1.0

        # State
        self.on_bike = False
        self.running = False
        self.stamina = STAMINA_MAX
        self.dodging = False
        self.dodge_t = 0.0
        self.dodge_cd = 0.0
        self.invuln_t = 0.0
        self.hit_flash = 0.0

        # Weapons
        self.weapons: dict[str, Weapon] = {"pistol": Weapon("pistol", self)}
        self.current = "pistol"
        self.weapon_order = ["pistol"]  # for cycling

        # Sprite caches
        if self.char_type == "shope":
            self.sprites_walk = {
                "left": load_sprite_keep_alpha_nearest(SPRITES / "shope_left.png", PLAYER_SIZE),
                "right": load_sprite_keep_alpha_nearest(SPRITES / "shope_right.png", PLAYER_SIZE),
                "up": load_sprite_keep_alpha_nearest(SPRITES / "shope_up.png", PLAYER_SIZE),
                "down": load_sprite_keep_alpha_nearest(SPRITES / "shope_down.png", PLAYER_SIZE),
                "idle": load_sprite_keep_alpha_nearest(SPRITES / "shope.png", PLAYER_SIZE),
            }
        else:
            self.sprites_walk = {
                "left": load_sprite_keep_alpha_nearest(SPRITES / "grab_left.png", PLAYER_SIZE),
                "right": load_sprite_keep_alpha_nearest(SPRITES / "grab_right.png", PLAYER_SIZE),
                "up": load_sprite_keep_alpha_nearest(SPRITES / "grab_up.png", PLAYER_SIZE),
                "down": load_sprite_keep_alpha_nearest(SPRITES / "grab_down.png", PLAYER_SIZE),
                "idle": load_sprite_keep_alpha_nearest(SPRITES / "grab.png", PLAYER_SIZE),
            }
        self.sprites_ride = {
            "left": load_sprite_keep_alpha_nearest(SPRITES / "riding_left.png", BIKE_SIZE),
            "right": load_sprite_keep_alpha_nearest(SPRITES / "riding_right.png", BIKE_SIZE),
            "up": load_sprite_keep_alpha_nearest(SPRITES / "riding_up.png", BIKE_SIZE),
            "down": load_sprite_keep_alpha_nearest(SPRITES / "riding_down.png", BIKE_SIZE),
        }
        # Real gun overlay sprites (loaded lazily; some weapons fall back to
        # procedural drawing when no sprite is available).
        self._gun_sprites: dict[str, pygame.Surface] = {}
        if self.char_type == "shope":
            # Shopee uses full body sprites for weapons
            for key, fname in (
                ("pistol", "shope_holds_pistol.png"),
                ("pistol_mk2", "shope_holds_pistol.png"),
                ("smg", "shope_holds_smg.png"),
                ("shotgun", "shope_holds_shotgun.png"),
                ("ar", "shope_holds_ar.png"),
                ("sniper", "shope_holds_sniper.png"),
            ):
                path = SPRITES / fname
                if path.exists():
                    self._gun_sprites[key] = load_sprite_keep_alpha_nearest(path, PLAYER_SIZE)
        else:
            for key, fname in (
                ("shotgun", "gun_shotgun_ingame.png"),
                ("smg", "gun_smg_ingame.png"),
                ("sniper", "gun_sniper_ingame.png"),
            ):
                path = SPRITES / fname
                if path.exists():
                    try:
                        img = pygame.image.load(str(path)).convert_alpha()
                        longest = max(img.get_size())
                        target = 52
                        scale = target / longest
                        new_size = (int(img.get_width() * scale),
                                    int(img.get_height() * scale))
                        img = pygame.transform.smoothscale(img, new_size)
                        self._gun_sprites[key] = img
                    except (pygame.error, OSError):
                        pass

    # --------------------------------------------------------------
    @property
    def weapon(self) -> Weapon:
        return self.weapons[self.current]

    @property
    def radius(self) -> int:
        return 18 if not self.on_bike else 22

    @property
    def rect(self) -> pygame.Rect:
        r = self.radius
        return pygame.Rect(int(self.pos.x - r), int(self.pos.y - r), 2 * r, 2 * r)

    # --------------------------------------------------------------
    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def add_gold(self, amount: int):
        self.gold += amount

    def take_damage(self, amount: float):
        if self.invuln_t > 0 or self.dodging:
            return
        
        # Armor absorbs damage first
        if self.armor > 0:
            reduction = min(self.armor, amount)
            self.armor -= reduction
            amount -= reduction
            
        if amount <= 0:
            return

        self.hp -= amount
        self.hit_flash = 0.25
        self.invuln_t = 0.4
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def add_weapon(self, key: str):
        if key not in self.weapons:
            self.weapons[key] = Weapon(key, self)
            self.weapon_order.append(key)

    def switch_weapon(self, key: str):
        if key in self.weapons:
            self.current = key

    def cycle_weapon(self, direction: int):
        if not self.weapon_order:
            return
        i = self.weapon_order.index(self.current) if self.current in self.weapon_order else 0
        i = (i + direction) % len(self.weapon_order)
        self.current = self.weapon_order[i]

    # --------------------------------------------------------------
    def update(self, dt, keys, mouse_world: Vec, world, particles):
        # Aim
        ax = mouse_world.x - self.pos.x
        ay = mouse_world.y - self.pos.y
        self.aim_angle = math.atan2(ay, ax)
        if abs(ax) > 0.01 or abs(ay) > 0.01:
            self.aim = Vec(ax, ay).normalize()

        # Timers
        if self.invuln_t > 0:
            self.invuln_t = max(0, self.invuln_t - dt)
        if self.hit_flash > 0:
            self.hit_flash = max(0, self.hit_flash - dt)
        if self.dodge_cd > 0:
            self.dodge_cd = max(0, self.dodge_cd - dt)

        # Dodge state
        if self.dodging:
            self.dodge_t -= dt
            if self.dodge_t <= 0:
                self.dodging = False

        # Inputs (movement)
        dx = dy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
            self.facing = "left"
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
            self.facing = "right"
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
            self.facing = "up"
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
            self.facing = "down"

        moving = (dx != 0 or dy != 0)
        # face aim (only if mouse moved meaningfully) so weapon points right way
        if moving:
            if abs(dx) > abs(dy):
                self.facing = "left" if dx < 0 else "right"
            else:
                self.facing = "up" if dy < 0 else "down"

        # determine speed
        if self.dodging:
            speed = DODGE_SPEED
            mvx, mvy = self._dodge_dir
        else:
            if self.on_bike:
                speed = PLAYER_BIKE_SPEED
                self.running = False
            else:
                want_run = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and self.stamina > 0
                self.running = want_run and moving
                base = PLAYER_RUN_SPEED if self.running else PLAYER_WALK_SPEED
                speed = base * self.upgrade_speed_mult
            if moving:
                n = math.hypot(dx, dy) or 1
                mvx, mvy = dx / n, dy / n
            else:
                mvx, mvy = 0, 0

        # Stamina (uses upgrade-aware max_stamina)
        if self.running and moving and not self.on_bike:
            self.stamina = max(0, self.stamina - STAMINA_DRAIN * dt)
        else:
            self.stamina = min(self.max_stamina,
                               self.stamina + STAMINA_REGEN * dt)

        # Movement with collision (axis separate)
        new_x = self.pos.x + mvx * speed * dt
        new_y = self.pos.y + mvy * speed * dt
        r = self.radius

        # Check collision on X
        rect_x = pygame.Rect(int(new_x - r), int(self.pos.y - r), 2 * r, 2 * r)
        if not world.collides(rect_x):
            self.pos.x = new_x

        rect_y = pygame.Rect(int(self.pos.x - r), int(new_y - r), 2 * r, 2 * r)
        if not world.collides(rect_y):
            self.pos.y = new_y

        # clamp to world bounds
        ww, wh = world.pixel_size()
        self.pos.x = clamp(self.pos.x, r, ww - r)
        self.pos.y = clamp(self.pos.y, r, wh - r)

        # Weapons
        self.weapon.update(dt)

    # --------------------------------------------------------------
    def start_dodge(self, dx, dy):
        if self.dodge_cd > 0 or self.dodging or self.on_bike:
            return
        if dx == 0 and dy == 0:
            # dodge in facing direction
            dx, dy = {"left": (-1, 0), "right": (1, 0),
                      "up": (0, -1), "down": (0, 1),
                      "idle": (0, 1)}[self.facing]
        n = math.hypot(dx, dy) or 1
        self._dodge_dir = (dx / n, dy / n)
        self.dodging = True
        self.dodge_t = DODGE_DURATION
        self.dodge_cd = DODGE_COOLDOWN

    def toggle_bike(self, nearest_bike) -> bool:
        """Toggle on/off bike. nearest_bike is a Solid of kind 'bike' or None."""
        if self.on_bike:
            # park bike: spawn a bike solid at current pos
            self.on_bike = False
            return True
        else:
            if nearest_bike and ((Vec(nearest_bike.rect.center) - self.pos).length() < 60):
                nearest_bike.alive = False  # consume parked bike
                self.on_bike = True
                return True
        return False

    def try_fire(self, world) -> list[Bullet]:
        if self.on_bike:
            return []
        muzzle = self.pos + Vec(math.cos(self.aim_angle), math.sin(self.aim_angle)) * 26
        return self.weapon.fire(muzzle, self.aim_angle, owner="player")

    def reload(self):
        self.weapon.start_reload()

    # --------------------------------------------------------------
    def draw(self, surf, cam, t):
        sprite_dir = self.facing if self.facing in ("left", "right", "up", "down") else "down"
        if self.on_bike:
            spr = self.sprites_ride[sprite_dir]
            sz = BIKE_SIZE
        else:
            spr = self.sprites_walk[sprite_dir]
            sz = PLAYER_SIZE
            
            # SHOPEE FULL BODY OVERRIDE
            if self.char_type == "shope" and self.current in self._gun_sprites:
                spr = self._gun_sprites[self.current]
                # Flip if aiming left
                if abs(self.aim_angle) > math.pi / 2:
                    spr = pygame.transform.flip(spr, True, False)

        # Flash white on hit
        if self.hit_flash > 0:
            # tint sprite white briefly
            tinted = spr.copy()
            white = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
            white.fill((255, 255, 255, 180))
            tinted.blit(white, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            spr = tinted

        # Blink while long-invulnerable (level start / respawn grace)
        if self.invuln_t > 0.5:
            if int(t * 12) % 2 == 0:
                spr = spr.copy()
                spr.set_alpha(140)

        if self.dodging:
            # subtle motion blur (low alpha trails)
            for i in range(3):
                ghost = spr.copy()
                ghost.set_alpha(60)
                trail_pos = self.pos - Vec(self._dodge_dir) * (8 * (i + 1))
                gp = cam.apply(trail_pos)
                surf.blit(ghost, (gp[0] - sz // 2, gp[1] - sz // 2))

        p = cam.apply(self.pos)
        # shadow
        shadow = pygame.Surface((sz, sz // 3), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90),
                            (0, 0, sz, sz // 3))
        surf.blit(shadow, (p[0] - sz // 2, p[1] + sz // 3))

        if spr:
            surf.blit(spr, (p[0] - sz // 2, p[1] - sz // 2))
        else:
            # Enhanced fallback if no sprites
            pygame.draw.circle(surf, (50, 200, 80), p, sz // 2)
            # Add simple eyes based on facing
            eye_off = Vec(0, 0)
            if self.facing == "left": eye_off = Vec(-8, -2)
            elif self.facing == "right": eye_off = Vec(8, -2)
            elif self.facing == "up": eye_off = Vec(0, -8)
            else: eye_off = Vec(0, 4)
            pygame.draw.circle(surf, (0, 0, 0), (int(p[0] + eye_off.x), int(p[1] + eye_off.y)), 3)
            pygame.draw.circle(surf, (255, 255, 255), (int(p[0] + eye_off.x - 1), int(p[1] + eye_off.y - 1)), 1)

        # Gun in hand (only when off-bike) — rotates with aim
        if not self.on_bike and self.char_type == "grab":
            self._draw_gun_in_hand(surf, p, t)

        # Reload indicator above head
        if self.weapon.reloading:
            pct = self.weapon.reload_progress()
            bar_w = 36
            x = p[0] - bar_w // 2
            y = p[1] - sz // 2 - 14
            pygame.draw.rect(surf, (40, 40, 40), (x, y, bar_w, 5))
            pygame.draw.rect(surf, (255, 220, 90), (x, y, int(bar_w * pct), 5))

        # Subtle aim indicator (small line) - REMOVED per user request
        # if not self.on_bike:
        #     ang = self.aim_angle
        #     ax = p[0] + math.cos(ang) * 30
        #     ay = p[1] + math.sin(ang) * 30
        #     pygame.draw.line(surf, (255, 230, 90), p, (int(ax), int(ay)), 2)
        #     pygame.draw.circle(surf, (255, 230, 90), (int(ax), int(ay)), 3)

    # --------------------------------------------------------------
    def _draw_gun_in_hand(self, surf, p, t):
        """Draw the current weapon in the player's hand pointing at aim.

        Prefers real pixel-art sprites for shotgun/smg/sniper, falls back
        to procedural rectangles for pistol / pistol_mk2 / ar / grenade."""
        key = self.weapon.key
        ang = self.aim_angle
        hand_x = p[0] + math.cos(ang) * 12
        hand_y = p[1] + math.sin(ang) * 12

        # ------------ Real-sprite branch (shotgun / smg / sniper) ------
        spr = self._gun_sprites.get(key)
        if spr is not None:
            # The sprite faces right. Rotate by -aim_angle (pygame's
            # rotate is counter-clockwise).
            deg = -math.degrees(ang)
            rotated = pygame.transform.rotate(spr, deg)
            rect = rotated.get_rect(center=(hand_x, hand_y))
            surf.blit(rotated, rect)
            # Muzzle flash if just fired
            cd_full = 1.0 / max(0.001, self.weapon.fire_rate)
            if cd_full - self.weapon.fire_cd < 0.05 and not self.weapon.reloading:
                mx = p[0] + math.cos(ang) * 44
                my = p[1] + math.sin(ang) * 44
                pygame.draw.circle(surf, (255, 230, 130), (int(mx), int(my)), 8)
                pygame.draw.circle(surf, (255, 160, 60), (int(mx), int(my)), 4)
            return

        # ------------ Procedural fallback -----------------------------
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)
        color = self.weapon.spec.get("color", (220, 220, 220))
        dark = (max(0, color[0] - 60), max(0, color[1] - 60),
                max(0, color[2] - 60))
        sizing = {
            "pistol": (18, 5, 6, 7),
            "pistol_mk2": (20, 5, 6, 7),
            "ar": (30, 6, 6, 8),
            "grenade": (24, 10, 7, 9),
        }
        bl, bw, gw, gh = sizing.get(key, (20, 5, 6, 7))

        def rot(lx, ly):
            return (hand_x + lx * cos_a - ly * sin_a,
                    hand_y + lx * sin_a + ly * cos_a)

        barrel = [rot(0, -bw // 2), rot(bl, -bw // 2),
                  rot(bl, bw // 2), rot(0, bw // 2)]
        pygame.draw.polygon(surf, color, barrel)
        pygame.draw.polygon(surf, dark, barrel, 1)
        grip = [rot(-gw, 0), rot(0, 0), rot(0, gh), rot(-gw, gh)]
        pygame.draw.polygon(surf, dark, grip)
        pygame.draw.polygon(surf, (0, 0, 0), grip, 1)
        if key == "ar":
            sp = rot(bl - 6, -bw // 2 - 3)
            pygame.draw.circle(surf, (220, 60, 60),
                               (int(sp[0]), int(sp[1])), 2)
        cd_full = 1.0 / max(0.001, self.weapon.fire_rate)
        if cd_full - self.weapon.fire_cd < 0.05 and not self.weapon.reloading:
            mp = rot(bl + 4, 0)
            pygame.draw.circle(surf, (255, 230, 130),
                               (int(mp[0]), int(mp[1])), 6)
            pygame.draw.circle(surf, (255, 160, 60),
                               (int(mp[0]), int(mp[1])), 3)
