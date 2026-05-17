"""Level definitions — 4 beautiful hand-designed maps.

Each level has its own builder function returning (world, enemies, label,
biome). Levels are designed to be played left-to-right (exit on the right
edge), with strategic landmarks: houses, gas station shop, industrial
warehouses, boss arena.
"""
from __future__ import annotations
import random
import pygame
from utils import Vec
from world import (
    World, Solid, Pickup, Decal,
    T_GRASS, T_ROAD_H, T_ROAD_V, T_ROAD_X, T_DIRT, T_CONCRETE, T_SAND,
    T_GRASS_DARK, T_FLOOR_WOOD, T_FLOOR_TILE, T_ASH, T_WATER,
    P_GOLD, P_MEDKIT, P_AMMO, P_KEY,
)
from enemies import Enemy
from settings import TILE, SPRITES


# ============================================================
# Helpers
# ============================================================
def _add_house(world, x, y, w, h, wall=None, roof=None):
    rect = pygame.Rect(x, y, w, h)
    s = Solid(rect, "house")
    if wall is not None:
        s.aux["wall"] = wall
    if roof is not None:
        s.aux["roof"] = roof
    world.add_solid(s)
    return s


def _add_fence(world, x, y, w, h):
    world.add_solid(Solid(pygame.Rect(x, y, w, h), "fence"))


def _add_tree(world, cx, cy, r=24):
    world.add_solid(Solid(pygame.Rect(cx - r, cy - r, 2 * r, 2 * r), "tree"))


def _add_car(world, x, y, w=64, h=36, color=None):
    s = Solid(pygame.Rect(x, y, w, h), "car", color=color)
    world.add_solid(s)


def _add_drum(world, cx, cy):
    world.add_solid(Solid(pygame.Rect(cx - 16, cy - 16, 32, 32), "drum"))


def _add_container(world, x, y, w, h, color=None):
    world.add_solid(Solid(pygame.Rect(x, y, w, h), "container", color=color))


def _add_sprite_solid(world, x, y, w, h, fname):
    path = SPRITES / fname
    rect = pygame.Rect(x, y, w, h)
    s = Solid(rect, "sprite")
    if path.exists():
        try:
            img = pygame.image.load(str(path)).convert()
            # Auto-detect background color (usually at 0,0)
            bg_color = img.get_at((0, 0))
            # If color is close to white or black, treat as background
            if sum(bg_color[:3]) > 700 or sum(bg_color[:3]) < 25:
                img.set_colorkey(bg_color)
            img = img.convert_alpha()
            s.sprite = pygame.transform.smoothscale(img, (w, h))
        except Exception as e:
            print(f"DEBUG: Failed to load sprite {fname}: {e}")
    world.add_solid(s)
    return s


def _scatter_gold(world, rect: pygame.Rect, count: int, amount=15):
    for _ in range(count):
        x = random.randint(rect.left + 20, rect.right - 20)
        y = random.randint(rect.top + 20, rect.bottom - 20)
        world.add_pickup(Pickup(Vec(x, y), P_GOLD, amount))


