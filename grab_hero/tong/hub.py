"""Sảnh (Hub) — between-level menu for permanent upgrades + shop + pets.

Layout: a single overlay with 4 tabs at the top:
  • NÂNG CẤP NHÂN VẬT   (character permanent upgrades)
  • MUA SÚNG            (unlock weapons directly)
  • MUA PET             (buy and equip companions)
  • CHƠI                (start / continue the run)

Gold and upgrade state are persistent: any gold the player ends a run with is
banked into the save when they enter the hub, and all purchases come out of
the banked total. Leaving the hub via "CHƠI" applies the upgrades + spawns
the pet on the player and starts (or resumes) the run.
"""
from __future__ import annotations
import math
import pygame

from utils import Vec, draw_text
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SPRITES,
    CHAR_UPGRADES, CHAR_UPGRADE_ORDER,
    PETS, PET_ORDER,
    HUB_GUN_ORDER, WEAPONS,
    GRAB_GREEN, DARK_GREEN, GOLD, YELLOW, FONT_PATH,
)


# Cached preview sprites (loaded on first access)
_gun_previews: dict = {}
_grab_previews: dict = {}


def _load_preview(filename, target_w):
    path = SPRITES / filename
    if not path.exists():
        return None
    try:
        img = pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, OSError):
        return None
    w, h = img.get_size()
    if w > target_w:
        scale = target_w / w
        img = pygame.transform.smoothscale(img, (target_w, int(h * scale)))
    return img


def get_gun_preview(key):
    if key in _gun_previews:
        return _gun_previews[key]
    name_map = {
        "shotgun": "gun_shotgun.png",
        "smg": "gun_smg.png",
        "sniper": "gun_sniper.png",
    }
    fname = name_map.get(key)
    img = _load_preview(fname, 220) if fname else None
    _gun_previews[key] = img
    return img


def get_grab_preview(key):
    if key in _grab_previews:
        return _grab_previews[key]
    name_map = {
        "pistol": "grab_holds_pistol.png",
        "pistol_mk2": "grab_holds_pistol.png",
        "smg": "grab_holds_smg.png",
        "shotgun": "grab_holds_shotgun.png",
        "sniper": "grab_holds_sniper.png",
        "ar": "grab_holds_smg.png",
    }
    fname = name_map.get(key)
    img = _load_preview(fname, 180) if fname else None
    _grab_previews[key] = img
    return img


TAB_UPGRADE = 0
TAB_GUN = 1
TAB_PET = 2
TAB_PLAY = 3

TAB_NAMES = [
    "NÂNG CẤP NHÂN VẬT",
    "MUA SÚNG",
    "MUA PET",
    "CHƠI",
]


