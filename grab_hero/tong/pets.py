"""Pet companions: Dog (melee), Cat (laser), Eagle (orbit AOE).

The active pet (if any) is loaded from the player's save when a level starts
and follows them around, attacking nearby enemies.
"""
from __future__ import annotations
import math
import random
import pygame
from utils import Vec, clamp, vec_from_angle
from settings import PETS
from weapons import Bullet


class Pet:
    """A single pet that follows the player and attacks enemies."""

    def __init__(self, kind: str, pos: Vec):
        spec = PETS[kind]
        self.kind = kind
        self.spec = spec
        self.pos = Vec(pos)
        self.vel = Vec(0, 0)
        self.size = spec["size"]
        self.speed = spec["speed"]
        self.attack_range = spec["attack_range"]
        self.attack_cd_max = spec["attack_cd"]
        self.attack_cd = 0.0
        self.damage = spec["damage"]
        self.color = spec["color"]
        self.facing = Vec(1, 0)
        self.bob = random.uniform(0, math.tau)
        self.orbit_angle = random.uniform(0, math.tau)
        self.alive = True

    # ----------------------------------------------------------
    def _nearest_enemy(self, enemies):
        best = None
        best_d = 1e18
        for e in enemies:
            if not e.alive:
                continue
            d = (Vec(e.pos) - self.pos).length_squared()
            if d < best_d:
                best_d = d
                best = e
        return best, math.sqrt(best_d) if best else 0

    # ----------------------------------------------------------
    def update(self, dt, player, enemies, world, bullets, particles, t, sounds=None):
        self.bob += dt * 5
        self.attack_cd = max(0.0, self.attack_cd - dt)

        # Movement: orbit for eagle, follow at offset for dog/cat
        if self.kind == "eagle":
            self.orbit_angle += dt * 2.4
            radius = 90
            tx = player.pos.x + math.cos(self.orbit_angle) * radius
            ty = player.pos.y + math.sin(self.orbit_angle) * radius
            target = Vec(tx, ty)
            diff = target - self.pos
            if diff.length() > 1:
                step = diff.normalize() * self.speed * dt
                if step.length() > diff.length():
                    self.pos = target
                else:
                    self.pos += step
                self.facing = diff.normalize() if diff.length() > 0.01 else self.facing
        else:
            # Follow behind the player with a small lag
            offset = Vec(-40, 30) if self.kind == "dog" else Vec(40, 30)
            target = player.pos + offset
            diff = target - self.pos
            d = diff.length()
            if d > 8:
                step = diff.normalize() * self.speed * dt
                if step.length() > d:
                    self.pos = target
                else:
                    self.pos += step
                if step.length() > 0.01:
                    self.facing = step.normalize()

        # Attack logic
        if self.kind == "dog":
            self._update_melee(dt, enemies, particles, sounds)
        elif self.kind == "cat":
            self._update_ranged(dt, enemies, bullets, particles, sounds)
        elif self.kind == "eagle":
            self._update_aoe(dt, enemies, particles, sounds)

    # ----------------------------------------------------------
    def _update_melee(self, dt, enemies, particles, sounds=None):
        if self.attack_cd > 0:
            return
        for e in enemies:
            if not e.alive:
                continue
            if (Vec(e.pos) - self.pos).length() < self.attack_range:
                dirv = Vec(e.pos) - self.pos
                if dirv.length() > 0.01:
                    dirv = dirv.normalize()
                else:
                    dirv = Vec(1, 0)
                e.take_damage(self.damage, dirv)
                particles.blood(e.pos, count=4)
                self.attack_cd = self.attack_cd_max
                return

    def _update_ranged(self, dt, enemies, bullets, particles, sounds=None):
        if self.attack_cd > 0:
            return
        target, dist = self._nearest_enemy(enemies)
        if target is None or dist > self.attack_range:
            return
        ang = math.atan2(target.pos.y - self.pos.y,
                         target.pos.x - self.pos.x)
        b = Bullet(
            self.pos + vec_from_angle(ang, 18),
            ang, self.spec["bullet_speed"], self.damage,
            owner="player",
            color=self.spec["bullet_color"],
            size=3,
            life=1.0,
        )
        bullets.append(b)
        particles.muzzle(self.pos, ang, color=self.spec["bullet_color"])
        if sounds and "pistol" in sounds:
            sounds["pistol"].play()
        self.attack_cd = self.attack_cd_max

    def _update_aoe(self, dt, enemies, particles, sounds=None):
        if self.attack_cd > 0:
            return
        any_hit = False
        for e in enemies:
            if not e.alive:
                continue
            if (Vec(e.pos) - self.pos).length() < self.attack_range:
                dirv = Vec(e.pos) - self.pos
                if dirv.length() > 0.01:
                    dirv = dirv.normalize()
                else:
                    dirv = Vec(1, 0)
                e.take_damage(self.damage, dirv)
                particles.blood(e.pos, count=3)
                any_hit = True
        if any_hit:
            self.attack_cd = self.attack_cd_max

    # ----------------------------------------------------------
    def draw(self, surf, cam, t):
        p = cam.apply(self.pos)
        bob = math.sin(self.bob) * 2
        cx, cy = int(p[0]), int(p[1] + bob)
        s = self.size

        # shadow
        shadow = pygame.Surface((s + 8, (s // 3) + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        surf.blit(shadow, (cx - shadow.get_width() // 2, cy + s // 3))

        if self.kind == "dog":
            self._draw_dog(surf, cx, cy)
        elif self.kind == "cat":
            self._draw_cat(surf, cx, cy)
        elif self.kind == "eagle":
            self._draw_eagle(surf, cx, cy)

    def _draw_dog(self, surf, cx, cy):
        s = self.size
        # body
        pygame.draw.ellipse(surf, self.color, (cx - s, cy - s // 3, s * 2, s))
        pygame.draw.ellipse(surf, (40, 30, 20), (cx - s, cy - s // 3, s * 2, s), 2)
        # head
        head_x = cx + int(self.facing.x * s * 0.7)
        head_y = cy + int(self.facing.y * s * 0.4) - s // 4
        pygame.draw.circle(surf, self.color, (head_x, head_y), s // 2)
        pygame.draw.circle(surf, (40, 30, 20), (head_x, head_y), s // 2, 2)
        # ears
        pygame.draw.circle(surf, (140, 100, 60),
                           (head_x - s // 3, head_y - s // 3), s // 4)
        pygame.draw.circle(surf, (140, 100, 60),
                           (head_x + s // 3, head_y - s // 3), s // 4)
        # nose
        pygame.draw.circle(surf, (40, 30, 20),
                           (head_x + int(self.facing.x * 6),
                            head_y + int(self.facing.y * 4) + 2), 2)
        # eyes
        pygame.draw.circle(surf, (20, 20, 20),
                           (head_x - 4, head_y - 2), 2)
        pygame.draw.circle(surf, (20, 20, 20),
                           (head_x + 4, head_y - 2), 2)

    def _draw_cat(self, surf, cx, cy):
        s = self.size
        # body
        pygame.draw.ellipse(surf, self.color, (cx - s, cy - s // 3, s * 2, s))
        pygame.draw.ellipse(surf, (90, 50, 20), (cx - s, cy - s // 3, s * 2, s), 2)
        # stripes
        for ox in (-6, 0, 6):
            pygame.draw.line(surf, (90, 50, 20),
                             (cx + ox, cy - 4), (cx + ox, cy + 4), 1)
        # head
        head_x = cx + int(self.facing.x * s * 0.7)
        head_y = cy + int(self.facing.y * s * 0.4) - s // 4
        pygame.draw.circle(surf, self.color, (head_x, head_y), s // 2)
        # pointy ears (triangular)
        ear_w = s // 3
        pygame.draw.polygon(surf, self.color, [
            (head_x - s // 2, head_y - 2),
            (head_x - s // 2 + ear_w, head_y - ear_w - 4),
            (head_x - s // 2 + ear_w + 2, head_y - 2),
        ])
        pygame.draw.polygon(surf, self.color, [
            (head_x + s // 2, head_y - 2),
            (head_x + s // 2 - ear_w, head_y - ear_w - 4),
            (head_x + s // 2 - ear_w - 2, head_y - 2),
        ])
        # eyes (glowing pink to match laser)
        pygame.draw.circle(surf, (255, 100, 220), (head_x - 4, head_y - 1), 2)
        pygame.draw.circle(surf, (255, 100, 220), (head_x + 4, head_y - 1), 2)

    def _draw_eagle(self, surf, cx, cy):
        s = self.size
        # wing flap based on bob
        flap = math.sin(self.bob * 2) * 5
        # body
        pygame.draw.ellipse(surf, self.color,
                            (cx - s // 2, cy - s // 3, s, s * 2 // 3))
        pygame.draw.ellipse(surf, (40, 30, 20),
                            (cx - s // 2, cy - s // 3, s, s * 2 // 3), 2)
        # wings (triangles)
        wing_l = [
            (cx - 4, cy - 2),
            (cx - s - 4, cy - 2 + int(flap)),
            (cx - 4, cy + 4 + int(flap)),
        ]
        wing_r = [
            (cx + 4, cy - 2),
            (cx + s + 4, cy - 2 + int(flap)),
            (cx + 4, cy + 4 + int(flap)),
        ]
        pygame.draw.polygon(surf, (60, 40, 25), wing_l)
        pygame.draw.polygon(surf, (60, 40, 25), wing_r)
        pygame.draw.polygon(surf, (40, 30, 20), wing_l, 1)
        pygame.draw.polygon(surf, (40, 30, 20), wing_r, 1)
        # head (white)
        head_x = cx + int(self.facing.x * 8)
        head_y = cy - s // 4
        pygame.draw.circle(surf, (235, 235, 230), (head_x, head_y), 7)
        # beak
        beak_dir = self.facing
        if beak_dir.length() < 0.1:
            beak_dir = Vec(1, 0)
        else:
            beak_dir = beak_dir.normalize()
        pygame.draw.polygon(surf, (255, 200, 60), [
            (head_x + int(beak_dir.x * 6), head_y + int(beak_dir.y * 6)),
            (head_x + int(beak_dir.x * 12), head_y + int(beak_dir.y * 12) - 1),
            (head_x + int(beak_dir.x * 12), head_y + int(beak_dir.y * 12) + 2),
        ])
        # eye
        pygame.draw.circle(surf, (20, 20, 20),
                           (head_x + int(beak_dir.x * 2),
                            head_y + int(beak_dir.y * 2) - 1), 2)
        # AOE ring pulse if attacking soon
        if self.attack_cd < 0.12:
            ring = pygame.Surface((self.attack_range * 2,
                                   self.attack_range * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 200, 60, 50),
                               (self.attack_range, self.attack_range),
                               self.attack_range, 3)
            surf.blit(ring, (cx - self.attack_range, cy - self.attack_range))