# ============================================================
# LEVEL 1 — Khu Dân Cư (Suburban)
# Beautiful suburban layout: 2 parallel horizontal roads with a vertical
# cross road, two rows of houses with front gardens, scattered trees,
# parked cars, exit on the right.
# ============================================================
def build_level1(world=None):
    W, H = 90, 50
    if world is None:
        world = World(W, H, default_tile=T_GRASS)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_GRASS] * W for _ in range(H)]
        world._dirty = True
    # Sidewalks/concrete around houses
    # Horizontal main road (3 tiles tall) at y=12 and y=36
    for y in (11, 12, 13):
        for x in range(W):
            world.set_tile(x, y, T_ROAD_H)
    for y in (35, 36, 37):
        for x in range(W):
            world.set_tile(x, y, T_ROAD_H)
    # Vertical connector road at x=44
    for x in (43, 44, 45):
        for y in range(H):
            world.set_tile(x, y, T_ROAD_V)
    # Intersections
    for y in (11, 12, 13, 35, 36, 37):
        for x in (43, 44, 45):
            world.set_tile(x, y, T_ROAD_X)
    # Sidewalks (concrete) flanking roads
    for x in range(W):
        world.set_tile(x, 10, T_CONCRETE)
        world.set_tile(x, 14, T_CONCRETE)
        world.set_tile(x, 34, T_CONCRETE)
        world.set_tile(x, 38, T_CONCRETE)
    for y in range(H):
        for x in (42, 46):
            world.set_tile(x, y, T_CONCRETE)

    # Front gardens darker grass
    for x in range(W):
        for y in (15, 16, 32, 33):
            world.set_tile(x, y, T_GRASS_DARK)
        for y in (8, 9, 39, 40):
            world.set_tile(x, y, T_GRASS_DARK)

    # House blocks: 6 houses in upper row, 6 in lower row, skipping connector
    house_w, house_h = 90, 100
    upper_y = 6 * TILE - 40
    lower_y = 38 * TILE
    house_positions = []
    for i, gx in enumerate([3, 13, 23, 33, 53, 63, 73, 83]):
        x = gx * TILE
        house_positions.append((x, upper_y))
        
        # Replace the 2nd and 6th houses with Pho restaurants
        if i == 1 or i == 5:
            _add_sprite_solid(world, x, upper_y - 20, 160, 140, "pho_house.png")
            continue
            
        # roof varying
        roof = (165, 60, 50) if i % 2 == 0 else (70, 100, 160)
        wall = (245, 240, 220) if i % 3 == 0 else (215, 195, 160)
        _add_house(world, x, upper_y, house_w, house_h, wall=wall, roof=roof)
        # tree in front yard
        _add_tree(world, x + house_w // 2, upper_y - 30, r=20)
    for i, gx in enumerate([3, 13, 23, 33, 53, 63, 73, 83]):
        x = gx * TILE
        roof = (70, 100, 160) if i % 2 == 0 else (165, 60, 50)
        wall = (210, 180, 140) if i % 2 == 0 else (245, 240, 220)
        _add_house(world, x, lower_y, house_w, house_h, wall=wall, roof=roof)
        house_positions.append((x, lower_y))
        _add_tree(world, x + house_w // 2, lower_y + house_h + 30, r=20)

    # Fences along gardens (between houses)
    for x in range(0, W * TILE, 36):
        pass  # skip for cleanliness

    # Parked cars on roadside
    car_colors = [(200, 50, 50), (60, 80, 200), (220, 200, 60),
                  (40, 160, 60), (50, 50, 50)]
    for i, gx in enumerate(range(6, W - 6, 14)):
        _add_car(world, gx * TILE, 9 * TILE + 8,
                 color=car_colors[i % len(car_colors)])
        _add_car(world, gx * TILE + 70, 38 * TILE + 8,
                 color=car_colors[(i + 2) % len(car_colors)])

    # Drums for shooting fun
    _add_drum(world, 64 * TILE, 24 * TILE)

    # Decorative flowers
    for _ in range(80):
        x = random.randint(0, W * TILE - 10)
        y = random.randint(0, H * TILE - 10)
        # avoid roads
        ti = x // TILE
        tj = y // TILE
        if not (0 <= ti < W and 0 <= tj < H):
            continue
        if world.tiles[tj][ti] in (T_GRASS, T_GRASS_DARK):
            world.add_decal(Decal(pygame.Rect(x, y, 6, 6), "flower",
                                  random.choice([(240, 80, 80),
                                                 (250, 200, 60),
                                                 (180, 100, 240),
                                                 (255, 255, 255)])))

    # Pickups
    _scatter_gold(world, pygame.Rect(2 * TILE, 16 * TILE,
                                     40 * TILE, 16 * TILE), 6, 10)
    _scatter_gold(world, pygame.Rect(46 * TILE, 16 * TILE,
                                     40 * TILE, 16 * TILE), 8, 12)
    world.add_pickup(Pickup(Vec(28 * TILE, 24 * TILE), P_MEDKIT))
    world.add_pickup(Pickup(Vec(72 * TILE, 22 * TILE), P_MEDKIT))

    # Spawn at left
    # Spawn area: suburb start
    world.spawn = Vec(8 * TILE, 24 * TILE)

    # Road passing through spawn
    for x in range(W):
        for y in (23, 24, 25):
            world.set_tile(x, y, T_ROAD_H)

    # Neighborhood at the start
    for x in (5 * TILE, 12 * TILE, 19 * TILE):
        _add_house(world, x, 18 * TILE, 90, 100)
        _add_tree(world, x + 45, 20 * TILE, r=20)

    # Exit at right edge (small zone)
    world.exit_rect = pygame.Rect((W - 4) * TILE, 22 * TILE,
                                  3 * TILE, 6 * TILE)
    world.exit_locked = True  # unlock after boss

    # Enemies — spread out, ramping right-to-left, kept away from spawn
    enemies = []
    for i in range(6):
        x = random.randint(14 * TILE, 36 * TILE)
        y = random.randint(16 * TILE, 32 * TILE)
        kind = "zombie" if random.random() < 0.7 else "thief_knife"
        enemies.append(Enemy(kind, Vec(x, y)))
    for i in range(7):
        x = random.randint(48 * TILE, 76 * TILE)
        y = random.randint(16 * TILE, 32 * TILE)
        kind = "thief_knife" if random.random() < 0.5 else "zombie"
        enemies.append(Enemy(kind, Vec(x, y)))
    # Mini-boss arena near exit
    arena_x = (W - 12) * TILE
    arena_y = 20 * TILE
    arena_w = 10 * TILE
    arena_h = 8 * TILE
    # Walls for arena
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y, arena_w, 20))) # top
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y + arena_h, arena_w, 20))) # bottom
    world.solids.append(Solid(pygame.Rect(arena_x + arena_w, arena_y, 20, arena_h + 20))) # right
    # Gate on the left
    gate_rect = pygame.Rect(arena_x, arena_y + 20, 20, arena_h - 20)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    
    # Puppy inside arena (behind boss)
    dog_rect = pygame.Rect(arena_x + arena_w - 60, arena_y + arena_h // 2 - 20, 40, 40)
    world.solids.append(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    boss_pos = Vec((W - 6) * TILE, arena_y + arena_h // 2)
    boss = Enemy("boss1", boss_pos)
    enemies.append(boss)
    # Two guards near boss
    enemies.append(Enemy("thief_knife", boss_pos + Vec(-60, -40)))
    enemies.append(Enemy("thief_knife", boss_pos + Vec(-60, 40)))

    return world, enemies, "Level 1 — Khu Dân Cư", "suburban"


# ============================================================
# LEVEL 2 — Phố Cổ (Downtown) with gas station shop
# Wider concrete streets, narrow alleys, rubble, abandoned cars and a
# gas station building where the shop is located.
# ============================================================
def build_level2(world=None):
    W, H = 100, 55
    if world is None:
        world = World(W, H, default_tile=T_CONCRETE)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_CONCRETE] * W for _ in range(H)]
        world._dirty = True
    # Main street horizontal (5 tiles tall, centered on y=22)
    for y in range(20, 25):
        for x in range(W):
            world.set_tile(x, y, T_ROAD_H)
    # Two perpendicular alleys (5 wide)
    for x in range(28, 33):
        for y in range(H):
            world.set_tile(x, y, T_ROAD_V)
    for x in range(64, 69):
        for y in range(H):
            world.set_tile(x, y, T_ROAD_V)
    for x in range(28, 33):
        for y in range(20, 25):
            world.set_tile(x, y, T_ROAD_X)
    for x in range(64, 69):
        for y in range(20, 25):
            world.set_tile(x, y, T_ROAD_X)
    # Sidewalk concrete (default already concrete)
    # Some dirt patches for visual variety
    for _ in range(40):
        cx = random.randint(0, W - 4)
        cy = random.randint(0, H - 4)
        if world.tiles[cy][cx] == T_CONCRETE:
            for dx in range(3):
                for dy in range(3):
                    if 0 <= cx + dx < W and 0 <= cy + dy < H:
                        if random.random() < 0.6:
                            world.tiles[cy + dy][cx + dx] = T_DIRT

    # Abandoned ruined buildings (multi-block, irregular)
    def add_ruin(gx, gy, w, h, wall=(170, 150, 110), roof=(110, 70, 40)):
        _add_house(world, gx * TILE, gy * TILE, w * TILE, h * TILE,
                   wall=wall, roof=roof)

    # Top row buildings
    add_ruin(2, 4, 10, 13, wall=(180, 150, 110), roof=(120, 60, 40))
    add_ruin(13, 6, 6, 11, wall=(160, 140, 110), roof=(140, 60, 50))
    add_ruin(20, 4, 7, 13, wall=(195, 175, 140), roof=(70, 60, 130))
    add_ruin(34, 6, 11, 11, wall=(200, 180, 150), roof=(140, 80, 60))
    add_ruin(46, 4, 9, 13, wall=(160, 130, 100), roof=(70, 50, 130))
    add_ruin(56, 4, 7, 13, wall=(220, 200, 170), roof=(120, 70, 60))
    # Gas station building (shop)
    shop_x, shop_y = 70, 6
    shop_w, shop_h = 14, 9
    _add_house(world, shop_x * TILE, shop_y * TILE,
               shop_w * TILE, shop_h * TILE,
               wall=(245, 240, 220), roof=(60, 130, 80))
    world.shop_rect = pygame.Rect((shop_x + 5) * TILE, (shop_y + shop_h + 1) * TILE,
                                  4 * TILE, 2 * TILE)
    # Pump pad concrete
    for x in range(shop_x + 1, shop_x + shop_w - 1):
        for y in range(shop_y + shop_h, shop_y + shop_h + 3):
            world.set_tile(x, y, T_CONCRETE)
    # Pumps (drums in front)
    _add_drum(world, (shop_x + 3) * TILE + TILE // 2,
              (shop_y + shop_h + 1) * TILE)
    _add_drum(world, (shop_x + 8) * TILE + TILE // 2,
              (shop_y + shop_h + 1) * TILE)
    _add_drum(world, (shop_x + 11) * TILE + TILE // 2,
              (shop_y + shop_h + 1) * TILE)

    add_ruin(86, 4, 10, 13, wall=(140, 120, 90), roof=(120, 60, 40))

    # Bottom row buildings
    add_ruin(2, 28, 7, 15, wall=(180, 150, 110), roof=(120, 60, 40))
    add_ruin(10, 30, 9, 13, wall=(195, 175, 140), roof=(70, 60, 130))
    add_ruin(20, 28, 7, 15, wall=(160, 140, 110), roof=(140, 60, 50))
    add_ruin(34, 30, 11, 13, wall=(200, 180, 150), roof=(140, 80, 60))
    add_ruin(46, 28, 7, 15, wall=(220, 200, 170), roof=(70, 60, 130))
    add_ruin(54, 30, 9, 13, wall=(160, 130, 100), roof=(120, 70, 60))
    add_ruin(70, 28, 8, 15, wall=(195, 175, 140), roof=(140, 70, 50))
    add_ruin(79, 30, 6, 13, wall=(220, 200, 170), roof=(70, 60, 130))
    add_ruin(86, 28, 10, 15, wall=(160, 130, 100), roof=(120, 70, 50))

    # Rubble piles and crashed cars on the road
    for x in (10, 22, 52, 60, 76, 90):
        _add_car(world, x * TILE, 20 * TILE + 12,
                 color=random.choice([(80, 80, 80), (160, 60, 50),
                                      (60, 80, 160)]))
    for x in (38, 48, 78):
        rect = pygame.Rect(x * TILE, 22 * TILE + 8, 64, 36)
        world.add_solid(Solid(rect, "rubble"))
    for x in (16, 42, 72):
        world.add_solid(Solid(pygame.Rect(x * TILE, 23 * TILE,
                                          40, 24), "rubble"))
    
    # Added: Banh Mi carts on the sidewalk (some near spawn)
    _add_sprite_solid(world, 5 * TILE, 24 * TILE + 10, 80, 80, "banh_mi.png")
    _add_sprite_solid(world, 15 * TILE, 24 * TILE + 10, 80, 80, "banh_mi.png")
    _add_sprite_solid(world, 40 * TILE, 19 * TILE, 80, 80, "banh_mi.png")

    # decorative cracks
    for _ in range(80):
        x = random.randint(0, W * TILE - 6)
        y = random.randint(20 * TILE, 26 * TILE)
        world.add_decal(Decal(pygame.Rect(x, y, 12, 12), "crack"))
    for _ in range(30):
        x = random.randint(0, W * TILE - 12)
        y = random.randint(0, H * TILE - 12)
        ti = x // TILE
        tj = y // TILE
        if 0 <= ti < W and 0 <= tj < H and world.tiles[tj][ti] != T_ROAD_H:
            world.add_decal(Decal(pygame.Rect(x, y, 16, 16), "puddle"))

    # Pickups
    _scatter_gold(world, pygame.Rect(2 * TILE, 18 * TILE,
                                     45 * TILE, 16 * TILE), 10, 15)
    _scatter_gold(world, pygame.Rect(48 * TILE, 18 * TILE,
                                     45 * TILE, 16 * TILE), 12, 18)
    world.add_pickup(Pickup(Vec(32 * TILE, 24 * TILE), P_MEDKIT))
    world.add_pickup(Pickup(Vec(67 * TILE, 24 * TILE), P_MEDKIT))
    world.add_pickup(Pickup(Vec(15 * TILE, 23 * TILE), P_AMMO))
    world.add_pickup(Pickup(Vec(58 * TILE, 23 * TILE), P_AMMO))
    world.add_pickup(Pickup(Vec(82 * TILE, 23 * TILE), P_AMMO))

    world.spawn = Vec(2 * TILE, 22 * TILE + 16)
    world.exit_rect = pygame.Rect((W - 4) * TILE, 22 * TILE,
                                  3 * TILE, 5 * TILE)
    world.exit_locked = True

    enemies = []
    # zombies in groups
    for _ in range(10):
        x = random.randint(6 * TILE, 40 * TILE)
        y = random.randint(18 * TILE, 28 * TILE)
        kind = "zombie_fast" if random.random() < 0.6 else "zombie"
        enemies.append(Enemy(kind, Vec(x, y)))
    # thieves with pistols mid-map
    for _ in range(6):
        x = random.randint(28 * TILE, 60 * TILE)
        y = random.randint(18 * TILE, 28 * TILE)
        enemies.append(Enemy("thief_pistol", Vec(x, y)))
    # wild dogs around alleys
    for _ in range(5):
        x = random.randint(28 * TILE, 70 * TILE)
        y = random.choice([random.randint(2 * TILE, 18 * TILE),
                           random.randint(28 * TILE, 44 * TILE)])
        enemies.append(Enemy("wild_dog", Vec(x, y)))
    # more thieves near boss area
    for _ in range(5):
        x = random.randint(72 * TILE, 92 * TILE)
        y = random.randint(18 * TILE, 28 * TILE)
        enemies.append(Enemy("thief_pistol", Vec(x, y)))

    # Boss Arena
    arena_x = (W - 14) * TILE
    arena_y = 18 * TILE
    arena_w = 12 * TILE
    arena_h = 10 * TILE
    # Walls
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y, arena_w, 20)))
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y + arena_h, arena_w, 20)))
    world.solids.append(Solid(pygame.Rect(arena_x + arena_w, arena_y, 20, arena_h + 20)))
    # Gate
    gate_rect = pygame.Rect(arena_x, arena_y + 20, 20, arena_h - 20)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    # Puppy
    dog_rect = pygame.Rect(arena_x + arena_w - 60, arena_y + arena_h // 2 - 20, 40, 40)
    world.solids.append(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    boss = Enemy("boss2", Vec(arena_x + arena_w // 2, arena_y + arena_h // 2))
    enemies.append(boss)

    return world, enemies, "Level 2 — Phố Cổ Bỏ Hoang", "downtown"


# ============================================================
# LEVEL 3 — Khu Công Nghiệp (Industrial)
# Dark concrete/ash floor with stacked containers and warehouses, plus a
# warehouse shop and rooftop sniper perches.
# ============================================================
def build_level3(world=None):
    W, H = 100, 56
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    # Side roads at top and bottom
    for y in range(2, 6):
        for x in range(W):
            world.set_tile(x, y, T_CONCRETE)
    for y in range(50, 54):
        for x in range(W):
            world.set_tile(x, y, T_CONCRETE)
    # Middle corridor
    for y in range(24, 32):
        for x in range(W):
            world.set_tile(x, y, T_CONCRETE)

    # Stripes of dirt
    for _ in range(80):
        cx = random.randint(0, W - 2)
        cy = random.randint(0, H - 2)
        if world.tiles[cy][cx] == T_ASH:
            world.tiles[cy][cx] = T_DIRT

    # Container stacks (rows)
    def add_stack(gx, gy, w, h, color):
        _add_container(world, gx * TILE, gy * TILE,
                       w * TILE, h * TILE, color=color)

    # Warehouse buildings
    _add_house(world, 4 * TILE, 8 * TILE, 12 * TILE, 14 * TILE,
               wall=(120, 120, 130), roof=(80, 80, 90))
    _add_house(world, 4 * TILE, 32 * TILE, 12 * TILE, 14 * TILE,
               wall=(120, 120, 130), roof=(80, 80, 90))
    _add_house(world, 84 * TILE, 8 * TILE, 12 * TILE, 14 * TILE,
               wall=(140, 100, 80), roof=(120, 60, 40))
    _add_house(world, 84 * TILE, 32 * TILE, 12 * TILE, 14 * TILE,
               wall=(140, 100, 80), roof=(120, 60, 40))

    # Shop (office) — building in center top
    shop_x, shop_y = 44, 8
    _add_house(world, shop_x * TILE, shop_y * TILE,
               12 * TILE, 12 * TILE,
               wall=(240, 230, 210), roof=(60, 140, 90))
    world.shop_rect = pygame.Rect((shop_x + 4) * TILE,
                                  (shop_y + 12 + 1) * TILE,
                                  4 * TILE, 2 * TILE)

    # Container stacks across middle area
    container_colors = [(180, 50, 40), (60, 110, 180), (220, 170, 50),
                        (50, 150, 100), (140, 60, 130)]
    layouts = [
        (18, 10, 3, 4), (18, 14, 3, 4), (22, 12, 3, 6),
        (28, 8, 3, 4), (28, 12, 3, 4), (32, 8, 3, 6),
        (60, 8, 3, 4), (60, 12, 3, 4), (64, 10, 3, 4),
        (68, 12, 3, 6), (72, 8, 3, 4), (76, 12, 3, 4),
        (18, 36, 3, 4), (18, 40, 3, 4), (22, 36, 3, 6),
        (28, 38, 3, 4), (28, 42, 3, 4),
        (60, 36, 3, 6), (64, 38, 3, 4), (64, 42, 3, 4),
        (68, 36, 3, 4), (72, 40, 3, 6), (76, 36, 3, 4),
    ]
    for i, (x, y, w, h) in enumerate(layouts):
        add_stack(x, y, w, h, container_colors[i % len(container_colors)])

    # Machines (large industrial objects)
    for gx, gy in [(36, 16), (52, 16), (36, 38), (52, 38)]:
        world.add_solid(Solid(pygame.Rect(gx * TILE, gy * TILE,
                                          4 * TILE, 4 * TILE), "machine"))

    # Crates around for ammo loot
    for gx, gy in [(20, 28), (30, 28), (45, 27),
                   (60, 28), (75, 28), (88, 27),
                   (12, 26), (8, 28)]:
        world.add_solid(Solid(pygame.Rect(gx * TILE, gy * TILE,
                                          TILE, TILE), "crate"))

    # Drums
    for gx, gy in [(20, 26), (40, 25), (62, 26), (80, 25)]:
        _add_drum(world, gx * TILE, gy * TILE)

    # Pickups
    _scatter_gold(world, pygame.Rect(4 * TILE, 24 * TILE,
                                     90 * TILE, 8 * TILE), 18, 20)
    world.add_pickup(Pickup(Vec(30 * TILE, 28 * TILE), P_MEDKIT))
    world.add_pickup(Pickup(Vec(60 * TILE, 28 * TILE), P_MEDKIT))
    world.add_pickup(Pickup(Vec(86 * TILE, 28 * TILE), P_MEDKIT))
    for x in (16, 32, 50, 70, 88):
        world.add_pickup(Pickup(Vec(x * TILE, 28 * TILE), P_AMMO))

    # Decals
    for _ in range(80):
        x = random.randint(0, W * TILE - 8)
        y = random.randint(0, H * TILE - 8)
        ti = x // TILE
        tj = y // TILE
        if 0 <= ti < W and 0 <= tj < H and world.tiles[tj][ti] in (T_ASH, T_CONCRETE):
            world.add_decal(Decal(pygame.Rect(x, y, 12, 12), "puddle"))

    world.spawn = Vec(3 * TILE, 28 * TILE)
    world.exit_rect = pygame.Rect((W - 4) * TILE, 26 * TILE,
                                  3 * TILE, 5 * TILE)
    world.exit_locked = True

    enemies = []
    # SMG minions in mid area
    for _ in range(8):
        x = random.randint(18 * TILE, 60 * TILE)
        y = random.randint(20 * TILE, 36 * TILE)
        enemies.append(Enemy("minion_smg", Vec(x, y)))
    # snipers on raised positions (right side)
    for _ in range(4):
        x = random.randint(60 * TILE, 88 * TILE)
        y = random.choice([10 * TILE, 42 * TILE])
        enemies.append(Enemy("sniper", Vec(x, y)))
    # wild dogs roaming
    for _ in range(6):
        x = random.randint(20 * TILE, 80 * TILE)
        y = random.randint(20 * TILE, 38 * TILE)
        enemies.append(Enemy("wild_dog", Vec(x, y)))
    # extra mid-range pistol thieves
    for _ in range(6):
        x = random.randint(24 * TILE, 80 * TILE)
        y = random.randint(20 * TILE, 36 * TILE)
        enemies.append(Enemy("thief_pistol", Vec(x, y)))

    # Boss Arena
    arena_x = (W - 14) * TILE
    arena_y = 24 * TILE
    arena_w = 12 * TILE
    arena_h = 12 * TILE
    # Walls
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y, arena_w, 20)))
    world.solids.append(Solid(pygame.Rect(arena_x, arena_y + arena_h, arena_w, 20)))
    world.solids.append(Solid(pygame.Rect(arena_x + arena_w, arena_y, 20, arena_h + 20)))
    # Gate
    gate_rect = pygame.Rect(arena_x, arena_y + 20, 20, arena_h - 20)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    # Puppy
    dog_rect = pygame.Rect(arena_x + arena_w - 60, arena_y + arena_h // 2 - 20, 40, 40)
    world.solids.append(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    # Boss: Robot Boss for Level 3
    boss = Enemy("boss4", Vec(arena_x + arena_w // 2, arena_y + arena_h // 2))
    enemies.append(boss)

    return world, enemies, "Level 3 — Khu Công Nghiệp", "industrial"


# ============================================================
# LEVEL 4 — Hang Ổ Trùm (Boss Lair)
# Walled compound: outer yard with hedges + entrance, inner arena with the
# kidnapped dog cage and the boss.
# ============================================================
def build_level4(world=None):
    """Level 4: Steel Fortress - Boss: Mobile Fortress (boss4)
    A high-tech industrial zone with metallic floors, containers, and lasers.
    """
    W, H = 110, 65
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    world.biome = "industrial"

    # Central industrial road
    for x in range(W):
        for y in range(H // 2 - 2, H // 2 + 3):
            world.set_tile(x, y, T_ROAD_H)

    # Adding large warehouses (containers)
    def add_warehouse(gx, gy, gw, gh):
        rect = pygame.Rect(gx * TILE, gy * TILE, gw * TILE, gh * TILE)
        world.add_solid(Solid(rect, "container", color=(60, 60, 75)))
        # Inner floor
        for ix in range(gx + 1, gx + gw - 1):
            for iy in range(gy + 1, gy + gh - 1):
                world.set_tile(ix, iy, T_FLOOR_TILE)

    add_warehouse(10, 5, 12, 10)
    add_warehouse(30, 5, 15, 12)
    add_warehouse(10, 45, 12, 10)
    add_warehouse(35, 48, 18, 10)
    add_warehouse(60, 45, 12, 14)

    # Machine clusters
    for gx, gy in [(25, 20), (45, 25), (65, 20), (25, 40), (45, 38)]:
        world.add_solid(Solid(pygame.Rect(gx * TILE, gy * TILE, 3 * TILE, 3 * TILE), "machine"))

    # Barriers/Fences
    for x in range(50, 90, 8):
        world.add_solid(Solid(pygame.Rect(x * TILE, 10 * TILE, 10, 6 * TILE), "fence"))
        world.add_solid(Solid(pygame.Rect(x * TILE, 50 * TILE, 10, 6 * TILE), "fence"))

    # Boss Arena (The Core)
    arena_x = 85 * TILE
    arena_y = 20 * TILE
    arena_w = 20 * TILE
    arena_h = 25 * TILE
    # Heavy walls
    world.add_solid(Solid(pygame.Rect(arena_x, arena_y, arena_w, 40), color=(40, 40, 50)))
    world.add_solid(Solid(pygame.Rect(arena_x, arena_y + arena_h - 40, arena_w, 40), color=(40, 40, 50)))
    world.add_solid(Solid(pygame.Rect(arena_x + arena_w - 40, arena_y, 40, arena_h), color=(40, 40, 50)))
    
    # Gate
    gate_rect = pygame.Rect(arena_x, arena_y + 40, 30, arena_h - 80)
    world.add_solid(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    
    # Puppy inside arena
    dog_rect = pygame.Rect(arena_x + arena_w - 120, arena_y + arena_h // 2 - 30, 60, 60)
    world.add_solid(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    world.spawn = Vec(5 * TILE, (H // 2) * TILE)
    world.exit_rect = dog_rect.inflate(40, 40)
    world.exit_locked = True

    enemies = []
    # Patrol robots (minions)
    for _ in range(12):
        x = random.randint(15 * TILE, 80 * TILE)
        y = random.randint(10 * TILE, 55 * TILE)
        enemies.append(Enemy("minion_smg", Vec(x, y)))
    for _ in range(6):
        x = random.randint(40 * TILE, 85 * TILE)
        y = random.randint(10 * TILE, 55 * TILE)
        enemies.append(Enemy("sniper", Vec(x, y)))

    # Boss: Robot Boss
    boss = Enemy("boss4", Vec(arena_x + arena_w // 2, arena_y + arena_h // 2))
    enemies.append(boss)

    return world, enemies, "Level 4 — Pháo Đài Thép", "industrial"

def build_level5(world=None):
    """Level 5: Industrial Zone - Boss: Mobile Fortress (boss5)"""
    W, H = 100, 60
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    # Just a basic expansion of world and enemies for demonstration
    world.biome = "industrial"
    enemies = []
    # Reuse some logic from other levels but change enemy types
    for _ in range(30):
        enemies.append(Enemy("minion_smg", Vec(random.randint(100, 2000), random.randint(100, 1500))))
    # Boss Gate
    gate_rect = pygame.Rect(1600, 600, 20, 400)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    # Puppy
    dog_rect = pygame.Rect(2000, 750, 40, 40)
    world.solids.append(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    enemies.append(Enemy("boss5", Vec(1800, 800)))
    return world, enemies, "Level 5 — Khu Công Nghiệp", "industrial"


def build_level6(world=None):
    """Level 6: Desert Wasteland - Boss: Desert Hunter (boss6)"""
    W, H = 120, 50
    if world is None:
        world = World(W, H, default_tile=T_SAND)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_SAND] * W for _ in range(H)]
        world._dirty = True
    world.biome = "desert"
    enemies = []
    for _ in range(25):
        enemies.append(Enemy("sniper", Vec(random.randint(100, 2500), random.randint(100, 1200))))
    # Boss Gate
    gate_rect = pygame.Rect(2000, 400, 20, 400)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    # Puppy
    dog_rect = pygame.Rect(2500, 550, 40, 40)
    world.solids.append(Solid(dog_rect, kind="puppy"))
    world.dog_rect = dog_rect

    enemies.append(Enemy("boss6", Vec(2300, 600)))
    return world, enemies, "Level 6 — Sa Mạc Chết", "desert"


def build_level7(world=None):
    """Level 7: The Citadel - Boss: Chúa Tể Umbrella (boss8)"""
    W, H = 100, 80
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    world.biome = "citadel"
    enemies = []
    for _ in range(20):
        enemies.append(Enemy("minion_shotgun", Vec(random.randint(100, 1500), random.randint(100, 1500))))
    # Boss Gate for Umbrella Tower
    gate_rect = pygame.Rect(2200, 800, 20, 400)
    world.solids.append(Solid(gate_rect, kind="boss_gate"))
    world.boss_gate_rect = gate_rect
    
    # MOTHER DOG (already kidnapped in Umbrella Tower)
    dog_rect = pygame.Rect(2700, 950, 80, 80)
    world.solids.append(Solid(dog_rect, kind="mother_dog"))
    world.dog_rect = dog_rect

    # Final Boss
    enemies.append(Enemy("boss7", Vec(2500, 1000)))
    return world, enemies, "Level 7 — Pháo Đài Cuối Cùng", "citadel"


def build_boss_rush_1(world=None):
    """Boss Rush 1: Axe General Extreme"""
    W, H = 60, 60
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    world.biome = "hell"
    enemies = [Enemy("boss1_ex", Vec(1000, 1000))]
    # Add some supporting mobs
    for _ in range(5):
        enemies.append(Enemy("zombie_fast", Vec(random.randint(800, 1200), random.randint(800, 1200))))
    return world, enemies, "BOSS RUSH 1 — Tướng Quân Lửa", "hell"

def build_boss_rush_2(world=None):
    """Boss Rush 2: Toxic Butcher Extreme"""
    W, H = 60, 60
    if world is None:
        world = World(W, H, default_tile=T_CONCRETE)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_CONCRETE] * W for _ in range(H)]
        world._dirty = True
    world.biome = "industrial"
    enemies = [Enemy("boss2_ex", Vec(1000, 1000))]
    for _ in range(8):
        enemies.append(Enemy("minion_smg", Vec(random.randint(800, 1200), random.randint(800, 1200))))
    return world, enemies, "BOSS RUSH 2 — Đồ Tể Độc", "industrial"

def build_boss_rush_3(world=None):
    """Boss Rush 3: Twin Tigers Extreme"""
    W, H = 60, 60
    if world is None:
        world = World(W, H, default_tile=T_GRASS)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_GRASS] * W for _ in range(H)]
        world._dirty = True
    world.biome = "forest"
    enemies = [Enemy("boss3_ex", Vec(1000, 800)), Enemy("boss3_ex", Vec(1000, 1200))]
    return world, enemies, "BOSS RUSH 3 — Song Hổ", "forest"

def build_boss_rush_4(world=None):
    """Boss Rush 4: Ultimate Overlord"""
    W, H = 70, 70
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True
    world.biome = "void"
    enemies = [Enemy("boss7_ex", Vec(1200, 1200))]
    for _ in range(10):
        enemies.append(Enemy("sniper", Vec(random.randint(500, 1500), random.randint(500, 1500))))
    return world, enemies, "BOSS RUSH FINAL — CHÚA TỂ", "void"
    
def build_boss_rush_5(world=None):
    """Boss Rush 5: Steel Fortress"""
    W, H = 80, 60
    if world is None:
        world = World(W, H, default_tile=T_CONCRETE)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_CONCRETE] * W for _ in range(H)]
        world._dirty = True
    world.biome = "industrial"
    enemies = [Enemy("boss4_ex", Vec(1200, 1000))]
    # support drones
    for _ in range(6):
        enemies.append(Enemy("minion_smg", Vec(random.randint(600, 1800), random.randint(600, 1400))))
    return world, enemies, "BOSS RUSH 5 — PHÁO ĐÀI THÉP", "industrial"



# ============================================================
# BOSS RUSH ALL — Đại chiến tất cả Boss trong 1 Map khổng lồ
# ============================================================
def build_boss_rush_all(world=None):
    """The Ultimate Boss Rush: All 7 bosses in one massive 200x150 arena.
    7 distinct biome zones, tons of pickups, supports 1-4 players co-op."""
    W, H = 200, 150
    if world is None:
        world = World(W, H, default_tile=T_ASH)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_ASH] * W for _ in range(H)]
        world._dirty = True

    world.biome = "hell"
    enemies = []

    # ── Helper to paint a rectangular zone ──────────────────────────
    def paint_zone(x0, y0, x1, y1, tile):
        for yy in range(max(0, y0), min(H, y1)):
            for xx in range(max(0, x0), min(W, x1)):
                world.tiles[yy][xx] = tile

    def add_walls(x0, y0, x1, y1):
        """Add decorative pillars at corners + sides of an arena."""
        for px, py in [(x0, y0),(x1-2, y0),(x0, y1-2),(x1-2, y1-2),
                       ((x0+x1)//2, y0),((x0+x1)//2, y1-2),
                       (x0, (y0+y1)//2),(x1-2, (y0+y1)//2)]:
            world.add_solid(Solid(pygame.Rect(px*TILE, py*TILE, TILE*2, TILE*2), "house"))

    def scatter_pickups(x0, y0, x1, y1, count=8):
        for _ in range(count):
            px = random.randint(x0*TILE+40, x1*TILE-40)
            py = random.randint(y0*TILE+40, y1*TILE-40)
            kind = random.choice([P_GOLD, P_GOLD, P_MEDKIT, P_AMMO, P_AMMO])
            world.add_pickup(Pickup(Vec(px, py), kind, 60 if kind == P_GOLD else 1))

    # ── Spawn point (center of map) ──────────────────────────────────
    world.spawn = Vec(W * TILE // 2, H * TILE // 2)

    # ── Zone layout (7 zones arranged around center) ─────────────────
    # Zone 1 (NW) — Lava — Boss1 (Đại Tướng Rìu Máu)
    paint_zone(5, 5, 65, 55, T_ROAD_H)
    paint_zone(8, 8, 62, 52, T_ASH)
    add_walls(10, 10, 60, 50)
    scatter_pickups(10, 10, 60, 50, 12)
    enemies.append(Enemy("boss1", Vec(35 * TILE, 30 * TILE)))
    for _ in range(5):
        enemies.append(Enemy("zombie_fast", Vec(random.randint(12*TILE, 58*TILE),
                                                 random.randint(12*TILE, 48*TILE))))

    # Zone 2 (N center) — Concrete — Boss2 (Đồ Tể Đột Biến)
    paint_zone(70, 5, 130, 55, T_CONCRETE)
    add_walls(73, 8, 127, 52)
    scatter_pickups(73, 8, 127, 52, 14)
    enemies.append(Enemy("boss2", Vec(100 * TILE, 28 * TILE)))
    for _ in range(6):
        enemies.append(Enemy("zombie", Vec(random.randint(75*TILE, 125*TILE),
                                           random.randint(10*TILE, 50*TILE))))

    # Zone 3 (NE) — Forest — Boss3 (Hổ Vương)
    paint_zone(135, 5, 195, 55, T_GRASS_DARK)
    paint_zone(138, 8, 192, 52, T_GRASS)
    add_walls(140, 10, 190, 50)
    scatter_pickups(140, 10, 190, 50, 12)
    enemies.append(Enemy("boss3", Vec(162 * TILE, 28 * TILE)))
    for _ in range(4):
        enemies.append(Enemy("tiger", Vec(random.randint(142*TILE, 188*TILE),
                                          random.randint(12*TILE, 48*TILE))))

    # Zone 4 (SW) — Industrial — Boss4 (Pháo Đài Di Động)
    paint_zone(5, 98, 65, 145, T_ROAD_V)
    paint_zone(8, 100, 62, 143, T_CONCRETE)
    add_walls(10, 102, 60, 141)
    scatter_pickups(10, 102, 60, 141, 14)
    enemies.append(Enemy("boss4", Vec(35 * TILE, 120 * TILE)))
    for _ in range(5):
        enemies.append(Enemy("minion_smg", Vec(random.randint(12*TILE, 58*TILE),
                                                random.randint(104*TILE, 139*TILE))))

    # Zone 5 (S center) — Desert — Boss5 (Thợ Săn Sa Mạc)
    paint_zone(70, 98, 130, 145, T_SAND)
    add_walls(73, 100, 127, 143)
    scatter_pickups(73, 100, 127, 143, 12)
    enemies.append(Enemy("boss5", Vec(100 * TILE, 120 * TILE)))
    for _ in range(6):
        enemies.append(Enemy("sniper", Vec(random.randint(75*TILE, 125*TILE),
                                           random.randint(102*TILE, 141*TILE))))

    # Zone 6 (SE) — Void — Boss6 (Pháp Sư Hắc Ám)
    paint_zone(135, 98, 195, 145, T_FLOOR_TILE)
    add_walls(138, 100, 192, 143)
    scatter_pickups(138, 100, 192, 143, 14)
    enemies.append(Enemy("boss6", Vec(162 * TILE, 120 * TILE)))
    for _ in range(5):
        enemies.append(Enemy("minion_shotgun", Vec(random.randint(140*TILE, 190*TILE),
                                                    random.randint(102*TILE, 141*TILE))))

    # Zone 7 (CENTER) — Dark Palace — Boss7 (Chúa Tể Umbrella) — FINAL
    paint_zone(68, 53, 132, 97, T_FLOOR_WOOD)
    paint_zone(72, 57, 128, 93, T_FLOOR_TILE)
    add_walls(74, 59, 126, 91)
    scatter_pickups(74, 59, 126, 91, 20)
    # More generous health pickups for the final boss
    for _ in range(6):
        world.add_pickup(Pickup(Vec(random.randint(76*TILE, 124*TILE),
                                    random.randint(61*TILE, 89*TILE)), P_MEDKIT, 1))
    enemies.append(Enemy("boss7", Vec(100 * TILE, 75 * TILE)))

    # ── Connecting corridors with road tiles ─────────────────────────
    # H corridors
    for cx in range(65, 70): paint_zone(cx, 20, cx+1, 35, T_ROAD_H)   # NW → N
    for cx in range(130, 135): paint_zone(cx, 20, cx+1, 35, T_ROAD_H) # N → NE
    for cx in range(65, 70): paint_zone(cx, 110, cx+1, 125, T_ROAD_H)  # SW → S
    for cx in range(130, 135): paint_zone(cx, 110, cx+1, 125, T_ROAD_H)# S → SE
    # V corridors
    for cy in range(55, 62): paint_zone(28, cy, 45, cy+1, T_ROAD_V)   # NW → SW
    for cy in range(55, 62): paint_zone(95, cy, 115, cy+1, T_ROAD_V)  # N  → Center
    for cy in range(55, 62): paint_zone(155, cy, 172, cy+1, T_ROAD_V) # NE → SE
    
    return world, enemies, "⚡ ĐẠI CHIẾN BOSS RUSH (ALL) ⚡", "citadel"

def build_pvp_arena(world=None):
    """A small, intense arena designed for PvP combat with cover and pickups."""
    W, H = 50, 40
    if world is None:
        world = World(W, H, default_tile=T_CONCRETE)
    else:
        world.w, world.h = W, H
        world.tiles = [[T_CONCRETE] * W for _ in range(H)]
        world._dirty = True
    
    world.biome = "industrial"
    world.spawn = Vec(W * TILE // 2, H * TILE // 2)
    
    # Simple walls around the edge
    for x in range(W):
        world.add_solid(Solid(pygame.Rect(x*TILE, 0, TILE, TILE), "wall", color=(40,40,40)))
        world.add_solid(Solid(pygame.Rect(x*TILE, (H-1)*TILE, TILE, TILE), "wall", color=(40,40,40)))
    for y in range(H):
        world.add_solid(Solid(pygame.Rect(0, y*TILE, TILE, TILE), "wall", color=(40,40,40)))
        world.add_solid(Solid(pygame.Rect((W-1)*TILE, y*TILE, TILE, TILE), "wall", color=(40,40,40)))
        
    # Some cover in the middle (containers, crates, etc.)
    for _ in range(12):
        cx = random.randint(5, W-10)
        cy = random.randint(5, H-10)
        kind = random.choice(["container", "crate", "car"])
        world.add_solid(Solid(pygame.Rect(cx*TILE, cy*TILE, TILE*2, TILE*2), kind))

    # Explosive drums for extra chaos
    for _ in range(8):
        cx = random.randint(5, W-5)
        cy = random.randint(5, H-5)
        world.add_solid(Solid(pygame.Rect(cx*TILE, cy*TILE, TILE, TILE), "drum"))
        
    # Abundant medkits and ammo for long fights
    for _ in range(15):
        px = random.randint(2*TILE, (W-2)*TILE)
        py = random.randint(2*TILE, (H-2)*TILE)
        kind = random.choice([P_MEDKIT, P_AMMO])
        world.add_pickup(Pickup(Vec(px, py), kind))

    return world, [], "🔥 ĐẤU TRƯỜNG SINH TỒN (PvP) 🔥", "industrial"

# ============================================================
LEVEL_BUILDERS = [
    build_level1, build_level2, build_level3, build_level4,
    build_level5, build_level6, build_level7,
    build_boss_rush_1, build_boss_rush_2, build_boss_rush_3, build_boss_rush_4, build_boss_rush_5,
    build_boss_rush_all,   # index 12 — The Ultimate All-Boss map
    build_pvp_arena,       # index 13 — PvP Arena
]
