import sys
sys.path.insert(0, r'c:/Users/LAPTOP/Downloads/grab_hero (1)/grab_hero/tong')

with open(r'c:/Users/LAPTOP/Downloads/grab_hero (1)/grab_hero/tong/main.py', encoding='utf-8') as f:
    content = f.read()

# Find and replace the draw_waiting_room method
start_marker = '\r\n    def draw_waiting_room(self):\r\n'
end_marker = '\r\n    def draw_host_mode_select(self):'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1:
    start_marker = '\n    def draw_waiting_room(self):\n'
    end_marker = '\n    def draw_host_mode_select(self):'
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

print(f"start_idx={start_idx}, end_idx={end_idx}")

new_method = """
    def draw_waiting_room(self):
        \"\"\"Cyberpunk-style waiting room: neon grid, vertical player cards, side panels.\"\"\"
        # === BACKGROUND: dark purple-black + neon grid ===
        self.screen.fill((8, 6, 20))
        # Animated neon grid lines
        grid_color = (30, 20, 80)
        grid_spacing = 60
        offset_x = int(self.t * 20) % grid_spacing
        offset_y = int(self.t * 10) % grid_spacing
        for x in range(-grid_spacing + offset_x, SCREEN_WIDTH + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(-grid_spacing + offset_y, SCREEN_HEIGHT + grid_spacing, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (0, y), (SCREEN_WIDTH, y), 1)

        # Floating neon orbs
        for i in range(12):
            ox = int(SCREEN_WIDTH * 0.5 + math.sin(self.t * 0.7 + i * 1.1) * 300)
            oy = int(SCREEN_HEIGHT * 0.5 + math.cos(self.t * 0.5 + i * 0.9) * 200)
            alpha = int(30 + 20 * math.sin(self.t * 2 + i))
            orb_s = pygame.Surface((40, 40), pygame.SRCALPHA)
            orb_col = [(180, 0, 255), (0, 200, 255), (255, 0, 150)][i % 3]
            pygame.draw.circle(orb_s, (*orb_col, alpha), (20, 20), 20)
            self.screen.blit(orb_s, (ox - 20, oy - 20))

        # === MODE & IP INFO ===
        mode_map = {"journey": "HANH TRINH CUU CHO", "boss_rush": "DAI CHIEN BOSS RUSH", "pvp": "DAU TRUONG PvP"}
        mode = getattr(self, '_waiting_room_mode', 'journey')
        mode_name = mode_map.get(mode, "??")
        mode_colors = {"journey": (80, 255, 180), "boss_rush": (255, 120, 30), "pvp": (255, 60, 80)}
        mode_color = mode_colors.get(mode, (200, 200, 200))

        import socket as _sock
        try: my_ip = _sock.gethostbyname(_sock.gethostname())
        except: my_ip = "unknown"

        # === TITLE (neon glow) ===
        glow_t = math.sin(self.t * 3)
        glow_r = int(200 + 55 * glow_t)
        glow_g = int(80 + 40 * math.sin(self.t * 2))
        title_col = (glow_r, glow_g, 255)
        # Glow shadow
        for offset in [(2,2),(3,3)]:
            draw_text(self.screen, "SANH CHO ONLINE",
                      (SCREEN_WIDTH//2 + offset[0], 46 + offset[1]),
                      size=54, color=(50, 0, 120), bold=True, center=True)
        draw_text(self.screen, "SANH CHO ONLINE",
                  (SCREEN_WIDTH//2, 46), size=54, color=title_col, bold=True, center=True)

        # Mode badge below title
        badge_w = 340
        badge_rect = pygame.Rect(SCREEN_WIDTH//2 - badge_w//2, 100, badge_w, 30)
        pygame.draw.rect(self.screen, (20, 10, 50), badge_rect, border_radius=6)
        pygame.draw.rect(self.screen, mode_color, badge_rect, 2, border_radius=6)
        draw_text(self.screen, "CHE DO: " + mode_name, badge_rect.center,
                  size=15, color=mode_color, bold=True, center=True)

        # === LEFT SIDE PANEL: SERVER INFO ===
        lp_rect = pygame.Rect(30, 140, 220, 380)
        pygame.draw.rect(self.screen, (10, 8, 30), lp_rect, border_radius=12)
        pygame.draw.rect(self.screen, (80, 0, 200), lp_rect, 2, border_radius=12)
        # Corner accents
        acc = 16
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.left, lp_rect.top), (lp_rect.left+acc, lp_rect.top), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.left, lp_rect.top), (lp_rect.left, lp_rect.top+acc), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.right, lp_rect.bottom), (lp_rect.right-acc, lp_rect.bottom), 3)
        pygame.draw.line(self.screen, (180, 0, 255), (lp_rect.right, lp_rect.bottom), (lp_rect.right, lp_rect.bottom-acc), 3)

        draw_text(self.screen, "SERVER INFO", (lp_rect.centerx, lp_rect.top+20),
                  size=16, color=(180, 0, 255), bold=True, center=True)
        pygame.draw.line(self.screen, (80, 0, 150), (lp_rect.left+10, lp_rect.top+38), (lp_rect.right-10, lp_rect.top+38), 1)

        n_peers = len(self.network.clients)
        total = n_peers + 1
        info_items = [
            ("IP", my_ip),
            ("CONG", "5555"),
            ("NGUOI CHOI", str(total) + "/4"),
            ("TRANG THAI", "ONLINE" if self.network.running else "OFFLINE"),
        ]
        for ii, (label, val) in enumerate(info_items):
            iy = lp_rect.top + 58 + ii * 55
            draw_text(self.screen, label, (lp_rect.left+14, iy), size=11, color=(130, 100, 200))
            val_col = (100, 255, 100) if label in ("TRANG THAI", "NGUOI CHOI") else (220, 220, 255)
            if label == "NGUOI CHOI" and total >= 2: val_col = (100, 255, 100)
            elif label == "NGUOI CHOI": val_col = GOLD
            draw_text(self.screen, val, (lp_rect.left+14, iy+18), size=15, color=val_col, bold=True)
            pygame.draw.line(self.screen, (40, 30, 80),
                             (lp_rect.left+10, iy+38), (lp_rect.right-10, iy+38), 1)

        # Scan indicator
        pulse_r = int(6 + 3 * math.sin(self.t * 6))
        scan_col = (100, 255, 100) if self.network.running else (200, 60, 60)
        pygame.draw.circle(self.screen, scan_col, (lp_rect.left+20, lp_rect.bottom-22), pulse_r)
        draw_text(self.screen, "PHAT HIEU BEACON...",
                  (lp_rect.left+34, lp_rect.bottom-22), size=11, color=scan_col)

        # === RIGHT SIDE PANEL: TIPS ===
        rp_rect = pygame.Rect(SCREEN_WIDTH - 250, 140, 220, 380)
        pygame.draw.rect(self.screen, (10, 20, 10), rp_rect, border_radius=12)
        pygame.draw.rect(self.screen, (0, 180, 100), rp_rect, 2, border_radius=12)
        acc2 = 16
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.left, rp_rect.top), (rp_rect.left+acc2, rp_rect.top), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.left, rp_rect.top), (rp_rect.left, rp_rect.top+acc2), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.right, rp_rect.bottom), (rp_rect.right-acc2, rp_rect.bottom), 3)
        pygame.draw.line(self.screen, (0, 255, 130), (rp_rect.right, rp_rect.bottom), (rp_rect.right, rp_rect.bottom-acc2), 3)

        draw_text(self.screen, "HUONG DAN", (rp_rect.centerx, rp_rect.top+20),
                  size=16, color=(0, 220, 120), bold=True, center=True)
        pygame.draw.line(self.screen, (0, 100, 60), (rp_rect.left+10, rp_rect.top+38), (rp_rect.right-10, rp_rect.top+38), 1)
        tips = [
            "1. Ban be tai game",
            "   GrabHero.exe",
            "2. Bat Radmin VPN",
            "3. Tham gia cung",
            "   mang Radmin",
            "4. Vao Multiplayer",
            "5. Chon Ket Noi",
            "6. Phat hien phong",
            "   tu dong!",
            "",
            "ENTER: Bat dau",
            "ESC:   Huy phong",
        ]
        for ti, tip in enumerate(tips):
            tc = (0, 200, 120) if tip.startswith(("ENTER", "ESC")) else (160, 220, 180)
            draw_text(self.screen, tip, (rp_rect.left+12, rp_rect.top+50+ti*24), size=12, color=tc)

        # === CENTER: 4 PLAYER CARDS (vertical 2x2 compact) ===
        cw, ch_h = 320, 140
        cgx, cgy = 20, 16
        cx_base = SCREEN_WIDTH//2 - cw - cgx//2
        cy_base = 140
        positions = [
            (cx_base, cy_base),
            (cx_base + cw + cgx, cy_base),
            (cx_base, cy_base + ch_h + cgy),
            (cx_base + cw + cgx, cy_base + ch_h + cgy),
        ]
        peers = list(self.network.peer_data.values())

        for idx, (sx, sy) in enumerate(positions):
            rect = pygame.Rect(sx, sy, cw, ch_h)
            is_host = (idx == 0)
            is_occ  = (0 < idx <= n_peers)

            # Card background gradient effect
            if is_host:
                card_bg = (18, 14, 45)
                card_border = (200, 160, 0)
                card_accent = GOLD
            elif is_occ:
                card_bg = (10, 28, 18)
                card_border = (0, 200, 100)
                card_accent = (0, 255, 130)
            else:
                card_bg = (12, 12, 22)
                card_border = (40, 35, 80)
                card_accent = (60, 55, 110)

            # Shadow
            shadow = rect.move(5, 5)
            s_surf = pygame.Surface((shadow.w, shadow.h), pygame.SRCALPHA)
            s_surf.fill((0, 0, 0, 80))
            self.screen.blit(s_surf, shadow.topleft)

            pygame.draw.rect(self.screen, card_bg, rect, border_radius=10)
            pygame.draw.rect(self.screen, card_border, rect, 2, border_radius=10)

            # Corner line accents
            ca = 12
            pygame.draw.line(self.screen, card_accent, rect.topleft, (rect.left+ca, rect.top), 2)
            pygame.draw.line(self.screen, card_accent, rect.topleft, (rect.left, rect.top+ca), 2)
            pygame.draw.line(self.screen, card_accent, rect.bottomright, (rect.right-ca, rect.bottom), 2)
            pygame.draw.line(self.screen, card_accent, rect.bottomright, (rect.right, rect.bottom-ca), 2)

            # Slot number tag
            tag_rect = pygame.Rect(rect.left+8, rect.top+8, 56, 18)
            pygame.draw.rect(self.screen, card_border, tag_rect, border_radius=4)
            draw_text(self.screen, "SLOT " + str(idx+1), tag_rect.center, size=10,
                      color=(8,6,20), bold=True, center=True)

            if is_host:
                # HOST badge
                host_tag = pygame.Rect(rect.right-72, rect.top+8, 64, 18)
                pygame.draw.rect(self.screen, GOLD, host_tag, border_radius=4)
                draw_text(self.screen, "HOST", host_tag.center, size=10,
                          color=(20,15,5), bold=True, center=True)
                # Avatar hex shape (simulate with polygon)
                av_cx, av_cy = rect.left + 52, rect.centery + 4
                av_r = 26
                hex_pts = [(int(av_cx + av_r * math.cos(math.radians(a))),
                            int(av_cy + av_r * math.sin(math.radians(a)))) for a in range(0,360,60)]
                pygame.draw.polygon(self.screen, (50, 40, 10), hex_pts)
                pygame.draw.polygon(self.screen, GOLD, hex_pts, 2)
                draw_text(self.screen, "H", (av_cx, av_cy), size=22, color=GOLD, bold=True, center=True)
                # Info
                draw_text(self.screen, "Ban (Host)", (rect.left+94, rect.top+36), size=17, color=WHITE, bold=True)
                draw_text(self.screen, mode_name[:16], (rect.left+94, rect.top+58), size=11, color=(200,160,60))
                # Status bar
                bar_rect2 = pygame.Rect(rect.left+8, rect.bottom-24, rect.width-16, 14)
                pygame.draw.rect(self.screen, (40,35,10), bar_rect2, border_radius=4)
                pygame.draw.rect(self.screen, GOLD, bar_rect2, border_radius=4)
                draw_text(self.screen, "READY - DA VAO PHONG", bar_rect2.center, size=9, color=(20,15,5), bold=True, center=True)

            elif is_occ:
                peer = peers[idx-1]
                p_id = peer.get("id", "??")
                # Avatar
                av_cx2, av_cy2 = rect.left + 52, rect.centery + 4
                hex_pts2 = [(int(av_cx2 + 26 * math.cos(math.radians(a))),
                             int(av_cy2 + 26 * math.sin(math.radians(a)))) for a in range(0,360,60)]
                pygame.draw.polygon(self.screen, (5, 30, 18), hex_pts2)
                pygame.draw.polygon(self.screen, (0, 200, 100), hex_pts2, 2)
                draw_text(self.screen, str(idx+1), (av_cx2, av_cy2), size=22, color=(0,255,130), bold=True, center=True)
                draw_text(self.screen, "Player " + str(p_id), (rect.left+94, rect.top+36), size=17, color=WHITE, bold=True)
                draw_text(self.screen, "DA KET NOI", (rect.left+94, rect.top+58), size=11, color=(0,220,120))
                bar_rect3 = pygame.Rect(rect.left+8, rect.bottom-24, rect.width-16, 14)
                pygame.draw.rect(self.screen, (5,35,18), bar_rect3, border_radius=4)
                pygame.draw.rect(self.screen, (0,200,100), bar_rect3, border_radius=4)
                draw_text(self.screen, "READY", bar_rect3.center, size=9, color=(5,20,10), bold=True, center=True)

            else:
                # Empty slot - animated scan line
                scan_y2 = rect.top + int((self.t * 50 + idx * 40) % rect.height)
                scan_surf = pygame.Surface((rect.width, 3), pygame.SRCALPHA)
                scan_surf.fill((80, 60, 180, 60))
                self.screen.blit(scan_surf, (rect.left, scan_y2))
                draw_text(self.screen, "--- TRONG ---", (rect.centerx, rect.centery-14),
                          size=18, color=(50,45,90), bold=True, center=True)
                draw_text(self.screen, "Cho nguoi choi...",
                          (rect.centerx, rect.centery+12), size=12, color=(40,38,72), center=True)

        # === BOTTOM: counter + buttons ===
        cy_btm = cy_base + 2*ch_h + 2*cgy + 10
        count_col2 = (100, 255, 100) if total >= 2 else GOLD
        count_str = str(total) + "/4 nguoi choi tham gia"
        draw_text(self.screen, count_str, (SCREEN_WIDTH//2, cy_btm),
                  size=20, color=count_col2, bold=True, center=True)

        ready_msg = ">> NHAN ENTER DE BAT DAU! <<" if total >= 2 else "Can them " + str(2-total) + " nguoi choi nua..."
        ready_col = (0, 255, 130) if total >= 2 else (160, 140, 60)
        draw_text(self.screen, ready_msg, (SCREEN_WIDTH//2, cy_btm+26), size=14, color=ready_col, center=True)

        # HUY PHONG button
        btn_y2 = cy_btm + 58
        cr2 = pygame.Rect(SCREEN_WIDTH//2 - 280, btn_y2, 210, 52)
        pygame.draw.rect(self.screen, (0,0,0), cr2.move(4,4), border_radius=10)
        for layer, (col, inset) in enumerate([((120,30,60),0),((200,50,90),2)]):
            pygame.draw.rect(self.screen, col, cr2.inflate(-inset*2,-inset*2), border_radius=10)
        pygame.draw.rect(self.screen, (255,80,130), cr2, 2, border_radius=10)
        draw_text(self.screen, "[ ESC ] HUY PHONG", cr2.center, size=18, color=WHITE, bold=True, center=True)

        # BAT DAU button (glowing)
        pulse_v = math.sin(self.t * 5)
        sr2 = pygame.Rect(SCREEN_WIDTH//2 + 70, btn_y2, 210, 52)
        pygame.draw.rect(self.screen, (0,0,0), sr2.move(4,4), border_radius=10)
        btn_g = int(180 + 50*pulse_v)
        pygame.draw.rect(self.screen, (0, int(100+40*pulse_v), 40), sr2, border_radius=10)
        pygame.draw.rect(self.screen, (0, btn_g, 80), sr2, 3, border_radius=10)
        # Glow effect
        glow_surf = pygame.Surface((sr2.w+20, sr2.h+20), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (0, btn_g, 80, int(40+20*pulse_v)),
                         (10, 10, sr2.w, sr2.h), border_radius=10)
        self.screen.blit(glow_surf, (sr2.left-10, sr2.top-10))
        draw_text(self.screen, "[ ENTER ] BAT DAU!", sr2.center, size=18, color=WHITE, bold=True, center=True)

        # Footer scan line
        pygame.draw.line(self.screen, (40, 30, 100),
                         (0, SCREEN_HEIGHT-40), (SCREEN_WIDTH, SCREEN_HEIGHT-40), 1)
        draw_text(self.screen, "IP: " + my_ip + "   PORT: 5555   |   Radmin VPN / LAN",
                  (SCREEN_WIDTH//2, SCREEN_HEIGHT-24), size=13, color=(80,70,130), center=True)

"""

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_method + content[end_idx:]
    with open(r'c:/Users/LAPTOP/Downloads/grab_hero (1)/grab_hero/tong/main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Done! Lines:", new_content.count('\n'))
else:
    print("ERROR: Markers not found!")
    print("start_idx:", start_idx, "end_idx:", end_idx)