class Hub:
    def __init__(self, save: dict):
        self.save = save
        self.tab = TAB_UPGRADE
        self.row = 0                # selected row in current tab
        self.message = ""
        self.message_t = 0.0
        self.open = True
        self.exit_to_play = False   # set True when player picks CHƠI
        self.t = 0.0

    # ----------------------------------------------------------
    def feedback(self, msg: str):
        self.message = msg
        self.message_t = 1.8

    # ----------------------------------------------------------
    def _row_count(self):
        if self.tab == TAB_UPGRADE:
            return len(CHAR_UPGRADE_ORDER)
        if self.tab == TAB_GUN:
            return len(HUB_GUN_ORDER)
        if self.tab == TAB_PET:
            # one row per pet, plus a "không dùng" row
            return len(PET_ORDER) + 1
        return 1  # play tab has a single big action

    # ----------------------------------------------------------
    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k in (pygame.K_LEFT, pygame.K_a):
            self.tab = (self.tab - 1) % 4
            self.row = 0
            return
        if k in (pygame.K_RIGHT, pygame.K_d):
            self.tab = (self.tab + 1) % 4
            self.row = 0
            return
        if k in (pygame.K_TAB,):
            self.tab = (self.tab + 1) % 4
            self.row = 0
            return
        if k in (pygame.K_UP, pygame.K_w):
            self.row = (self.row - 1) % self._row_count()
            return
        if k in (pygame.K_DOWN, pygame.K_s):
            self.row = (self.row + 1) % self._row_count()
            return
        if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
            self._activate()
            return
        if k == pygame.K_p:
            # quick "Play"
            self.tab = TAB_PLAY
            self.row = 0
            self._activate()
            return

    # ----------------------------------------------------------
    def _activate(self):
        if self.tab == TAB_UPGRADE:
            self._buy_upgrade(CHAR_UPGRADE_ORDER[self.row])
        elif self.tab == TAB_GUN:
            self._buy_gun(HUB_GUN_ORDER[self.row])
        elif self.tab == TAB_PET:
            if self.row < len(PET_ORDER):
                self._buy_or_equip_pet(PET_ORDER[self.row])
            else:
                # "không dùng pet" row
                self.save["equipped_pet"] = None
                self.feedback("Đã bỏ pet — solo run")
        elif self.tab == TAB_PLAY:
            self.exit_to_play = True
            self.open = False

    # ----------------------------------------------------------
    def _buy_upgrade(self, key: str):
        u = CHAR_UPGRADES[key]
        lvl = self.save["upgrades"].get(key, 0)
        if lvl >= u["max_level"]:
            self.feedback(f"{u['name']} đã đạt cấp tối đa")
            return
        cost = u["cost"][lvl]
        if self.save["gold"] < cost:
            self.feedback("Không đủ vàng")
            return
        self.save["gold"] -= cost
        self.save["upgrades"][key] = lvl + 1
        from saveload import write_save
        write_save(self.save)
        self.feedback(f"Đã nâng {u['name']} lên cấp {lvl + 1}!")

    def _buy_gun(self, key: str):
        if key in self.save["owned_guns"]:
            self.feedback("Đã sở hữu súng này")
            return
        price = WEAPONS[key]["price"]
        if self.save["gold"] < price:
            self.feedback("Không đủ vàng")
            return
        self.save["gold"] -= price
        self.save["owned_guns"].append(key)
        from saveload import write_save
        write_save(self.save)
        self.feedback(f"Đã mua {WEAPONS[key]['name']}!")

    def _buy_or_equip_pet(self, key: str):
        spec = PETS[key]
        if key in self.save["owned_pets"]:
            if self.save.get("equipped_pet") == key:
                self.feedback(f"{spec['emoji']} {spec['name']} đang theo bạn")
            else:
                self.save["equipped_pet"] = key
                self.feedback(f"Đã trang bị {spec['name']}")
            return
        price = spec["price"]
        if self.save["gold"] < price:
            self.feedback("Không đủ vàng để mua pet này")
            return
        self.save["gold"] -= price
        self.save["owned_pets"].append(key)
        from saveload import write_save
        write_save(self.save)
        self.save["equipped_pet"] = key
        self.feedback(f"Đã mua {spec['name']}!")

    # ----------------------------------------------------------
    def update(self, dt):
        self.t += dt
        if self.message_t > 0:
            self.message_t = max(0.0, self.message_t - dt)

    # ==========================================================
    # DRAW
    # ==========================================================
    def draw(self, surf):
        surf.fill((20, 28, 22))
        self._draw_backdrop(surf)

        # Title bar
        draw_text(surf, "SẢNH GRAB HERO",
                  (SCREEN_WIDTH // 2, 28), size=44,
                  color=GOLD, bold=True, center=True)
        draw_text(surf, f"Vàng tích luỹ: {self.save['gold']}",
                  (SCREEN_WIDTH // 2, 70), size=22,
                  color=(255, 230, 100), bold=True, center=True)

        # Tabs
        self._draw_tabs(surf)

        # Panel
        panel = pygame.Rect(60, 160, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 240)
        pygame.draw.rect(surf, (24, 32, 28), panel)
        pygame.draw.rect(surf, GRAB_GREEN, panel, 3)

        if self.tab == TAB_UPGRADE:
            self._draw_upgrade_panel(surf, panel)
        elif self.tab == TAB_GUN:
            self._draw_gun_panel(surf, panel)
        elif self.tab == TAB_PET:
            self._draw_pet_panel(surf, panel)
        else:
            self._draw_play_panel(surf, panel)

        # Footer help
        draw_text(surf,
                  "←/→ chuyển panel    ↑/↓ chọn    ENTER mua / chọn    P để chơi",
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50), size=18,
                  color=(220, 220, 220), bold=True, center=True)

        # Message
        if self.message_t > 0:
            mt = self.message_t
            draw_text(surf, self.message,
                      (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90),
                      size=22, color=YELLOW, bold=True, center=True)

    def _draw_backdrop(self, surf):
        """Subtle parallax 'garage' backdrop."""
        # gradient
        for y in range(0, SCREEN_HEIGHT, 6):
            t = y / SCREEN_HEIGHT
            col = (int(20 + t * 12), int(30 + t * 10), int(22 + t * 8))
            pygame.draw.rect(surf, col, (0, y, SCREEN_WIDTH, 6))
        # floor band
        pygame.draw.rect(surf, (32, 36, 30),
                         (0, SCREEN_HEIGHT - 200, SCREEN_WIDTH, 200))
        # decorative columns / Grab green stripes
        for x in range(0, SCREEN_WIDTH, 220):
            offset = int(math.sin(self.t + x * 0.01) * 4)
            pygame.draw.rect(surf, (28, 60, 38),
                             (x + offset, 100, 8, SCREEN_HEIGHT - 160))
        # subtle scanlines for retro look
        for y in range(0, SCREEN_HEIGHT, 3):
            pygame.draw.line(surf, (0, 0, 0, 6),
                             (0, y), (SCREEN_WIDTH, y), 1)

    def _draw_tabs(self, surf):
        n = len(TAB_NAMES)
        tab_w = (SCREEN_WIDTH - 120) // n
        for i, name in enumerate(TAB_NAMES):
            x = 60 + i * tab_w
            r = pygame.Rect(x, 110, tab_w - 10, 44)
            selected = (i == self.tab)
            bg = GRAB_GREEN if selected else (40, 50, 44)
            pygame.draw.rect(surf, bg, r)
            pygame.draw.rect(surf, (10, 20, 14), r, 2)
            txt_col = (10, 30, 16) if selected else (200, 220, 200)
            draw_text(surf, name, r.center, size=18,
                      color=txt_col, bold=True, center=True)

    # ----------------------------------------------------------
    def _draw_row(self, surf, x, y, w, h, title, sub, right_text,
                  selected, color, afford):
        r = pygame.Rect(x, y, w, h)
        bg = (60, 70, 64) if not selected else (80, 110, 90)
        pygame.draw.rect(surf, bg, r)
        border = GOLD if selected else (20, 30, 24)
        pygame.draw.rect(surf, border, r, 3 if selected else 2)
        # color chip
        pygame.draw.rect(surf, color, (x + 8, y + 12, 36, h - 24))
        pygame.draw.rect(surf, (0, 0, 0), (x + 8, y + 12, 36, h - 24), 2)
        draw_text(surf, title, (x + 60, y + 8), size=22,
                  bold=True, color=(255, 255, 255))
        draw_text(surf, sub, (x + 60, y + 38), size=15,
                  color=(210, 210, 210))
        col = YELLOW if afford else (200, 100, 100)
        font = pygame.font.SysFont(FONT_PATH, 22, bold=True)
        img = font.render(right_text, True, col)
        sh = font.render(right_text, True, (0, 0, 0))
        rect = img.get_rect(midright=(x + w - 16, y + h // 2))
        surf.blit(sh, rect.move(2, 2))
        surf.blit(img, rect)

    # ----------------------------------------------------------
    def _draw_upgrade_panel(self, surf, panel):
        draw_text(surf, "Nâng cấp vĩnh viễn — lưu vào save, áp dụng mỗi lần chơi",
                  (panel.centerx, panel.top + 24), size=18,
                  color=(220, 220, 220), bold=True, center=True)
        y = panel.top + 60
        for i, key in enumerate(CHAR_UPGRADE_ORDER):
            u = CHAR_UPGRADES[key]
            lvl = self.save["upgrades"].get(key, 0)
            if lvl >= u["max_level"]:
                right = "MAX"
                afford = False
            else:
                cost = u["cost"][lvl]
                right = f"{cost}$"
                afford = self.save["gold"] >= cost
            sub = f"{u['desc']}  •  Cấp: {lvl}/{u['max_level']}"
            self._draw_row(surf, panel.left + 24, y, panel.width - 48, 70,
                           u["name"], sub, right,
                           selected=(self.row == i),
                           color=u["color"], afford=afford)
            y += 82

    def _draw_gun_panel(self, surf, panel):
        draw_text(surf,
                  "Mua súng đẹp ngay tại sảnh (không cần chờ shop ingame)",
                  (panel.centerx, panel.top + 24), size=18,
                  color=(220, 220, 220), bold=True, center=True)

        # Split panel into list (left 55%) + preview (right 45%)
        list_w = int(panel.width * 0.55)
        list_rect = pygame.Rect(panel.left + 16, panel.top + 60,
                                list_w, panel.height - 80)
        preview_rect = pygame.Rect(panel.left + list_w + 32, panel.top + 60,
                                   panel.width - list_w - 48,
                                   panel.height - 80)
        y = list_rect.top
        for i, key in enumerate(HUB_GUN_ORDER):
            spec = WEAPONS[key]
            owned = key in self.save["owned_guns"]
            if owned:
                right = "ĐÃ SỞ HỮU"
                afford = False
            else:
                right = f"{spec['price']}$"
                afford = self.save["gold"] >= spec["price"]
            sub = (f"DMG {spec['damage']}  ROF {spec['fire_rate']:.1f}"
                   f"  MAG {spec['mag']}")
            self._draw_row(surf, list_rect.left, y, list_rect.width, 56,
                           spec["name"], sub, right,
                           selected=(self.row == i),
                           color=spec["color"], afford=afford)
            y += 64

        # Preview panel for the currently selected weapon
        pygame.draw.rect(surf, (16, 24, 20), preview_rect)
        pygame.draw.rect(surf, (40, 60, 50), preview_rect, 2)
        sel_key = HUB_GUN_ORDER[self.row]
        sel = WEAPONS[sel_key]
        draw_text(surf, sel["name"],
                  (preview_rect.centerx, preview_rect.top + 16),
                  size=22, color=GOLD, bold=True, center=True)

        # Gun image (real pixel art)
        gimg = get_gun_preview(sel_key)
        char_y = preview_rect.top + 56
        if gimg is not None:
            gx = preview_rect.centerx - gimg.get_width() // 2
            gy = preview_rect.top + 48
            surf.blit(gimg, (gx, gy))
            char_y = gy + gimg.get_height() + 8

        # Character holding the gun
        cimg = get_grab_preview(sel_key)
        if cimg is not None:
            cx = preview_rect.centerx - cimg.get_width() // 2
            cy_pos = min(preview_rect.bottom - cimg.get_height() - 80,
                         char_y)
            surf.blit(cimg, (cx, cy_pos))

        # Stat lines at the bottom
        stat_y = preview_rect.bottom - 72
        for line in (
            f"Damage: {sel['damage']}",
            f"Fire Rate: {sel['fire_rate']:.1f} RPS",
            f"Magazine: {sel['mag']}",
        ):
            draw_text(surf, line,
                      (preview_rect.centerx, stat_y),
                      size=16, color=(220, 220, 220), bold=True,
                      center=True)
            stat_y += 22

    def _draw_pet_panel(self, surf, panel):
        draw_text(surf,
                  "Mua pet — pet đi theo bạn vào mọi level và đánh enemy",
                  (panel.centerx, panel.top + 24), size=18,
                  color=(220, 220, 220), bold=True, center=True)
        y = panel.top + 60
        for i, key in enumerate(PET_ORDER):
            spec = PETS[key]
            owned = key in self.save["owned_pets"]
            equipped = (self.save.get("equipped_pet") == key)
            if equipped:
                right = "ĐANG DÙNG"
                afford = False
            elif owned:
                right = "TRANG BỊ"
                afford = True
            else:
                right = f"{spec['price']}$"
                afford = self.save["gold"] >= spec["price"]
            sub = f"{spec['emoji']}  {spec['desc']}"
            self._draw_row(surf, panel.left + 24, y, panel.width - 48, 70,
                           spec["name"], sub, right,
                           selected=(self.row == i),
                           color=spec["color"], afford=afford)
            y += 82
        # "Không dùng pet" row
        none_idx = len(PET_ORDER)
        none_sel = (self.row == none_idx)
        is_none = self.save.get("equipped_pet") is None
        right = "ĐANG DÙNG" if is_none else "BỎ PET"
        self._draw_row(surf, panel.left + 24, y, panel.width - 48, 60,
                       "Không dùng pet", "Chơi một mình", right,
                       selected=none_sel, color=(120, 120, 130),
                       afford=not is_none)

    def _draw_play_panel(self, surf, panel):
        draw_text(surf, "Sẵn sàng chiến đấu?",
                  (panel.centerx, panel.top + 60), size=34,
                  color=(255, 255, 255), bold=True, center=True)
        # owned summary
        lines = [
            f"Súng sở hữu: {len(self.save['owned_guns'])}/"
            f"{1 + len(HUB_GUN_ORDER)}",
            f"Pet: {len(self.save['owned_pets'])}/{len(PET_ORDER)}"
            f"   |   Đang dùng: "
            f"{PETS[self.save['equipped_pet']]['name'] if self.save.get('equipped_pet') else 'không có'}",
            f"Level đã clear: {self.save['best_level']}/4",
        ]
        for i, line in enumerate(lines):
            draw_text(surf, line,
                      (panel.centerx, panel.top + 130 + i * 36),
                      size=20, color=(220, 230, 220),
                      bold=True, center=True)

        # Big play button
        btn = pygame.Rect(panel.centerx - 220, panel.bottom - 140, 440, 90)
        pulse = (math.sin(self.t * 3) + 1) / 2
        col = (int(GRAB_GREEN[0] + pulse * 30),
               int(GRAB_GREEN[1] + pulse * 30),
               int(GRAB_GREEN[2] + pulse * 20))
        pygame.draw.rect(surf, col, btn)
        pygame.draw.rect(surf, GOLD if self.row == 0 else (20, 30, 24),
                         btn, 5 if self.row == 0 else 2)
        draw_text(surf, "BẮT ĐẦU CHƠI", btn.center, size=36,
                  color=(10, 30, 16), bold=True, center=True)


# ============================================================
# Apply hub upgrades to a Player + spawn pet
# ============================================================
def apply_upgrades_to_player(player, save: dict):
    """Apply persistent character upgrades to a freshly initialised player.

    This is called once per level load. The player object must be the live
    instance so we can mutate hp/max_hp/etc.
    """
    from settings import (
        PLAYER_MAX_HP, PLAYER_WALK_SPEED, PLAYER_RUN_SPEED,
        PLAYER_BIKE_SPEED, STAMINA_MAX,
    )
    up = save.get("upgrades", {})
    player.upgrade_speed_mult = 1.0 + up.get("speed", 0) * CHAR_UPGRADES["speed"]["per_level"]
    player.upgrade_fr_mult = 1.0 + up.get("fire_rate", 0) * CHAR_UPGRADES["fire_rate"]["per_level"]
    player.upgrade_dmg_mult = 1.0 + up.get("damage", 0) * CHAR_UPGRADES["damage"]["per_level"]
    player.max_hp = int(PLAYER_MAX_HP + up.get("max_hp", 0) * CHAR_UPGRADES["max_hp"]["per_level"])
    player.max_stamina = int(STAMINA_MAX + up.get("stamina", 0) * CHAR_UPGRADES["stamina"]["per_level"])
    player.hp = min(player.hp, player.max_hp) if player.hp > 0 else player.max_hp
    player.stamina = player.max_stamina
