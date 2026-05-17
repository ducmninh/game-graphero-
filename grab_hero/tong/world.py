"""World: tile-based map with houses, props, doors, collidables.

The world is composed of:
- A background tile grid (grass / road / dirt / concrete / sand)
- A list of solid rects (walls, houses, fences, containers, ...) for collision
- A list of props (cars, oil drums, crates, trees) for visuals + some collidable
- A list of pickups (gold, ammo, medkit)
- A list of building interiors (we render them differently if biome wants it)

Each level builds its own World via LevelBuilder.
"""
from __future__ import annotations
import math
import random
import pygame
from utils import Vec, draw_text
from settings import (
    TILE, SCREEN_WIDTH, SCREEN_HEIGHT, ROAD, ROAD_LINE, GRASS, GRASS_DARK, DIRT, CONCRETE,
    WALL_TAN, WALL_WHITE, ROOF_RED, ROOF_BLUE, BROWN, DARK_BROWN,
    DARK_GRAY, GRAY, LIGHT_GRAY, SAND, RED, YELLOW, GREEN, BLUE,
    DARK_GREEN, NEON_PINK, NEON_CYAN, BLACK, WHITE, ASH,
)


# ============================================================
# TILE TYPES
# ============================================================
T_GRASS = 0
T_ROAD_H = 1     # horizontal road (with dashed line)
T_ROAD_V = 2     # vertical road
T_ROAD_X = 3     # intersection
T_DIRT = 4
T_CONCRETE = 5
T_SAND = 6
T_GRASS_DARK = 7
T_FLOOR_WOOD = 8
T_FLOOR_TILE = 9
T_WATER = 10
T_ASH = 11        # industrial dark floor


TILE_COLORS = {
    T_GRASS: GRASS,
    T_ROAD_H: ROAD,
    T_ROAD_V: ROAD,
    T_ROAD_X: ROAD,
    T_DIRT: DIRT,
    T_CONCRETE: CONCRETE,
    T_SAND: SAND,
    T_GRASS_DARK: GRASS_DARK,
    T_FLOOR_WOOD: (130, 90, 55),
    T_FLOOR_TILE: (210, 210, 220),
    T_WATER: (60, 110, 180),
    T_ASH: ASH,
}


# ============================================================
# Pickup types
# ============================================================
P_GOLD = "gold"
P_MEDKIT = "medkit"
P_AMMO = "ammo"
P_KEY = "key"


class Pickup:
    def __init__(self, pos: Vec, kind: str, amount: int = 0):
        self.pos = Vec(pos)
        self.kind = kind
        self.amount = amount
        self.bob = random.uniform(0, math.tau)
        self.alive = True

    def update(self, dt, t):
        self.bob += dt * 3

    def draw(self, surf, cam):
        p = cam.apply(self.pos)
        offset = math.sin(self.bob) * 3
        cx, cy = p[0], int(p[1] + offset)
        if self.kind == P_GOLD:
            pygame.draw.circle(surf, (110, 80, 0), (cx, cy + 1), 11)
            pygame.draw.circle(surf, (255, 215, 0), (cx, cy), 10)
            pygame.draw.circle(surf, (255, 240, 130), (cx - 3, cy - 3), 3)
            draw_text(surf, "$", (cx, cy), size=14, color=(110, 80, 0),
                      bold=True, center=True, shadow=False)
        elif self.kind == P_MEDKIT:
            pygame.draw.rect(surf, (240, 240, 240),
                             (cx - 11, cy - 9 + offset, 22, 18), border_radius=3)
            pygame.draw.rect(surf, (210, 40, 40),
                             (cx - 3, cy - 7 + offset, 6, 14))
            pygame.draw.rect(surf, (210, 40, 40),
                             (cx - 9, cy - 1 + offset, 18, 4))
        elif self.kind == P_AMMO:
            pygame.draw.rect(surf, (140, 100, 40),
                             (cx - 12, cy - 8 + offset, 24, 14), border_radius=2)
            pygame.draw.rect(surf, (200, 170, 80),
                             (cx - 12, cy - 8 + offset, 24, 5))
            draw_text(surf, "AMMO", (cx, cy + offset), size=10,
                      color=(0, 0, 0), bold=True, center=True, shadow=False)
        elif self.kind == P_KEY:
            pygame.draw.circle(surf, (255, 215, 0), (cx - 4, cy), 7, 3)
            pygame.draw.rect(surf, (255, 215, 0), (cx, cy - 2, 14, 4))
            pygame.draw.rect(surf, (255, 215, 0), (cx + 8, cy + 2, 4, 4))


