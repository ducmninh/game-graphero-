"""HUD: HP bar (top-left), gold, current weapon + ammo, minimap, quest hint, boss bar."""
from __future__ import annotations
import math
import pygame
from utils import Vec, draw_text, draw_bar, draw_panel, clamp, lerp_color
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, HUD_PAD, HUD_HP_W, HUD_HP_H,
    WEAPONS, FONT_PATH,
)


class HUD:
    def __init__(self):
        self.message = ""
        self.message_t = 0.0
        self.boss_target = None
        self.boss_name = ""

    def set_message(self, msg, duration=3.0):
        self.message = msg
        self.message_t = duration

    def set_boss(self, boss, name=""):
        self.boss_target = boss
        self.boss_name = name

    def clear_boss(self):
        self.boss_target = None

    def update(self, dt):
        if self.message_t > 0:
            self.message_t = max(0, self.message_t - dt)

    def draw(self, surf, player, level_name, world, enemies, t):
        # ---- Top-left HP + Gold ----
        x = HUD_PAD
        y = HUD_PAD
        # HP bar with color shift
        hp_pct = player.hp / player.max_hp
        if hp_pct > 0.6:
            hp_color = (60, 200, 80)
        elif hp_pct > 0.3:
            hp_color = (240, 200, 60)
        else:
            hp_color = (220, 60, 60)
        # Pulse if low
        if hp_pct < 0.3:
            pulse = (math.sin(t * 8) + 1) / 2
            hp_color = lerp_color(hp_color, (255, 255, 255), pulse * 0.3)

        # Frame
        draw_panel(surf, pygame.Rect(x - 6, y - 6, HUD_HP_W + 170, 90),
                   fill=(0, 0, 0, 140), border=(220, 220, 220))
        # HP icon (heart)
        heart_x = x + 4
        heart_y = y + 4
        pygame.draw.polygon(surf, (220, 50, 50), [
            (heart_x + 12, heart_y + 4),
            (heart_x + 6, heart_y),
            (heart_x, heart_y + 4),
            (heart_x, heart_y + 8),
            (heart_x + 12, heart_y + 20),
            (heart_x + 24, heart_y + 8),
            (heart_x + 24, heart_y + 4),
            (heart_x + 18, heart_y),
        ])
        pygame.draw.polygon(surf, (255, 100, 100), [
            (heart_x + 4, heart_y + 4),
            (heart_x + 2, heart_y + 7),
            (heart_x + 6, heart_y + 10),
        ])
        # HP bar
        draw_bar(surf, x + 34, y + 4, HUD_HP_W, HUD_HP_H, hp_pct,
                 fg=hp_color, bg=(40, 40, 40))
        draw_text(surf, f"{int(player.hp)} / {player.max_hp}",
                  (x + 34 + HUD_HP_W // 2, y + 4 + HUD_HP_H // 2),
                  size=14, bold=True, center=True)

        # Stamina bar
        sta_pct = player.stamina / 100
        draw_bar(surf, x + 34, y + 30, HUD_HP_W, 10, sta_pct,
                 fg=(180, 230, 80), bg=(40, 40, 40))
        draw_text(surf, "Stamina", (x + 34, y + 30 - 1), size=11,
                  color=(220, 220, 220))

        # Armor bar
        arm_pct = player.armor / player.max_armor
        draw_bar(surf, x + 34, y + 46, HUD_HP_W, 10, arm_pct,
                 fg=(80, 180, 255), bg=(40, 40, 40))
        draw_text(surf, "Armor", (x + 34, y + 46 - 1), size=11,
                  color=(220, 220, 220))

        # Gold
        gx = x + 4
        gy = y + 50
        pygame.draw.circle(surf, (110, 80, 0), (gx + 12, gy + 13), 11)
        pygame.draw.circle(surf, (255, 215, 0), (gx + 12, gy + 12), 10)
        draw_text(surf, "$", (gx + 12, gy + 12), size=14, bold=True,
                  color=(110, 80, 0), center=True, shadow=False)
        draw_text(surf, f"{player.gold}", (gx + 30, gy + 16),
                  size=22, color=(255, 215, 0), bold=True)

        # Level name
        draw_text(surf, level_name, (gx + 130, gy + 4),
                  size=18, color=(220, 220, 230), bold=True)

        # ---- Bottom-left: Weapon + ammo ----
        wpn = player.weapon
        spec = WEAPONS[wpn.key]
        bx = HUD_PAD
        by = SCREEN_HEIGHT - HUD_PAD - 80
        draw_panel(surf, pygame.Rect(bx - 6, by - 6, 340, 86),
                   fill=(0, 0, 0, 160), border=(220, 220, 220))
        # weapon icon (color block)
        pygame.draw.rect(surf, spec["color"], (bx, by, 36, 36),
                         border_radius=4)
        pygame.draw.rect(surf, (0, 0, 0), (bx, by, 36, 36), 2, border_radius=4)
        # weapon name
        draw_text(surf, spec["name"], (bx + 46, by - 2), size=20,
                  bold=True, color=(255, 255, 255))
        # ammo
        if wpn.spec.get("ammo_reserve", 9999) >= 9999:
            reserve = "∞"
        else:
            reserve = str(wpn.ammo_reserve)
        draw_text(surf, f"{wpn.ammo_in_mag} / {reserve}", (bx + 46, by + 18),
                  size=22, bold=True, color=(255, 230, 110))
        if wpn.reloading:
            pct = wpn.reload_progress()
            draw_bar(surf, bx + 46, by + 50, 200, 8, pct,
                     fg=(255, 200, 60), bg=(40, 40, 40))
            draw_text(surf, "RELOADING...", (bx + 46, by + 56),
                      size=12, color=(255, 200, 60))

        # Weapon slots 1..N
        slot_x = bx
        slot_y = by + 50
        for i, key in enumerate(player.weapon_order):
            r = pygame.Rect(slot_x + i * 24, slot_y, 20, 20)
            pygame.draw.rect(surf, WEAPONS[key]["color"], r, border_radius=3)
            border = (255, 255, 0) if key == wpn.key else (40, 40, 40)
            pygame.draw.rect(surf, border, r, 2, border_radius=3)
            draw_text(surf, str(i + 1), (r.centerx, r.bottom + 1),
                      size=10, color=(220, 220, 220),
                      center=True, shadow=False)

        # ---- Bottom-right: controls hint (right-aligned) ----
        hint_x = SCREEN_WIDTH - HUD_PAD
        hints = [
            "WASD: di chuyển",
            "Chuột: ngắm/bắn",
            "R: nạp đạn",
            "1-7: chọn súng",
            "Q/E: đổi súng / shop",
            "Shift: chạy nhanh",
            "Space: né",
            "F: lên/xuống xe",
            "Tab: bản đồ",
            "ESC: pause",
        ]
        font = pygame.font.SysFont(FONT_PATH, 12)
        for i, h in enumerate(hints):
            img = font.render(h, True, (200, 200, 200))
            sh = font.render(h, True, (0, 0, 0))
            r = img.get_rect(topright=(hint_x,
                             SCREEN_HEIGHT - HUD_PAD - 16 - i * 16))
            surf.blit(sh, r.move(1, 1))
            surf.blit(img, r)

        # ---- Top-center: quest message ----
        if self.message_t > 0:
            alpha = clamp(self.message_t * 2, 0, 1)
            msg_surf = pygame.font.SysFont(FONT_PATH, 28, bold=True).render(
                self.message, True, (255, 255, 255))
            sh = pygame.font.SysFont(FONT_PATH, 28, bold=True).render(
                self.message, True, (0, 0, 0))
            msg_surf.set_alpha(int(alpha * 255))
            sh.set_alpha(int(alpha * 255))
            r = msg_surf.get_rect(center=(SCREEN_WIDTH // 2, 60))
            surf.blit(sh, r.move(2, 2))
            surf.blit(msg_surf, r)

        # ---- Boss bar ----
        if self.boss_target is not None and self.boss_target.alive:
            self.draw_boss_bar(surf, self.boss_target, self.boss_name)

        # ---- Minimap top-right ----
        self.draw_minimap(surf, player, world, enemies)

    def draw_boss_bar(self, surf, boss, name):
        bw = 720
        bh = 28
        bx = (SCREEN_WIDTH - bw) // 2
        by = SCREEN_HEIGHT - 60
        draw_panel(surf, pygame.Rect(bx - 6, by - 28, bw + 12, bh + 36),
                   fill=(20, 0, 0, 200), border=(200, 30, 30))
        draw_text(surf, f"BOSS: {name}", (bx + bw // 2, by - 12),
                  size=22, bold=True, color=(255, 200, 200), center=True)
        pct = clamp(boss.hp / boss.max_hp, 0, 1)
        draw_bar(surf, bx, by, bw, bh, pct,
                 fg=(220, 40, 40), bg=(50, 0, 0), border=(0, 0, 0))
        draw_text(surf, f"{int(boss.hp)} / {boss.max_hp}",
                  (bx + bw // 2, by + bh // 2),
                  size=16, color=(255, 255, 255), bold=True, center=True)

    def draw_minimap(self, surf, player, world, enemies):
        size = 180
        x = SCREEN_WIDTH - HUD_PAD - size
        y = HUD_PAD
        rect = pygame.Rect(x, y, size, size)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((20, 20, 25, 180))
        ww, wh = world.pixel_size()
        sx = size / ww
        sy = size / wh

        # Tile colors
        from world import (
            T_ROAD_H, T_ROAD_V, T_ROAD_X, T_GRASS, T_GRASS_DARK,
            T_CONCRETE, T_DIRT, T_SAND, T_ASH,
        )
        # Draw downsampled tiles
        for j in range(0, world.h, 2):
            for i in range(0, world.w, 2):
                t = world.tiles[j][i]
                col = None
                if t in (T_ROAD_H, T_ROAD_V, T_ROAD_X):
                    col = (90, 90, 95)
                elif t == T_CONCRETE:
                    col = (130, 130, 130)
                elif t == T_DIRT:
                    col = (110, 80, 50)
                elif t == T_ASH:
                    col = (60, 60, 65)
                if col:
                    px = int(i * world.tile_size * sx)
                    py = int(j * world.tile_size * sy)
                    pygame.draw.rect(s, col, (px, py, 4, 4))
        # solids (houses) as dark blocks
        for sol in world.solids:
            if not sol.alive:
                continue
            if sol.kind in ("house", "wall", "container", "machine", "rubble"):
                r = sol.rect
                rx = int(r.left * sx)
                ry = int(r.top * sy)
                rw = max(2, int(r.width * sx))
                rh = max(2, int(r.height * sy))
                pygame.draw.rect(s, (160, 130, 90), (rx, ry, rw, rh))
        # enemies
        for e in enemies:
            if not e.alive:
                continue
            ex = int(e.pos.x * sx)
            ey = int(e.pos.y * sy)
            col = (255, 80, 80) if not e.is_boss else (255, 30, 180)
            pygame.draw.circle(s, col, (ex, ey), 3 if not e.is_boss else 5)
        # exit
        if world.exit_rect:
            ex = int(world.exit_rect.centerx * sx)
            ey = int(world.exit_rect.centery * sy)
            col = (220, 220, 220) if world.exit_locked else (60, 220, 100)
            pygame.draw.circle(s, col, (ex, ey), 4)
        # shop
        if world.shop_rect:
            sx2 = int(world.shop_rect.centerx * sx)
            sy2 = int(world.shop_rect.centery * sy)
            pygame.draw.rect(s, (255, 215, 0),
                             (sx2 - 3, sy2 - 3, 6, 6))
        # dog
        if world.dog_rect:
            dx = int(world.dog_rect.centerx * sx)
            dy = int(world.dog_rect.centery * sy)
            pygame.draw.circle(s, (255, 180, 200), (dx, dy), 4)
        # player (green dot with arrow)
        px = int(player.pos.x * sx)
        py = int(player.pos.y * sy)
        pygame.draw.circle(s, (90, 220, 90), (px, py), 4)
        ax = px + int(math.cos(player.aim_angle) * 8)
        ay = py + int(math.sin(player.aim_angle) * 8)
        pygame.draw.line(s, (90, 220, 90), (px, py), (ax, ay), 2)

        # border
        pygame.draw.rect(s, (220, 220, 220), s.get_rect(), 2)
        surf.blit(s, rect.topleft)
        draw_text(surf, "MAP", (x + size // 2, y + size + 8),
                  size=12, color=(220, 220, 220), bold=True, center=True)
