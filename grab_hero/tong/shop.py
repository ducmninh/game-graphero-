"""Shop screen: buy weapons + upgrade current weapon."""
from __future__ import annotations
import pygame
from utils import Vec, draw_text, draw_panel
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, WEAPONS, SHOP_LEVEL2, SHOP_LEVEL3,
    UPGRADE_DAMAGE_PRICE, UPGRADE_FIRERATE_PRICE, UPGRADE_MAG_PRICE,
    FONT_PATH, PRICE_HEAL, PRICE_ARMOR, ARMOR_AMOUNT
)
from weapons import Weapon


class Shop:
    def __init__(self, level: int):
        # level = 2 or 3
        self.level = level
        self.weapons_for_sale = SHOP_LEVEL2 if level == 2 else SHOP_LEVEL3
        self.open = False
        self.selected = 0  # 0..N-1 for weapon, then upgrade rows
        self.message = ""
        self.message_t = 0.0

    def show(self):
        self.open = True

    def hide(self):
        self.open = False

    def feedback(self, msg):
        self.message = msg
        self.message_t = 1.6

    def update(self, dt):
        if self.message_t > 0:
            self.message_t = max(0, self.message_t - dt)

    def handle(self, event, player):
        if not self.open:
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_e, pygame.K_q):
                self.hide()
                return
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                self.selected = (self.selected - 1) % self._option_count(player)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                self.selected = (self.selected + 1) % self._option_count(player)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._buy(player)

    def _option_count(self, player):
        return len(self.weapons_for_sale) + 3 + 2  # 3 upgrades + heal + armor

    def _buy(self, player):
        idx = self.selected
        n_w = len(self.weapons_for_sale)
        if idx < n_w:
            key = self.weapons_for_sale[idx]
            price = WEAPONS[key]["price"]
            if key in player.weapons:
                self.feedback("Đã sở hữu súng này")
                return
            if player.gold < price:
                self.feedback("Không đủ vàng")
                return
            player.gold -= price
            player.add_weapon(key)
            player.switch_weapon(key)
            self.feedback(f"Đã mua {WEAPONS[key]['name']}!")
        else:
            kind = idx - n_w
            w = player.weapon
            if kind == 0:
                lvl = w.dmg_lvl
                if lvl >= 3:
                    self.feedback("Đã max nâng cấp sát thương")
                    return
                price = UPGRADE_DAMAGE_PRICE[lvl]
                if player.gold < price:
                    self.feedback("Không đủ vàng")
                    return
                player.gold -= price
                w.dmg_lvl += 1
                self.feedback(f"Sát thương +30% (Lv {w.dmg_lvl})")
            elif kind == 1:
                lvl = w.fr_lvl
                if lvl >= 3:
                    self.feedback("Đã max nâng cấp tốc độ bắn")
                    return
                price = UPGRADE_FIRERATE_PRICE[lvl]
                if player.gold < price:
                    self.feedback("Không đủ vàng")
                    return
                player.gold -= price
                w.fr_lvl += 1
                self.feedback(f"Tốc độ bắn +20% (Lv {w.fr_lvl})")
            elif kind == 2:
                lvl = w.mag_lvl
                if lvl >= 3:
                    self.feedback("Đã max nâng cấp băng đạn")
                    return
                price = UPGRADE_MAG_PRICE[lvl]
                if player.gold < price:
                    self.feedback("Không đủ vàng")
                    return
                player.gold -= price
                w.mag_lvl += 1
                self.feedback(f"Băng đạn +40% (Lv {w.mag_lvl})")
            elif kind == 3:
                # Heal
                if player.hp >= player.max_hp:
                    self.feedback("Máu đã đầy")
                    return
                if player.gold < PRICE_HEAL:
                    self.feedback("Không đủ vàng")
                    return
                player.gold -= PRICE_HEAL
                player.heal(100)
                self.feedback("Đã hồi 100 máu!")
            elif kind == 4:
                # Armor
                if player.armor >= player.max_armor:
                    self.feedback("Giáp đã đầy")
                    return
                if player.gold < PRICE_ARMOR:
                    self.feedback("Không đủ vàng")
                    return
                player.gold -= PRICE_ARMOR
                player.armor = min(player.max_armor, player.armor + ARMOR_AMOUNT)
                self.feedback(f"Đã mua thêm {ARMOR_AMOUNT} giáp!")

    def draw(self, surf, player):
        if not self.open:
            return
        # Dim background
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surf.blit(dim, (0, 0))

        # Panel
        pw, ph = 720, 540
        px = (SCREEN_WIDTH - pw) // 2
        py = (SCREEN_HEIGHT - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(surf, (28, 32, 40), panel)
        pygame.draw.rect(surf, (255, 215, 0), panel, 4)
        # Title
        draw_text(surf, f"⛽ TRẠM XĂNG — SHOP NÂNG CẤP (Level {self.level})",
                  (px + pw // 2, py + 22), size=26, color=(255, 215, 0),
                  bold=True, center=True)
        draw_text(surf, f"Vàng: {player.gold}", (px + pw // 2, py + 50),
                  size=18, color=(255, 230, 90), bold=True, center=True)

        # Items
        y = py + 90
        idx = 0
        for key in self.weapons_for_sale:
            spec = WEAPONS[key]
            owned = key in player.weapons
            self._draw_row(surf, px + 30, y, pw - 60,
                           f"{spec['name']}", f"DMG {spec['damage']}  ROF {spec['fire_rate']:.1f}",
                           f"{spec['price']} $" if not owned else "ĐÃ SỞ HỮU",
                           selected=(self.selected == idx),
                           color=spec["color"],
                           afford=player.gold >= spec["price"] and not owned)
            idx += 1
            y += 56

        # Upgrades for current weapon
        y += 12
        w = player.weapon
        draw_text(surf, f"Nâng cấp súng hiện tại: {WEAPONS[w.key]['name']}",
                  (px + 30, y), size=18, color=(255, 230, 90), bold=True)
        y += 28
        for label, lvl_attr, price_list in (
            ("Sát thương +30%", "dmg_lvl", UPGRADE_DAMAGE_PRICE),
            ("Tốc độ bắn +20%", "fr_lvl", UPGRADE_FIRERATE_PRICE),
            ("Băng đạn +40%", "mag_lvl", UPGRADE_MAG_PRICE),
        ):
            lvl = getattr(w, lvl_attr)
            max_lvl = 3
            if lvl >= max_lvl:
                p = "MAX"
                afford = False
            else:
                p = f"{price_list[lvl]} $"
                afford = player.gold >= price_list[lvl]
            self._draw_row(surf, px + 30, y, pw - 60,
                           label, f"Cấp hiện tại: {lvl} / {max_lvl}",
                           p, selected=(self.selected == idx),
                           color=(180, 200, 240), afford=afford)
            idx += 1
            
        # Supplies
        y += 12
        draw_text(surf, "Vật phẩm bổ trợ:", (px + 30, y), size=18, color=(120, 255, 120), bold=True)
        y += 28
        # Heal row
        self._draw_row(surf, px + 30, y, pw - 60,
                       "Hồi máu (100 HP)", f"Máu hiện tại: {int(player.hp)} / {player.max_hp}",
                       f"{PRICE_HEAL} $", selected=(self.selected == idx),
                       color=(80, 220, 80), afford=player.gold >= PRICE_HEAL and player.hp < player.max_hp)
        y += 50
        idx += 1
        # Armor row
        self._draw_row(surf, px + 30, y, pw - 60,
                       f"Mua Giáp (+{ARMOR_AMOUNT})", f"Giáp hiện tại: {int(player.armor)} / {player.max_armor}",
                       f"{PRICE_ARMOR} $", selected=(self.selected == idx),
                       color=(140, 180, 255), afford=player.gold >= PRICE_ARMOR and player.armor < player.max_armor)
        y += 50
        idx += 1

        # Footer
        draw_text(surf, "↑/↓ chọn   ENTER/SPACE mua   ESC/E thoát",
                  (px + pw // 2, py + ph - 28), size=14,
                  color=(200, 200, 200), center=True)

        # Message
        if self.message_t > 0:
            draw_text(surf, self.message, (px + pw // 2, py + ph - 56),
                      size=18, color=(255, 230, 90), bold=True, center=True)

    def _draw_row(self, surf, x, y, w, title, sub, price,
                  selected=False, color=(255, 255, 255), afford=True):
        h = 48
        bg = (60, 60, 70) if not selected else (90, 90, 130)
        pygame.draw.rect(surf, bg, (x, y, w, h))
        border = (255, 215, 0) if selected else (30, 30, 30)
        pygame.draw.rect(surf, border, (x, y, w, h), 3)
        # color block
        pygame.draw.rect(surf, color, (x + 6, y + 8, 32, 32))
        pygame.draw.rect(surf, (0, 0, 0), (x + 6, y + 8, 32, 32), 2)
        draw_text(surf, title, (x + 50, y + 6), size=20,
                  bold=True, color=(255, 255, 255))
        draw_text(surf, sub, (x + 50, y + 26), size=14,
                  color=(200, 200, 200))
        # price right-aligned
        price_color = (255, 230, 90) if afford else (200, 100, 100)
        if price == "ĐÃ SỞ HỮU":
            price_color = (140, 200, 140)
        elif price == "MAX":
            price_color = (140, 200, 140)
        text = price
        font = pygame.font.SysFont(FONT_PATH, 22, bold=True)
        img = font.render(text, True, price_color)
        sh = font.render(text, True, (0, 0, 0))
        rect = img.get_rect(midright=(x + w - 16, y + h // 2))
        surf.blit(sh, rect.move(2, 2))
        surf.blit(img, rect)