# ============================================================
# Solid object (collidable rect, optionally drawable as house/wall/etc.)
# ============================================================
class Solid:
    def __init__(self, rect: pygame.Rect, kind: str = "wall", color=None, height=0):
        self.rect = rect
        self.kind = kind   # wall, house, fence, container, car, drum, tree, crate
        self.color = color
        self.height = height
        self.hp = 0        # 0 = indestructible
        self.alive = True
        self.sprite: pygame.Surface | None = None
        self.aux = {}      # any extra data

    def draw(self, surf, cam):
        if not self.alive: return
        r = cam.apply_rect(self.rect)
        k = self.kind
        if k == "wall":
            pygame.draw.rect(surf, self.color or (90, 90, 90), r)
            pygame.draw.rect(surf, BLACK, r, 2)
        elif k == "house":
            self._draw_house(surf, r)
        elif k == "fence":
            pygame.draw.rect(surf, (170, 130, 70), r)
            for x in range(r.left, r.right, 8):
                pygame.draw.line(surf, (120, 80, 40),
                                 (x, r.top), (x, r.bottom), 1)
            pygame.draw.rect(surf, BLACK, r, 1)
        elif k == "container":
            pygame.draw.rect(surf, self.color or (190, 60, 40), r)
            pygame.draw.rect(surf, BLACK, r, 3)
            for y in range(r.top + 8, r.bottom, 16):
                pygame.draw.line(surf, (0, 0, 0), (r.left, y), (r.right, y), 1)
        elif k == "car":
            self._draw_car(surf, r)
        elif k == "drum":
            cx, cy = r.center
            pygame.draw.ellipse(surf, (160, 60, 30), r)
            pygame.draw.ellipse(surf, BLACK, r, 2)
            pygame.draw.line(surf, (90, 30, 10), (r.left + 4, cy - 4),
                             (r.right - 4, cy - 4), 2)
            pygame.draw.line(surf, (90, 30, 10), (r.left + 4, cy + 4),
                             (r.right - 4, cy + 4), 2)
        elif k == "tree":
            cx, cy = r.center
            # trunk
            pygame.draw.rect(surf, DARK_BROWN, (cx - 4, cy + 4, 8, 14))
            pygame.draw.circle(surf, DARK_GREEN, (cx, cy - 2), r.width // 2 + 2)
            pygame.draw.circle(surf, (90, 150, 70), (cx - 4, cy - 6), r.width // 3)
        elif k == "crate":
            pygame.draw.rect(surf, (155, 110, 60), r)
            pygame.draw.rect(surf, (90, 60, 30), r, 3)
            pygame.draw.line(surf, (90, 60, 30), r.topleft, r.bottomright, 2)
            pygame.draw.line(surf, (90, 60, 30), r.topright, r.bottomleft, 2)
        elif k == "machine":
            pygame.draw.rect(surf, (90, 90, 100), r)
            pygame.draw.rect(surf, (140, 140, 150), r.inflate(-10, -10))
            pygame.draw.circle(surf, (60, 60, 70),
                               r.center, min(r.w, r.h) // 4)
            pygame.draw.rect(surf, BLACK, r, 2)
        elif k == "rubble":
            pygame.draw.rect(surf, (120, 110, 100), r)
            pygame.draw.line(surf, (60, 55, 50), r.topleft, r.bottomright, 2)
            pygame.draw.line(surf, (60, 55, 50), r.topright, r.bottomleft, 2)
        elif k == "sprite":
            if self.sprite:
                surf.blit(self.sprite, r)
        elif k == "boss_gate":
            pygame.draw.rect(surf, (60, 60, 70), r)
            pygame.draw.rect(surf, (200, 200, 200), r, 4)
            # Bars
            for x in range(r.left + 8, r.right, 12):
                pygame.draw.line(surf, (150, 150, 160), (x, r.top), (x, r.bottom), 3)
            # Skull icon or caution
            pygame.draw.circle(surf, (200, 30, 30), r.center, 8)
        elif k == "puppy":
            self._draw_puppy(surf, r)
        elif k == "mother_dog":
            self._draw_mother_dog(surf, r)
        else:
            pygame.draw.rect(surf, self.color or (90, 90, 90), r)

    def _draw_house(self, surf, r):
        wall_color = self.aux.get("wall", WALL_TAN)
        roof_color = self.aux.get("roof", ROOF_RED)
        # wall body
        pygame.draw.rect(surf, wall_color, r)
        # roof overhang at top
        roof_h = max(14, r.height // 5)
        roof_rect = pygame.Rect(r.left - 4, r.top - 6, r.width + 8, roof_h)
        pygame.draw.rect(surf, roof_color, roof_rect)
        # roof tiles
        for x in range(roof_rect.left + 4, roof_rect.right, 16):
            pygame.draw.line(surf, (0, 0, 0, 40),
                             (x, roof_rect.top + 2),
                             (x, roof_rect.bottom - 2), 1)
        # door
        door_w = 22
        door_h = 36
        door_rect = pygame.Rect(r.centerx - door_w // 2,
                                r.bottom - door_h - 4,
                                door_w, door_h)
        pygame.draw.rect(surf, DARK_BROWN, door_rect)
        pygame.draw.rect(surf, BLACK, door_rect, 2)
        pygame.draw.circle(surf, (240, 200, 50),
                           (door_rect.right - 5, door_rect.centery), 2)
        # windows
        win_w = 22
        win_h = 22
        for wx in (r.left + 18, r.right - 18 - win_w):
            wr = pygame.Rect(wx, r.top + 18, win_w, win_h)
            pygame.draw.rect(surf, (140, 200, 230), wr)
            pygame.draw.rect(surf, BLACK, wr, 2)
            pygame.draw.line(surf, BLACK,
                             (wr.centerx, wr.top),
                             (wr.centerx, wr.bottom), 1)
            pygame.draw.line(surf, BLACK,
                             (wr.left, wr.centery),
                             (wr.right, wr.centery), 1)
        # outline
        pygame.draw.rect(surf, BLACK, r, 2)
        pygame.draw.rect(surf, BLACK, roof_rect, 2)

    def _draw_car(self, surf, r):
        body = self.color or (180, 60, 60)
        pygame.draw.rect(surf, body, r, border_radius=6)
        pygame.draw.rect(surf, BLACK, r, 2, border_radius=6)
        # windows
        inner = r.inflate(-12, -16)
        pygame.draw.rect(surf, (90, 130, 170), inner, border_radius=3)
        pygame.draw.rect(surf, BLACK, inner, 1, border_radius=3)
        # wheels
        rw = 8
        for cx, cy in (
            (r.left + 6, r.top - 2),
            (r.right - 6, r.top - 2),
            (r.left + 6, r.bottom + 2),
            (r.right - 6, r.bottom + 2),
        ):
            pygame.draw.circle(surf, BLACK, (cx, cy), rw // 2 + 2)

    def _draw_puppy(self, surf, r):
        # cage
        pygame.draw.rect(surf, (180, 180, 180), r, 2)
        for x in range(r.left, r.right, 8):
            pygame.draw.line(surf, (150, 150, 150), (x, r.top), (x, r.bottom), 1)
        # puppy (small brown blob)
        cx, cy = r.center
        pygame.draw.circle(surf, (160, 110, 60), (cx, cy + 4), 6) # body
        pygame.draw.circle(surf, (160, 110, 60), (cx, cy - 2), 4) # head
        # ears
        pygame.draw.circle(surf, (120, 80, 40), (cx - 4, cy - 5), 2)
        pygame.draw.circle(surf, (120, 80, 40), (cx + 4, cy - 5), 2)

    def _draw_mother_dog(self, surf, r):
        # larger cage
        pygame.draw.rect(surf, (200, 200, 200), r, 3)
        for x in range(r.left, r.right, 12):
            pygame.draw.line(surf, (170, 170, 170), (x, r.top), (x, r.bottom), 2)
        # mother dog (larger brown blob)
        cx, cy = r.center
        pygame.draw.circle(surf, (160, 110, 60), (cx, cy + 8), 14) # body
        pygame.draw.circle(surf, (160, 110, 60), (cx, cy - 6), 10) # head
        # ears
        pygame.draw.circle(surf, (120, 80, 40), (cx - 8, cy - 12), 5)
        pygame.draw.circle(surf, (120, 80, 40), (cx + 8, cy - 12), 5)


# ============================================================
# Decals (purely visual, drawn under entities)
# ============================================================
class Decal:
    def __init__(self, rect, kind, color=None):
        self.rect = rect
        self.kind = kind
        self.color = color

    def draw(self, surf, cam):
        r = cam.apply_rect(self.rect)
        k = self.kind
        if k == "flower":
            cx, cy = r.center
            pygame.draw.circle(surf, self.color or (240, 80, 80), (cx, cy), 3)
            pygame.draw.circle(surf, (255, 240, 100), (cx, cy), 1)
        elif k == "puddle":
            pygame.draw.ellipse(surf, (60, 90, 120, 180), r)
        elif k == "crack":
            pygame.draw.line(surf, (60, 60, 60),
                             r.topleft, r.bottomright, 1)
            pygame.draw.line(surf, (60, 60, 60),
                             (r.centerx, r.top), (r.right, r.bottom), 1)
        elif k == "blood":
            pygame.draw.circle(surf, (110, 20, 20), r.center, r.width // 2)
            pygame.draw.circle(surf, (160, 30, 30), r.center, r.width // 3)


# ============================================================
# World container
# ============================================================
class World:
    def __init__(self, w_tiles: int, h_tiles: int, default_tile: int = T_GRASS):
        self.w = w_tiles
        self.h = h_tiles
        self.tile_size = TILE
        self.tiles = [[default_tile] * w_tiles for _ in range(h_tiles)]
        self.solids: list[Solid] = []
        self.pickups: list[Pickup] = []
        self.decals: list[Decal] = []
        self.spawn = Vec(0, 0)
        self.exit_rect: pygame.Rect | None = None
        self.exit_locked = True
        self.shop_rect: pygame.Rect | None = None
        self.dog_rect: pygame.Rect | None = None
        self.boss_gate_rect: pygame.Rect | None = None
        self.boss_gate_active = True
        self.boss_dialog_triggered = False
        self._dirty = True

    def clear(self):
        """Reset all dynamic entities and markers for a fresh level."""
        self.solids = []
        self.pickups = []
        self.decals = []
        self.exit_rect = None
        self.exit_locked = True
        self.shop_rect = None
        self.dog_rect = None
        self.boss_gate_rect = None
        self.boss_gate_active = True
        self.boss_dialog_triggered = False
        self._dirty = True

    # ---------- map editing helpers ----------
    def fill_rect_tiles(self, x, y, w, h, t):
        for j in range(y, y + h):
            for i in range(x, x + w):
                if 0 <= i < self.w and 0 <= j < self.h:
                    self.tiles[j][i] = t
        self._dirty = True

    def fill_pixel_rect(self, px_rect: pygame.Rect, t: int):
        x = px_rect.left // TILE
        y = px_rect.top // TILE
        w = px_rect.width // TILE
        h = px_rect.height // TILE
        self.fill_rect_tiles(x, y, w, h, t)

    def set_tile(self, x, y, t):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.tiles[y][x] = t
            self._dirty = True

    def add_solid(self, s: Solid):
        self.solids.append(s)

    def add_pickup(self, p: Pickup):
        self.pickups.append(p)

    def add_decal(self, d: Decal):
        self.decals.append(d)

    def get_walkable_grid(self, ignore_boss_gates=False):
        if ignore_boss_gates:
            grid = [[True] * self.w for _ in range(self.h)]
            for s in self.solids:
                kinds_to_ignore = ("decoration", "boss_gate_trigger", "dialogue_trigger", "boss_gate")
                if s.alive and s.kind not in kinds_to_ignore:
                    x1 = max(0, s.rect.left // TILE)
                    y1 = max(0, s.rect.top // TILE)
                    x2 = min(self.w - 1, s.rect.right // TILE)
                    y2 = min(self.h - 1, s.rect.bottom // TILE)
                    for y in range(y1, y2 + 1):
                        for x in range(x1, x2 + 1):
                            grid[y][x] = False
            return grid

        if not hasattr(self, "_walkable_grid") or self._dirty:
            self._walkable_grid = [[True] * self.w for _ in range(self.h)]
            for s in self.solids:
                if s.alive and s.kind not in ("decoration", "boss_gate_trigger", "dialogue_trigger"):
                    x1 = max(0, s.rect.left // TILE)
                    y1 = max(0, s.rect.top // TILE)
                    x2 = min(self.w - 1, s.rect.right // TILE)
                    y2 = min(self.h - 1, s.rect.bottom // TILE)
                    for y in range(y1, y2 + 1):
                        for x in range(x1, x2 + 1):
                            self._walkable_grid[y][x] = False
            self._dirty = False
        return self._walkable_grid

    # ---------- collision ----------
    def collides(self, rect: pygame.Rect) -> bool:
        for s in self.solids:
            if s.alive and s.kind not in ("decoration",) and s.rect.colliderect(rect):
                return True
        return False

    def hit_solid(self, point: Vec) -> Solid | None:
        for s in self.solids:
            if s.alive and s.kind != "decoration" and s.rect.collidepoint(point):
                return s
        return None

    # ---------- size ----------
    def pixel_size(self):
        return self.w * TILE, self.h * TILE

    # ---------- drawing ----------
    def _is_road_center_h(self, i, j):
        if self.tiles[j][i] not in (T_ROAD_H, T_ROAD_X):
            return False
        up = 0
        k = j - 1
        while k >= 0 and self.tiles[k][i] in (T_ROAD_H, T_ROAD_X):
            up += 1
            k -= 1
        dn = 0
        k = j + 1
        while k < self.h and self.tiles[k][i] in (T_ROAD_H, T_ROAD_X):
            dn += 1
            k += 1
        return up == dn

    def _is_road_center_v(self, i, j):
        if self.tiles[j][i] not in (T_ROAD_V, T_ROAD_X):
            return False
        left = 0
        k = i - 1
        while k >= 0 and self.tiles[j][k] in (T_ROAD_V, T_ROAD_X):
            left += 1
            k -= 1
        right = 0
        k = i + 1
        while k < self.w and self.tiles[j][k] in (T_ROAD_V, T_ROAD_X):
            right += 1
            k += 1
        return left == right

    def _build_bg(self):
        w, h = self.pixel_size()
        self._bg_surface = pygame.Surface((w, h)).convert()
        bg = self._bg_surface
        for j in range(self.h):
            for i in range(self.w):
                t = self.tiles[j][i]
                col = TILE_COLORS.get(t, GRASS)
                # slight noise
                noise = ((i * 73856093) ^ (j * 19349663)) & 15
                c = (max(0, col[0] - noise // 2 + 4),
                     max(0, col[1] - noise // 2 + 4),
                     max(0, col[2] - noise // 2 + 4))
                pygame.draw.rect(bg, c, (i * TILE, j * TILE, TILE, TILE))

        # paint road centerline dashes only on the true center row/col
        for j in range(self.h):
                if t == T_GRASS and rnd.random() < 0.05:
                    cx = i * TILE + rnd.randint(4, TILE - 4)
                    cy = j * TILE + rnd.randint(4, TILE - 4)
                    pygame.draw.line(bg, GRASS_DARK, (cx, cy), (cx, cy - 3), 1)
                    pygame.draw.line(bg, GRASS_DARK, (cx, cy), (cx - 2, cy - 2), 1)
                    pygame.draw.line(bg, GRASS_DARK, (cx, cy), (cx + 2, cy - 2), 1)
                if t == T_ASH and rnd.random() < 0.07:
                    cx = i * TILE + rnd.randint(4, TILE - 4)
                    cy = j * TILE + rnd.randint(4, TILE - 4)
                    pygame.draw.circle(bg, (35, 35, 38), (cx, cy), 1)
        self._dirty = False

    def draw_bg(self, surf, cam):
        # Calculate visible tile range
        start_x = max(0, int(cam.offset.x // TILE))
        end_x = min(self.w, int((cam.offset.x + SCREEN_WIDTH) // TILE) + 1)
        start_y = max(0, int(cam.offset.y // TILE))
        end_y = min(self.h, int((cam.offset.y + SCREEN_HEIGHT) // TILE) + 1)

        off_x = -int(cam.offset.x) + int(cam.shake_offset.x)
        off_y = -int(cam.offset.y) + int(cam.shake_offset.y)

        # Draw base tiles
        for j in range(start_y, end_y):
            for i in range(start_x, end_x):
                t = self.tiles[j][i]
                color = TILE_COLORS.get(t, GRASS)
                pygame.draw.rect(surf, color, (i * TILE + off_x, j * TILE + off_y, TILE, TILE))
                
                # Draw simple details in real-time
                if t == T_ROAD_H:
                    cy = j * TILE + TILE // 2 + off_y
                    pygame.draw.rect(surf, ROAD_LINE, (i * TILE + off_x + 10, cy - 1, TILE - 20, 2))
                elif t == T_ROAD_V:
                    cx = i * TILE + TILE // 2 + off_x
                    pygame.draw.rect(surf, ROAD_LINE, (cx - 1, j * TILE + off_y + 10, 2, TILE - 20))
                elif t == T_ASH:
                    # Subtle ash dots
                    seed = (i * 12345 + j * 67890) % 100
                    if seed < 10:
                        pygame.draw.circle(surf, (35, 35, 38), (i * TILE + off_x + 20, j * TILE + off_y + 20), 1)

        # decals on top of bg (culled)
        view_rect = pygame.Rect(cam.offset.x - 50, cam.offset.y - 50, SCREEN_WIDTH + 100, SCREEN_HEIGHT + 100)
        for d in self.decals:
            if view_rect.colliderect(d.rect):
                d.draw(surf, cam)

    def draw_solids(self, surf, cam):
        for s in self.solids:
            if s.alive:
                s.draw(surf, cam)

    def draw_pickups(self, surf, cam):
        for p in self.pickups:
            if p.alive:
                p.draw(surf, cam)

    def draw_exit_marker(self, surf, cam, t):
        if self.exit_rect is None:
            return
        r = cam.apply_rect(self.exit_rect)
        color = (200, 200, 200) if self.exit_locked else (90, 220, 100)
        pygame.draw.rect(surf, color, r, 4, border_radius=4)
        flash = (math.sin(t * 4) + 1) / 2
        text_col = (40, 40, 40) if self.exit_locked else (10, 60, 20)
        msg = "LOCKED" if self.exit_locked else "EXIT >>"
        from utils import draw_text
        draw_text(surf, msg, (r.centerx, r.centery), size=20,
                  color=text_col, bold=True, center=True)
        if not self.exit_locked:
            arrow_size = 18 + int(flash * 6)
            pts = [(r.right + 10, r.centery),
                   (r.right + 10 + arrow_size, r.centery - arrow_size // 2),
                   (r.right + 10 + arrow_size, r.centery + arrow_size // 2)]
            pygame.draw.polygon(surf, (90, 220, 100), pts)
