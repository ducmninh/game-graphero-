new_method = '''
    def draw_waiting_room(self):
        self.screen.fill((12, 14, 28))
        for i in range(80):
            x = (i * 157 + int(self.t * 12)) % SCREEN_WIDTH
            y = (i * 83  + int(self.t * 8))  % SCREEN_HEIGHT
            pygame.draw.circle(self.screen, [(40,60,120),(30,50,100),(50,40,90)][i%3], (x, y), 1 + i%2)
        mode_map = {"journey": "Hanh Trinh", "boss_rush": "Boss Rush", "pvp": "PvP"}
        mode = getattr(self, '_waiting_room_mode', 'journey')
        mode_name = mode_map.get(mode, "??")
        import socket as _sock
        try: my_ip = _sock.gethostbyname(_sock.gethostname())
        except: my_ip = "unknown"
        col_list = [(255,100,180),(255,200,60),(100,255,180),(100,180,255),(220,100,255),(255,230,80)]
        title_str = "PHONG CUA BAN"
        char_w = 46
        tx0 = SCREEN_WIDTH//2 - len(title_str)*char_w//2
        for ci, ch in enumerate(title_str):
            draw_text(self.screen, ch, (tx0+ci*char_w+char_w//2, 55), size=52,
                      color=col_list[ci%len(col_list)], bold=True, center=True)
        bar = pygame.Rect(SCREEN_WIDTH//2-380, 100, 760, 34)
        pygame.draw.rect(self.screen, (22,28,52), bar, border_radius=8)
        pygame.draw.rect(self.screen, (80,100,160), bar, 2, border_radius=8)
        draw_text(self.screen, "IP: " + my_ip + "  |  Che do: " + mode_name + "  |  Cong: 5555",
                  bar.center, size=16, color=(170,195,240), center=True)
        n_peers = len(self.network.clients)
        peers = list(self.network.peer_data.values())
        sw, sh, gx, gy = 350, 158, 36, 20
        bx = SCREEN_WIDTH//2 - sw - gx//2
        by = 148
        positions = [(bx,by),(bx+sw+gx,by),(bx,by+sh+gy),(bx+sw+gx,by+sh+gy)]
        for idx, (sx, sy) in enumerate(positions):
            rect = pygame.Rect(sx, sy, sw, sh)
            if idx == 0:
                bg, bc, bw = (35,45,65), GOLD, 3
            elif 0 < idx <= n_peers:
                bg, bc, bw = (28,48,38), (80,220,120), 2
            else:
                bg, bc, bw = (20,24,38), (55,65,100), 2
            pygame.draw.rect(self.screen, (0,0,0), rect.move(4,4), border_radius=14)
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            pygame.draw.rect(self.screen, bc, rect, bw, border_radius=14)
            draw_text(self.screen, "SLOT " + str(idx+1), (sx+14, sy+10), size=13, color=(100,120,170))
            if idx == 0:
                bdg = pygame.Rect(sx+sw-88, sy+7, 80, 22)
                pygame.draw.rect(self.screen, GOLD, bdg, border_radius=6)
                draw_text(self.screen, "CHU PHONG", bdg.center, size=11, color=(20,15,5), bold=True, center=True)
                pygame.draw.circle(self.screen, (50,170,75), (sx+56, sy+80), 28)
                pygame.draw.circle(self.screen, (30,100,45), (sx+56, sy+80), 28, 3)
                draw_text(self.screen, "HOST", (sx+56, sy+80), size=14, color=WHITE, bold=True, center=True)
                draw_text(self.screen, "Ban (Host)", (sx+105, sy+62), size=19, color=WHITE, bold=True)
                draw_text(self.screen, "Che do: " + mode_name, (sx+105, sy+86), size=12, color=(155,155,185))
                pygame.draw.circle(self.screen, GREEN, (sx+22, sy+130), 6)
                draw_text(self.screen, "Da vao phong", (sx+36, sy+130), size=13, color=GREEN)
            elif 0 < idx <= n_peers:
                peer = peers[idx-1]
                p_id = peer.get("id","??")
                pygame.draw.circle(self.screen, (70,190,130), (sx+56, sy+80), 28)
                pygame.draw.circle(self.screen, (40,120,80),  (sx+56, sy+80), 28, 3)
                draw_text(self.screen, "P" + str(idx), (sx+56, sy+80), size=16, color=WHITE, bold=True, center=True)
                draw_text(self.screen, "Player " + str(p_id), (sx+105, sy+62), size=19, color=WHITE, bold=True)
                pygame.draw.circle(self.screen, GREEN, (sx+22, sy+130), 6)
                draw_text(self.screen, "Da ket noi", (sx+36, sy+130), size=13, color=GREEN)
            else:
                draw_text(self.screen, "DANG TRONG", rect.center, size=26, color=(55,65,100), bold=True, center=True)
                draw_text(self.screen, "Cho nguoi choi...",
                          (rect.centerx, rect.centery+30), size=14, color=(45,55,85), center=True)
        total = n_peers + 1
        cy = by + 2*sh + 2*gy + 16
        count_col = (100,255,100) if total >= 2 else GOLD
        draw_text(self.screen, str(total) + "/4 nguoi choi", (SCREEN_WIDTH//2, cy),
                  size=22, color=count_col, bold=True, center=True)
        sm = "Da du! Nhan ENTER bat dau!" if total >= 2 else "Can it nhat 2 nguoi choi de bat dau"
        draw_text(self.screen, sm, (SCREEN_WIDTH//2, cy+26), size=14,
                  color=(100,255,100) if total >= 2 else (160,160,160), center=True)
        btn_y = cy + 60
        pulse = int(180 + 40 * math.sin(self.t * 4))
        cr = pygame.Rect(SCREEN_WIDTH//2-295, btn_y, 240, 58)
        pygame.draw.rect(self.screen, (0,0,0), cr.move(4,4), border_radius=12)
        pygame.draw.rect(self.screen, (180,50,90), cr, border_radius=12)
        pygame.draw.rect(self.screen, (255,100,140), cr, 3, border_radius=12)
        draw_text(self.screen, "HUY PHONG", cr.center, size=24, color=WHITE, bold=True, center=True)
        sr = pygame.Rect(SCREEN_WIDTH//2+55, btn_y, 240, 58)
        sc = (40, min(255,130+pulse//3), 55)
        pygame.draw.rect(self.screen, (0,0,0), sr.move(4,4), border_radius=12)
        pygame.draw.rect(self.screen, sc, sr, border_radius=12)
        pygame.draw.rect(self.screen, (80,min(255,180+pulse//4),100), sr, 3, border_radius=12)
        draw_text(self.screen, "BAT DAU!", sr.center, size=26, color=WHITE, bold=True, center=True)
        draw_text(self.screen, "IP: " + my_ip + "  |  ESC: Huy phong  |  ENTER: Bat dau",
                  (SCREEN_WIDTH//2, SCREEN_HEIGHT-20), size=14, color=(75,85,115), center=True)

'''

with open(r'c:/Users/LAPTOP/Downloads/grab_hero (1)/grab_hero/tong/main.py', encoding='utf-8') as f:
    content = f.read()

target = '    def draw_host_mode_select(self):'
idx = content.find(target)
if idx == -1:
    print("TARGET NOT FOUND")
else:
    new_content = content[:idx] + new_method + content[idx:]
    with open(r'c:/Users/LAPTOP/Downloads/grab_hero (1)/grab_hero/tong/main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Done. Total lines:', new_content.count('\n'))
