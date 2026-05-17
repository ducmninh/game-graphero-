"""Particle system: blood spurts, muzzle flash, explosions, coin pickup, etc."""
from __future__ import annotations
import math
import random
import pygame
import settings
from utils import Vec, clamp


class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "color", "size", "gravity", "shrink")

    def __init__(self, pos, vel, life, color, size=4, gravity=0.0, shrink=True):
        self.pos = Vec(pos)
        self.vel = Vec(vel)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity
        self.shrink = shrink

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= (1 - dt * 1.5)
        self.vel.y += self.gravity * dt
        return self.life > 0

    def draw(self, surf, cam):
        p = cam.apply(self.pos)
        t = clamp(self.life / self.max_life, 0, 1)
        sz = max(1, int(self.size * (t if self.shrink else 1.0)))
        pygame.draw.circle(surf, self.color, p, sz)


class ParticleSystem:
    def __init__(self):
        self.parts: list[Particle] = []
        self.texts: list[FloatingText] = []

    def update(self, dt):
        self.parts = [p for p in self.parts if p.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]

    def draw(self, surf, cam):
        # Calculate view boundary for culling
        view_rect = pygame.Rect(cam.offset.x - 40, cam.offset.y - 40, 
                                settings.SCREEN_WIDTH + 80, settings.SCREEN_HEIGHT + 80)
        for p in self.parts:
            if view_rect.collidepoint(p.pos.x, p.pos.y):
                p.draw(surf, cam)
        for t in self.texts:
            if view_rect.collidepoint(t.pos.x, t.pos.y):
                t.draw(surf, cam)

    def add(self, pos, vel, color, life=0.5, size=4, gravity=0.0, shrink=True):
        if len(self.parts) > 800: return
        self.parts.append(Particle(pos, vel, life, color, size, gravity, shrink))

    # ------------------------------------------------------------------
    def blood(self, pos, color=(190, 30, 30), count=14):
        for _ in range(count):
            a = random.uniform(0, math.tau)
            sp = random.uniform(60, 240)
            self.parts.append(Particle(
                pos, (math.cos(a) * sp, math.sin(a) * sp),
                life=random.uniform(0.35, 0.7),
                color=color, size=random.randint(3, 6),
            ))

    def muzzle(self, pos, angle, color=(255, 220, 90)):
        for _ in range(5):
            a = angle + random.uniform(-0.35, 0.35)
            sp = random.uniform(120, 260)
            self.parts.append(Particle(
                pos, (math.cos(a) * sp, math.sin(a) * sp),
                life=random.uniform(0.08, 0.16),
                color=color, size=random.randint(3, 6),
            ))

    def explosion(self, pos, color=(255, 140, 40), count=40, big=False):
        rng = (200, 520) if big else (120, 320)
        for _ in range(count):
            a = random.uniform(0, math.tau)
            sp = random.uniform(*rng)
            self.parts.append(Particle(
                pos, (math.cos(a) * sp, math.sin(a) * sp),
                life=random.uniform(0.4, 1.0),
                color=color, size=random.randint(5, 10),
            ))
        # smoke
        for _ in range(15):
            a = random.uniform(0, math.tau)
            sp = random.uniform(30, 120)
            self.parts.append(Particle(
                pos, (math.cos(a) * sp, math.sin(a) * sp),
                life=random.uniform(0.6, 1.2),
                color=(60, 60, 60), size=random.randint(6, 12),
            ))

    def pickup(self, pos, color=(255, 215, 0)):
        for _ in range(8):
            a = random.uniform(0, math.tau)
            sp = random.uniform(80, 180)
            self.parts.append(Particle(
                pos, (math.cos(a) * sp, math.sin(a) * sp - 60),
                life=random.uniform(0.4, 0.6),
                color=color, size=random.randint(3, 5),
                gravity=300,
            ))

    def text(self, pos, msg, color=(255, 255, 255), size=20, life=0.9):
        self.texts.append(FloatingText(pos, msg, color, size, life))


class FloatingText:
    def __init__(self, pos, msg, color, size, life):
        self.pos = Vec(pos)
        self.msg = msg
        self.color = color
        self.size = size
        self.life = life
        self.max = life
        self.vel = Vec(0, -60)

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel.y *= (1 - dt * 1.2)
        return self.life > 0

    def draw(self, surf, cam):
        from utils import draw_text
        t = max(0, self.life / self.max)
        alpha = int(255 * t)
        col = (*self.color[:3], alpha)
        p = cam.apply(self.pos)
        font = pygame.font.SysFont(settings.FONT_PATH, self.size, bold=True)
        img = font.render(self.msg, True, self.color)
        img.set_alpha(alpha)
        sh = font.render(self.msg, True, (0, 0, 0))
        sh.set_alpha(alpha)
        surf.blit(sh, (p[0] - img.get_width() // 2 + 1, p[1] + 1))
        surf.blit(img, (p[0] - img.get_width() // 2, p[1]))
