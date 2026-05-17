"""Weapons + bullets + ammo system."""
from __future__ import annotations
import math
import pygame
import random
from utils import Vec, vec_from_angle, clamp
from settings import WEAPONS


class Bullet:
    __slots__ = ("pos", "vel", "life", "damage", "owner", "color", "size",
                 "aoe", "pierce", "trail")

    def __init__(self, pos, angle, speed, damage, owner, color,
                 size=4, aoe=0, pierce=False, life=1.4):
        self.pos = Vec(pos)
        self.vel = vec_from_angle(angle, speed)
        self.life = life
        self.damage = damage
        self.owner = owner  # 'player' or 'enemy'
        self.color = color
        self.size = size
        self.aoe = aoe
        self.pierce = pierce
        self.trail = []

    def update(self, dt):
        self.life -= dt
        self.trail.append(Vec(self.pos))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.pos += self.vel * dt
        return self.life > 0

    def draw(self, surf, cam):
        # Draw motion trail (simple lines for performance)
        if len(self.trail) > 1:
            points = [cam.apply(t) for t in self.trail]
            # Draw a fading trail
            for i in range(len(points) - 1):
                alpha = int(150 * (i / len(points)))
                col = (*self.color, alpha)
                # Note: pygame.draw.line doesn't support alpha easily on main surf, 
                # but we can use a small glow circle or just a colored line.
                pygame.draw.line(surf, self.color, points[i], points[i+1], max(1, self.size - 2))

        # Draw bullet head (elongated)
        p = cam.apply(self.pos)
        angle = math.atan2(self.vel.y, self.vel.x)
        
        # Bullet length depends on its size/type
        length = self.size * 2.5
        # Back point
        p_back = (p[0] - math.cos(angle) * length, p[1] - math.sin(angle) * length)
        
        # Outer glow/body
        pygame.draw.line(surf, self.color, p_back, p, self.size)
        # Inner bright core
        pygame.draw.line(surf, (255, 255, 255), p_back, p, max(1, self.size - 2))
        # Head highlight
        pygame.draw.circle(surf, (255, 255, 255), p, max(1, self.size - 1))


class Weapon:
    """Player weapon with upgrade levels.

    ``owner`` is an optional reference to the player object, used to read
    permanent hub-level upgrade multipliers. When ``owner`` is ``None`` the
    weapon behaves like a vanilla weapon (used in shop previews).
    """

    def __init__(self, key: str, owner=None):
        self.key = key
        self.spec = dict(WEAPONS[key])
        self.owner = owner
        self.dmg_lvl = 0
        self.fr_lvl = 0
        self.mag_lvl = 0
        self.ammo_in_mag = self.spec["mag"]
        self.ammo_reserve = self.spec.get("ammo_reserve", 9999)
        self.fire_cd = 0.0
        self.reloading = False
        self.reload_t = 0.0
        self.shoot_anim = 0.0

    # ---------- stats ----------
    def _owner_mult(self, attr, default=1.0):
        if self.owner is None:
            return default
        return getattr(self.owner, attr, default)

    @property
    def damage(self):
        base = self.spec["damage"] * (1.0 + 0.30 * self.dmg_lvl)
        return base * self._owner_mult("upgrade_dmg_mult")

    @property
    def fire_rate(self):
        base = self.spec["fire_rate"] * (1.0 + 0.20 * self.fr_lvl)
        return base * self._owner_mult("upgrade_fr_mult")

    @property
    def mag_size(self):
        return int(self.spec["mag"] * (1.0 + 0.40 * self.mag_lvl))

    @property
    def reload_time(self):
        return self.spec["reload_time"] * (1.0 - 0.10 * self.fr_lvl)

    # ---------- runtime ----------
    def update(self, dt):
        if self.fire_cd > 0:
            self.fire_cd -= dt
        if self.shoot_anim > 0:
            self.shoot_anim = max(0, self.shoot_anim - dt)
        if self.reloading:
            self.reload_t -= dt
            if self.reload_t <= 0:
                need = self.mag_size - self.ammo_in_mag
                take = min(need, self.ammo_reserve)
                # pistol family has infinite reserve
                if self.ammo_reserve >= 9999:
                    take = need
                else:
                    self.ammo_reserve -= take
                self.ammo_in_mag += take
                self.reloading = False

    def can_fire(self) -> bool:
        return (not self.reloading) and self.fire_cd <= 0 and self.ammo_in_mag > 0

    def start_reload(self):
        if self.reloading or self.ammo_in_mag >= self.mag_size:
            return
        if self.ammo_reserve <= 0 and self.spec.get("ammo_reserve", 0) < 9999:
            return
        self.reloading = True
        self.reload_t = self.reload_time

    def fire(self, pos: Vec, angle: float, owner: str = "player") -> list[Bullet]:
        if not self.can_fire():
            return []
        self.fire_cd = 1.0 / self.fire_rate
        self.shoot_anim = 0.15
        self.ammo_in_mag -= 1
        if self.ammo_in_mag <= 0:
            self.start_reload()
        bullets = []
        pellets = self.spec.get("pellets", 1)
        spread = math.radians(self.spec.get("spread", 0))
        speed = self.spec["bullet_speed"]
        color = self.spec.get("color", (255, 230, 100))
        size = 5 if self.key in ("sniper", "grenade") else 4
        aoe = self.spec.get("aoe", 0)
        for _ in range(pellets):
            a = angle + random.uniform(-spread, spread)
            bullets.append(Bullet(
                pos, a, speed, self.damage, owner, color,
                size=size, aoe=aoe,
                life=2.0 if self.key == "sniper" else 1.4,
            ))
        return bullets

    # ---------- helpers ----------
    def reload_progress(self) -> float:
        if not self.reloading:
            return 1.0
        return 1.0 - clamp(self.reload_t / self.reload_time, 0, 1)
