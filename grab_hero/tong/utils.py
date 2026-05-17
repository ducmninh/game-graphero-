"""Utility helpers: vectors, math, drawing primitives."""
from __future__ import annotations
import math
import random
import pygame
import settings
from typing import Iterable, Tuple


# ============================================================
# Vector helpers (using pygame.math.Vector2 everywhere)
# ============================================================
Vec = pygame.math.Vector2


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def angle_between(a: Vec, b: Vec) -> float:
    return math.atan2(b.y - a.y, b.x - a.x)


def vec_from_angle(angle: float, length: float = 1.0) -> Vec:
    return Vec(math.cos(angle) * length, math.sin(angle) * length)


def distance(a: Vec, b: Vec) -> float:
    return (a - b).length()


def dist_sq(a: Vec, b: Vec) -> float:
    return (a - b).length_squared()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


# ============================================================
# Sprite loading / scaling
# ============================================================
_sprite_cache: dict = {}


def load_sprite(path, size: int | None = None) -> pygame.Surface:
    """Load a PNG with alpha, optionally scaled to a square size."""
    key = (str(path), size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    img = pygame.image.load(str(path)).convert_alpha()
    if size is not None:
        # Maintain aspect; assume square sources
        img = pygame.transform.smoothscale(img, (size, size))
    _sprite_cache[key] = img
    return img


def load_sprite_keep_alpha_nearest(path, size: int) -> pygame.Surface:
    """Load preserving pixel-art crisp edges (nearest-neighbour scale)."""
    key = ("nn", str(path), size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    img = pygame.image.load(str(path)).convert_alpha()
    img = pygame.transform.scale(img, (size, size))
    _sprite_cache[key] = img
    return img


# ============================================================
# Drawing primitives
# ============================================================
def draw_text(
    surf: pygame.Surface,
    text: str,
    pos,
    size: int = 22,
    color=(255, 255, 255),
    bold: bool = False,
    center: bool = False,
    shadow: bool = True,
    shadow_color=(0, 0, 0),
):
    font = pygame.font.SysFont(settings.FONT_PATH, size, bold=bold)
    if shadow:
        sh = font.render(text, True, shadow_color)
        if center:
            r = sh.get_rect(center=(pos[0] + 2, pos[1] + 2))
            surf.blit(sh, r)
        else:
            surf.blit(sh, (pos[0] + 2, pos[1] + 2))
    img = font.render(text, True, color)
    if center:
        r = img.get_rect(center=pos)
        surf.blit(img, r)
    else:
        surf.blit(img, pos)
    return img.get_rect()


def draw_bar(
    surf,
    x,
    y,
    w,
    h,
    pct,
    fg=(220, 60, 60),
    bg=(40, 40, 40),
    border=(0, 0, 0),
    border_w=2,
):
    pct = clamp(pct, 0.0, 1.0)
    pygame.draw.rect(surf, bg, (x, y, w, h))
    pygame.draw.rect(surf, fg, (x, y, int(w * pct), h))
    if border_w > 0:
        pygame.draw.rect(surf, border, (x, y, w, h), border_w)


def draw_panel(surf, rect, fill=(0, 0, 0, 170), border=(255, 255, 255)):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill(fill)
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2)


# ============================================================
# Random helpers
# ============================================================
def chance(p: float) -> bool:
    return random.random() < p


def rand_in_circle(center: Vec, radius: float) -> Vec:
    a = random.uniform(0, math.tau)
    r = math.sqrt(random.random()) * radius
    return Vec(center.x + math.cos(a) * r, center.y + math.sin(a) * r)
