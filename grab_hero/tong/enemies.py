"""Enemies & bosses: zombies, thieves, snipers, tigers, bosses with AI."""
from __future__ import annotations
import math
import random
import pygame
import settings
from utils import Vec, vec_from_angle, draw_text, clamp
from settings import ENEMY_DEFS, NHANVAT, SPRITES
from weapons import Bullet


def _rand_gold(rng):
    return random.randint(rng[0], rng[1])


class Enemy:
    def __init__(self, kind: str, pos: Vec):
        self.kind = kind
        spec = dict(ENEMY_DEFS[kind])
        self.spec = spec
        self.name = spec.get("name", kind.upper())
        self.max_hp = spec["hp"]
        self.hp = self.max_hp
        self.pos = Vec(pos)
        self.vel = Vec(0, 0)
        self.speed = spec["speed"]
        self.dmg = spec["dmg"]
        self.attack_range = spec["attack_range"]
        self.attack_cd_max = spec["attack_cd"]
        self.attack_cd = random.uniform(0, self.attack_cd_max)
        self.ranged = spec["ranged"]
        self.bullet_speed = spec.get("bullet_speed", 600)
        self.color = spec.get("color", (200, 80, 80))
        self.size = spec.get("size", 42)
        self.sight = spec.get("sight", 500)
        self.is_boss = spec.get("is_boss", False)
        self.alive = True
        self.hit_flash = 0.0
        self.facing = Vec(1, 0)
        self.gold_drop = spec.get("gold", (0, 0))
        self.phase = 1  # for bosses
        self.burst_left = 0
        self.summon_t = 0.0
        self.slam_cd = 3.0
        self.roar_t = 0.0
        self.knockback_t = 0.0
        self.knockback_v = Vec(0, 0)
        self.bobbing = random.uniform(0, math.tau)
        self.attack_anim_t = 0.0
        self.anim_frame = 0
        self.anim_timer = 0.0
        self.anim_speed = 0.15 # seconds per frame
        self.slash_t = 0.0 # for melee slash effect
        self.slash_angle = 0.0
        self.laser_t = 0.0
        self.laser_warn_t = 0.0
        self.laser_target = Vec(0, 0)
        self.dash_t = 0.0
        self.dash_v = Vec(0, 0)
        
        # Sprite loading system
        self.sprites = {} # {"up": [img, img...], "down": [...], ...}
        self._load_boss_sprites()

    @property
    def radius(self):
        return self.size // 2

    @property
    def rect(self) -> pygame.Rect:
        r = self.radius
        return pygame.Rect(int(self.pos.x - r), int(self.pos.y - r), 2 * r, 2 * r)

    def take_damage(self, dmg, dir_vec: Vec | None = None):
        self.hp -= dmg
        self.hit_flash = 0.18
        if dir_vec is not None and dir_vec.length() > 0.01:
            kb = 220 if not self.is_boss else 60
            self.knockback_v = dir_vec.normalize() * kb
            self.knockback_t = 0.12
        if self.hp <= 0:
            self.alive = False

    # ==================================================================
    def update(self, dt, player, world, particles, enemies, bullets, t, sounds=None):
        self.bobbing += dt * 4
        if self.hit_flash > 0:
            self.hit_flash = max(0, self.hit_flash - dt)
        if self.knockback_t > 0:
            self.knockback_t -= dt
            mv = self.knockback_v * dt
            self._try_move(mv, world)

        if self.attack_cd > 0:
            self.attack_cd = max(0, self.attack_cd - dt)
        if self.roar_t > 0:
            self.roar_t -= dt
        if self.attack_anim_t > 0:
            self.attack_anim_t -= dt
        if self.slash_t > 0:
            self.slash_t -= dt
        if self.laser_t > 0:
            self.laser_t -= dt
        if self.laser_warn_t > 0:
            self.laser_warn_t -= dt
        if self.dash_t > 0:
            self.dash_t -= dt
            self._try_move(self.dash_v * dt, world)
            
        # Update animation frame
        self.anim_timer += dt
        if self.anim_timer >= self.anim_speed:
            self.anim_timer = 0
            self.anim_frame = (self.anim_frame + 1) % 7 # Assuming 7 frames per action

        to_player = player.pos - self.pos
        dist = to_player.length()
        if dist < self.sight:
            if dist > 0.5:
                self.facing = to_player.normalize()

            # Boss behaviour first
            if self.is_boss and self.kind == "boss_final":
                self._boss_final_ai(dt, player, world, particles, enemies, bullets, dist, to_player, sounds)
                return
            if self.is_boss and self.kind == "boss2":
                self._boss2_ai(dt, player, world, particles, bullets, dist, to_player)
                return
            if self.is_boss and self.kind == "boss3":
                self._tiger_king_ai(dt, player, world, particles, bullets, dist, to_player)
                return
            if self.is_boss and self.kind == "boss4":
                self._boss4_ai(dt, player, world, particles, bullets, dist, to_player, sounds)
                return
            if self.is_boss and self.kind == "boss5":
                self._boss5_ai(dt, player, world, particles, bullets, dist, to_player, sounds)
                return
            if self.is_boss and (self.kind == "boss7" or self.kind == "boss7_ex"):
                self._behavior_boss7(dt, player, world, particles, bullets, dist, to_player, sounds)
                return
            if self.kind == "minion_smg":
                self._smg_ai(dt, player, world, particles, bullets, dist, to_player, sounds)
                return

            # Generic: ranged keeps distance & fires; melee charges
            if self.ranged:
                preferred = self.attack_range * 0.6
                if dist < self.attack_range * 0.4:
                    # back off
                    dirn = -to_player.normalize() if dist > 0.1 else Vec(0, 1)
                    mv = dirn * self.speed * dt
                    self._try_move(mv, world)
                elif dist > preferred:
                    # RANGED ENEMY: Sử dụng A* để "Vừa đi vừa bắn"
                    if not hasattr(self, "_path_timer"): self._path_timer = 0
                    if not hasattr(self, "_path"): self._path = []
                    self._path_timer -= dt
                    
                    if self._path_timer <= 0:
                        try:
                            from pathfinding import Pathfinder
                            self._path = Pathfinder(world).a_star(self.pos, player.pos)
                        except:
                            self._path = []
                        self._path_timer = 0.5
                    
                    if self._path and len(self._path) > 0:
                        dir_vec = self._path[0] - self.pos
                        if dir_vec.length() > 0.1:
                            self._try_move(dir_vec.normalize() * self.speed * dt, world)
                        if dir_vec.length() < 20:
                            self._path.pop(0)
                    else:
                        mv = to_player.normalize() * self.speed * dt
                        self._try_move(mv, world)
                        
                # fire if in range
                if dist <= self.attack_range and self.attack_cd <= 0:
                    if self.is_boss and dist < 90:
                        self._melee_slash(player, particles)
                    else:
                        self._fire_at(player, particles, bullets, sounds)
                        self.attack_cd = self.attack_cd_max
            else:
                # MELEE ENEMY: Sử dụng BFS để truy đuổi (Demo thuật toán quét diện rộng)
                if dist > self.attack_range * 0.7:
                    if not hasattr(self, "_path_timer"): self._path_timer = 0
                    if not hasattr(self, "_path"): self._path = []
                    self._path_timer -= dt
                    
                    if self._path_timer <= 0:
                        try:
                            from pathfinding import Pathfinder
                            self._path = Pathfinder(world).bfs(self.pos, player.pos)
                        except:
                            self._path = []
                        self._path_timer = 0.5
                        
                    if self._path and len(self._path) > 0:
                        dir_vec = self._path[0] - self.pos
                        if dir_vec.length() > 0.1:
                            self._try_move(dir_vec.normalize() * self.speed * dt, world)
                        if dir_vec.length() < 20:
                            self._path.pop(0)
                    else:
                        mv = to_player.normalize() * self.speed * dt
                        self._try_move(mv, world)
                # attack
                if dist <= self.attack_range and self.attack_cd <= 0:
                    if self.is_boss:
                        self._melee_slash(player, particles)
                    else:
                        player.take_damage(self.dmg)
                        particles.blood(player.pos, (220, 60, 60), 8)
                        self.attack_cd = self.attack_cd_max
                        self.attack_anim_t = 0.4
                    
            # BOSS SPECIAL PARTICLES (Moved from draw to update)
            if self.is_boss and self.kind == "boss3" and random.random() < 0.2:
                particles.add(self.pos, Vec(random.uniform(-40, 40), -100), (255, 200, 50), 0.8)
        else:
            # idle wander tiny bit
            if random.random() < 0.01:
                self.facing = vec_from_angle(random.uniform(0, math.tau))
            mv = self.facing * (self.speed * 0.2) * dt
            self._try_move(mv, world)

    # ==================================================================
    def _try_move(self, mv, world):
        new = self.pos + mv
        r = self.radius
        rx = pygame.Rect(int(new.x - r), int(self.pos.y - r), 2 * r, 2 * r)
        if not world.collides(rx):
            self.pos.x = new.x
        ry = pygame.Rect(int(self.pos.x - r), int(new.y - r), 2 * r, 2 * r)
        if not world.collides(ry):
            self.pos.y = new.y
        ww, wh = world.pixel_size()
        self.pos.x = clamp(self.pos.x, r, ww - r)
        self.pos.y = clamp(self.pos.y, r, wh - r)

    def _fire_at(self, player, particles, bullets, sounds=None):
        ang = math.atan2(player.pos.y - self.pos.y, player.pos.x - self.pos.x)
        pellets = self.spec.get("pellets", 1)
        spread = math.radians(self.spec.get("spread", 4))
        for _ in range(pellets):
            a = ang + random.uniform(-spread, spread)
            bullets.append(Bullet(
                self.pos + vec_from_angle(ang, self.radius + 6),
                a, self.bullet_speed, self.dmg, "enemy",
                color=(255, 200, 80), size=4, life=1.6,
            ))
        muzzle_pos = self.pos + vec_from_angle(ang, self.radius + 4)
        particles.muzzle(muzzle_pos, ang)

        if sounds:
            if "sniper" in self.kind and "sniper" in sounds:
                sounds["sniper"].play()
            elif "minion_smg" in self.kind and "pistol" in sounds:
                sounds["pistol"].play()
            elif "boss4" in self.kind and "ak47" in sounds:
                sounds["ak47"].play()
            elif "thief_pistol" in self.kind and "pistol" in sounds:
                sounds["pistol"].play()
            elif "shotgun" in self.kind and "ak47" in sounds:
                sounds["ak47"].play()

    def _melee_slash(self, player, particles):
        # The "Knife" slash attack
        ang = math.atan2(player.pos.y - self.pos.y, player.pos.x - self.pos.x)
        self.slash_t = 0.3
        self.slash_angle = ang
        self.attack_anim_t = 0.4
        self.attack_cd = self.attack_cd_max
        
        # Damage logic
        dist = (player.pos - self.pos).length()
        if dist < self.attack_range + 30:
            player.take_damage(self.dmg * 1.5)
            particles.blood(player.pos, (220, 60, 60), 15)
            # Knockback player
            dirn = (player.pos - self.pos).normalize() if dist > 0.1 else Vec(1, 0)
            player.pos += dirn * 40

    # ==================================================================
    # Specific AIs
    # ==================================================================
    def _smg_ai(self, dt, player, world, particles, bullets, dist, to_player, sounds=None):
        preferred = 360
        if dist > preferred:
            mv = to_player.normalize() * self.speed * dt
            self._try_move(mv, world)
        if dist <= self.attack_range:
            # burst fire
            if self.attack_cd <= 0 and self.burst_left <= 0:
                self.burst_left = self.spec.get("burst", 4)
            if self.attack_cd <= 0 and self.burst_left > 0:
                self._fire_at(player, particles, bullets, sounds)
                self.burst_left -= 1
                self.attack_cd = self.attack_cd_max if self.burst_left > 0 else 1.0

    def _boss2_ai(self, dt, player, world, particles, bullets, dist, to_player):
        # Zombie Bự Con: slow chase, slam at close
        self.slam_cd -= dt
        
        # New: If very close, use the KNIFE slash
        if dist < 80 and self.attack_cd <= 0:
            self._melee_slash(player, particles)
            return

        if dist > 64:
            mv = to_player.normalize() * self.speed * dt
            self._try_move(mv, world)
        # melee
        if dist <= self.attack_range and self.attack_cd <= 0:
            self._melee_slash(player, particles)
        # slam
        if self.slam_cd <= 0 and dist < 360:
            self.slam_cd = 4.5
            for i in range(12):
                a = i * (math.tau / 12)
                bullets.append(Bullet(
                    self.pos + vec_from_angle(a, self.radius + 4),
                    a, 320, self.dmg * 0.7, "enemy",
                    color=(120, 200, 80), size=6, life=1.0,
                ))
            particles.explosion(self.pos, color=(120, 200, 80), count=24)
            # Screen shake on slam
            player.shake = 0.5 

    def _tiger_king_ai(self, dt, player, world, particles, bullets, dist, to_player):
        # Hổ Vương: fast chase + occasional roar that does AOE
        if dist > 50:
            mv = to_player.normalize() * self.speed * dt
            self._try_move(mv, world)
        if dist <= self.attack_range and self.attack_cd <= 0:
            player.take_damage(self.dmg)
            particles.blood(player.pos, (220, 60, 60), 12)
            self.attack_cd = self.attack_cd_max
        # roar every 5s
        if self.roar_t <= 0:
            self.roar_t = 5.0
            for i in range(16):
                a = i * (math.tau / 16)
                bullets.append(Bullet(
                    self.pos + vec_from_angle(a, self.radius + 4),
                    a, 380, 12, "enemy",
                    color=(255, 100, 80), size=5, life=0.9,
                ))
            particles.explosion(self.pos, color=(255, 100, 60), count=30)
        
        # Fire Breath every 8s if in range
        if getattr(self, "fire_t", 0) <= 0 and dist < 400:
            self._fire_breath(player, bullets, particles)
            self.fire_t = 8.0
        else:
            self.fire_t = getattr(self, "fire_t", 8.0) - dt

    def _throw_energy_ball(self, player, bullets, particles, color=(255, 100, 255), size=20, speed=350):
        """Swings arm to throw a heavy energy ball."""
        self.attack_anim_t = 0.8 # Arm swing duration
        ang = math.atan2(player.pos.y - self.pos.y, player.pos.x - self.pos.x)
        from weapons import Bullet
        # Large ball with high damage and slow speed
        bullets.append(Bullet(
            self.pos + vec_from_angle(ang, self.radius + 10),
            ang, speed, self.dmg * 2.0, "enemy",
            color=color, size=size, aoe=120, life=2.5
        ))
        particles.muzzle(self.pos, ang, color)
        # Visual 'charge' effect
        for _ in range(10):
            a = random.uniform(0, math.tau)
            particles.blood(self.pos, color, 1)

    def _boss5_ai(self, dt, player, world, particles, bullets, dist, to_player, sounds=None):
        # Boss 5: Steel Juggernaut - Heavy Armor + Energy Balls
        self.attack_cd = max(0, self.attack_cd - dt)
        
        # Movement: Slow but steady chase
        if dist > 200:
            self._try_move(to_player.normalize() * self.speed * dt, world)
        elif dist < 100:
            self._try_move(-to_player.normalize() * self.speed * dt, world)

        if self.attack_cd <= 0 and dist < 800:
            # 50% chance to throw heavy ball, 50% regular spread fire
            if random.random() < 0.4:
                self._throw_energy_ball(player, bullets, particles, color=(100, 255, 200), size=25)
                self.attack_cd = 3.0
            else:
                self._fire_at(player, particles, bullets, sounds)
                self.attack_cd = 1.0

    def _boss6_ai(self, dt, player, world, particles, bullets, dist, to_player, sounds=None):
        # Boss 6: Shadow Master - Fast + Multi Ball throw
        self.attack_cd = max(0, self.attack_cd - dt)
        
        # Movement: Fast erratic movement
        if not hasattr(self, "move_t"): self.move_t = 0
        self.move_t -= dt
        if self.move_t <= 0:
            self.move_dir = to_player.rotate(random.uniform(-90, 90)).normalize()
            self.move_t = 1.0 + random.random()
        
        if dist > 300:
            self._try_move(self.move_dir * self.speed * 1.5 * dt, world)
        
        if self.attack_cd <= 0 and dist < 900:
            # Triple ball throw
            self.attack_anim_t = 1.0
            base_ang = math.atan2(to_player.y, to_player.x)
            from weapons import Bullet
            for off in (-0.4, 0, 0.4):
                bullets.append(Bullet(
                    self.pos, base_ang + off, 400, self.dmg * 1.5, "enemy",
                    color=(180, 50, 255), size=18, aoe=80, life=2.0
                ))
            self.attack_cd = 4.0
            particles.explosion(self.pos, (180, 50, 255), count=20)

    def _boss4_ai(self, dt, player, world, particles, bullets, dist, to_player, sounds=None):
        # Robot Boss: Laser + Minigun + Dash
        self.attack_cd = max(0, self.attack_cd - dt)
        
        # If dashing, don't do other AI
        if self.dash_t > 0:
            return

        # Melee counter if too close
        if dist < 100 and self.attack_cd <= 0:
            self._melee_slash(player, particles)
            return

        # Random Charge Move (Dash)
        if not hasattr(self, "charge_cd"): self.charge_cd = 4.0
        self.charge_cd -= dt
        if self.charge_cd <= 0 and 200 < dist < 500:
            self.dash_t = 0.6
            self.dash_v = to_player.normalize() * (self.speed * 2.5)
            self.charge_cd = 5.0 + random.random() * 3
            particles.muzzle(self.pos, math.atan2(to_player.y, to_player.x) + math.pi, (200, 200, 200)) # smoke puff
            return

        # Laser attack every 6 seconds
        if not hasattr(self, "laser_cd"): self.laser_cd = 6.0
        self.laser_cd -= dt
        
        if self.laser_cd <= 0 and dist < 700:
            self.laser_warn_t = 1.0
            self.laser_target = Vec(player.pos)
            self.laser_cd = 6.0
            self.attack_anim_t = 2.0
            return

        if self.laser_warn_t <= 0 and self.laser_t <= 0 and self.attack_anim_t > 0:
            if self.laser_warn_t <= 0 and not hasattr(self, "_laser_fired"):
                self.laser_t = 0.8
                self._laser_fired = True # Temp flag
        
        if self.laser_t > 0:
            # Laser damage logic
            dirn = (self.laser_target - self.pos).normalize()
            # Check if player is on the line
            to_p = player.pos - self.pos
            p_dist = to_p.length()
            if p_dist < 800:
                proj = to_p.dot(dirn)
                if proj > 0:
                    perp_dist = (to_p - dirn * proj).length()
                    if perp_dist < 25: # Laser width
                        player.take_damage(self.dmg * 0.1) # Rapid ticks
                        particles.blood(player.pos, (220, 60, 60), 2)
        else:
            if hasattr(self, "_laser_fired"): delattr(self, "_laser_fired")

        # Regular fire if not lasering
        if self.laser_warn_t <= 0 and self.laser_t <= 0:
            # Chase more aggressively
            if dist > 80:
                mv = to_player.normalize() * self.speed * dt
                self._try_move(mv, world)
            if self.attack_cd <= 0 and dist < 600:
                self._fire_at(player, particles, bullets, sounds)
                self.attack_cd = self.attack_cd_max

    def _behavior_boss7(self, dt, player, world, particles, bullets, dist, to_player, sounds=None):
        # Final Boss Logic: Umbrella Overlord
        if not hasattr(self, "_state_t"): self._state_t = 0
        if not hasattr(self, "_phase"): self._phase = 1
        self._state_t -= dt

        # Update phase
        if self.hp < self.max_hp * 0.5: self._phase = 2

        # Movement: Stays at mid-range, orbits player
        preferred = 400
        if dist > 0:
            if dist > preferred + 50:
                self._try_move(to_player.normalize() * self.speed * dt, world)
            elif dist < preferred - 50:
                self._try_move(-to_player.normalize() * self.speed * dt, world)
            else:
                # Orbit
                orbit_dir = Vec(-to_player.y, to_player.x).normalize()
                self._try_move(orbit_dir * self.speed * 0.8 * dt, world)

        # Attacks
        if self.attack_cd <= 0:
            # Pick an attack
            choice = random.random()
            if choice < 0.6:
                # Radial Burst (Umbrella spokes firing)
                for i in range(12 if self._phase == 1 else 18):
                    ang = i * (math.tau / (12 if self._phase == 1 else 18))
                    bullets.append(Bullet(self.pos, ang, 500, self.dmg, "enemy", (255, 30, 80)))
                self.attack_cd = 1.2 if self._phase == 1 else 0.8
            elif choice < 0.9:
                # Targeted Volley
                ang = math.atan2(to_player.y, to_player.x)
                for i in range(5 if self._phase == 1 else 8):
                    bullets.append(Bullet(self.pos, ang + (i - (2 if self._phase == 1 else 3.5)) * 0.1, 
                                          850, self.dmg, "enemy", (255, 30, 80)))
                self.attack_cd = 1.5 if self._phase == 1 else 1.0
            else:
                # Shield pulse / Shockwave
                self.invuln_t = 1.2 # Brief invulnerability
                for i in range(36):
                    ang = i * (math.tau / 36)
                    p_vel = vec_from_angle(ang, 400)
                    particles.add(self.pos, p_vel, (255, 30, 80), 0.6)
                # Damage player if too close
                if dist < 150:
                    player.take_damage(self.dmg * 2)
                    push_dir = to_player.normalize() if dist > 0.1 else Vec(1, 0)
                    player.pos += push_dir * 100 # Pushback
                self.attack_cd = 3.0 if self._phase == 1 else 2.0

    def _fire_breath(self, player, bullets, particles):
        # Multi-bullet stream toward player
        ang = math.atan2(player.pos.y - self.pos.y, player.pos.x - self.pos.x)
        self.attack_anim_t = 1.5 # Lock in animation
        for i in range(20):
            # delayed stream using tiny random offsets
            a = ang + random.uniform(-0.3, 0.3)
            spd = random.uniform(300, 500)
            bullets.append(Bullet(
                self.pos + vec_from_angle(ang, self.radius + 10),
                a, spd, self.dmg * 0.4, "enemy",
                color=(255, 120, 0), size=6, life=0.6,
            ))
        particles.explosion(self.pos + vec_from_angle(ang, 30), color=(255, 60, 0), count=15)

    def _boss_final_ai(self, dt, player, world, particles, enemies, bullets, dist, to_player, sounds=None):
        # 3 phases based on HP%
        pct = self.hp / self.max_hp
        new_phase = 1
        if pct < 0.66:
            new_phase = 2
        if pct < 0.33:
            new_phase = 3
        if new_phase != self.phase:
            self.phase = new_phase
            self.attack_cd_max = max(0.3, self.attack_cd_max - 0.15)
            particles.explosion(self.pos, color=(255, 80, 80), count=40, big=True)
            # spawn extras at phase transitions
            if new_phase == 2:
                from enemies import Enemy as E
                for _ in range(2):
                    a = random.uniform(0, math.tau)
                    p = self.pos + vec_from_angle(a, 220)
                    enemies.append(E("tiger", p))
            elif new_phase == 3:
                for _ in range(4):
                    a = random.uniform(0, math.tau)
                    p = self.pos + vec_from_angle(a, 240)
                    enemies.append(Enemy("minion_shotgun", p))

        # Move toward player using A* Pathfinding (Vừa đi tìm đường)
        preferred = 380 if self.phase < 3 else 240
        if dist > preferred + 60:
            if not hasattr(self, "_path_timer"): self._path_timer = 0
            if not hasattr(self, "_path"): self._path = []
            self._path_timer -= dt
            
            # Cập nhật đường đi mỗi 0.5s để không bị giật lag
            if self._path_timer <= 0:
                try:
                    from pathfinding import Pathfinder
                    pf = Pathfinder(world)
                    self._path = pf.a_star(self.pos, player.pos)
                except:
                    self._path = []
                self._path_timer = 0.5
            
            if self._path and len(self._path) > 0:
                next_pt = self._path[0]
                dir_vec = next_pt - self.pos
                if dir_vec.length() > 0.1:
                    mv = dir_vec.normalize() * self.speed * dt
                    self._try_move(mv, world)
                # Xoá điểm đến khi đã đi tới gần
                if dir_vec.length() < 20: 
                    self._path.pop(0)
            else:
                # Dự phòng khi không tìm thấy đường
                mv = to_player.normalize() * self.speed * dt
                self._try_move(mv, world)
                
        elif dist < preferred - 60:
            # Lùi lại nếu đứng quá gần
            mv = -to_player.normalize() * self.speed * dt
            self._try_move(mv, world)

        if self.attack_cd <= 0 and dist < self.attack_range:
            if dist < 90:
                self._melee_slash(player, particles)
            else:
                self._fire_at(player, particles, bullets, sounds)
            self.attack_cd = self.attack_cd_max

    # ==================================================================
    # ==================================================================
    def draw(self, surf, cam, t, particles=None):
        # Vẽ đường đi của thuật toán tìm đường để thầy giáo dễ quan sát
        if settings.SHOW_PATHFINDING and hasattr(self, "_path") and self._path and len(self._path) > 0:
            # Chuyển đổi toạ độ Pixel sang hệ trục Camera
            pts = [cam.apply(pygame.Vector2(pt)) for pt in self._path]
            pts.insert(0, cam.apply(self.pos))
            if len(pts) > 1:
                # Màu đỏ neon cho A* (Ranged), Màu xanh lá neon cho BFS (Melee)
                color = (255, 50, 50) if self.ranged else (50, 255, 50)
                # Vẽ các nét nối liền
                pygame.draw.lines(surf, color, False, pts, 2)
                # Vẽ điểm chấm tròn tại mỗi nút Grid
                for pt in pts[1:]:
                    pygame.draw.circle(surf, color, (int(pt[0]), int(pt[1])), 5)
                    pygame.draw.circle(surf, (255, 255, 255), (int(pt[0]), int(pt[1])), 2)
                    
        p = cam.apply(self.pos)
        sz = self.size
        bob = math.sin(self.bobbing) * 1.5
        # shadow
        shadow = pygame.Surface((sz, sz // 3), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 110), (0, 0, sz, sz // 3))
        surf.blit(shadow, (p[0] - sz // 2, p[1] + sz // 3))

        # main body
        if self.is_boss and self.sprites:
            self._draw_animated_boss(surf, p, bob)
        elif self.kind in ("zombie", "zombie_fast", "boss2"):
            # Fallback for old sprites or simpler enemies
            self._draw_zombie(surf, p, bob)
        elif self.kind in ("tiger", "boss3"):
            self._draw_tiger(surf, p, bob)
        elif self.kind == "wild_dog":
            self._draw_dog(surf, p, bob)
        elif self.kind == "boss_final":
            self._draw_boss_final(surf, p, bob)
        elif self.kind == "boss1":
            self._draw_boss1(surf, p, bob)
        elif self.kind in ("boss5", "boss6"):
            # Handled by _draw_animated_boss if sprites loaded
            if not self.sprites: self._draw_boss_final(surf, p, bob)
        elif self.kind in ("thief_pistol", "minion_smg", "minion_shotgun", "sniper"):
            has_gun = True
            self._draw_thief(surf, p, bob, big=False, has_gun=has_gun)
        elif self.kind == "thief_knife":
            self._draw_thief(surf, p, bob, big=False, has_gun=False)
        else:
            pygame.draw.circle(surf, self.color, (p[0], int(p[1] + bob)), self.radius)

        # Melee Slash Visual Effect
        if self.slash_t > 0:
            alpha = int(255 * (self.slash_t / 0.3))
            s = pygame.Surface((160, 160), pygame.SRCALPHA)
            # Draw a silver arc for the knife slash
            arc_rect = pygame.Rect(0, 0, 160, 160)
            start_ang = -self.slash_angle - 0.8
            end_ang = -self.slash_angle + 0.8
            pygame.draw.arc(s, (200, 220, 255, alpha), arc_rect, start_ang, end_ang, 12)
            # Add a white edge
            pygame.draw.arc(s, (255, 255, 255, alpha), arc_rect, start_ang, end_ang, 3)
            surf.blit(s, (p[0] - 80, p[1] - 80))
        
        # Fire Breath Visual
        if self.kind == "boss3" and self.attack_anim_t > 1.0:
            # Draw orange glow for fire breath
            glow_sz = int(40 + math.sin(t * 20) * 10)
            glow = pygame.Surface((glow_sz * 2, glow_sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 100, 0, 120), (glow_sz, glow_sz), glow_sz)
            ang = math.atan2(self.facing.y, self.facing.x)
            mouth_pos = (p[0] + math.cos(ang) * 30, p[1] + math.sin(ang) * 30)
            surf.blit(glow, (mouth_pos[0] - glow_sz, mouth_pos[1] - glow_sz))
            
        # Laser Visual
        if self.laser_warn_t > 0 or self.laser_t > 0:
            # Eye glow
            glow_sz = int(40 + math.sin(t * 15) * 10)
            glow = pygame.Surface((glow_sz * 2, glow_sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 0, 0, 100), (glow_sz, glow_sz), glow_sz)
            pygame.draw.circle(glow, (255, 100, 100, 180), (glow_sz, glow_sz), glow_sz // 2)
            surf.blit(glow, (p[0] - glow_sz, p[1] - glow_sz - 10)) # offset slightly up for the eye

        if self.laser_warn_t > 0:
            tp = cam.apply(self.laser_target)
            pygame.draw.line(surf, (255, 0, 0, 150), p, tp, 1)
            # small warning circle
            pygame.draw.circle(surf, (255, 0, 0), tp, 5, 1)
        if self.laser_t > 0:
            tp = cam.apply(self.laser_target)
            dirn = (self.laser_target - self.pos).normalize()
            end_pos = self.pos + dirn * 1000
            ep = cam.apply(end_pos)
            # Glow
            alpha = int(255 * (self.laser_t / 0.8))
            pygame.draw.line(surf, (255, 50, 50, alpha // 2), p, ep, 25)
            pygame.draw.line(surf, (255, 255, 255, alpha), p, ep, 8)
            # Add some sparks at the origin
            if particles:
                for _ in range(2):
                    particles.add(p, Vec(random.uniform(-50, 50), random.uniform(-50, 50)), (255, 255, 255), 0.2)

        # BOSS SPECIAL EFFECTS (Visuals only, no particles here to avoid NameError)
        if self.is_boss:
            if self.kind == "boss2":
                # Blue aura for mutant boss
                s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 100, 255, 60), (sz, sz), sz)
                surf.blit(s, (p[0] - sz, p[1] - sz))
            elif self.kind == "boss_final":
                # Rotating dark orbs for final boss
                for i in range(3):
                    ang = t * 3 + i * (math.tau / 3)
                    ox = p[0] + math.cos(ang) * (sz * 0.8)
                    oy = p[1] + math.sin(ang) * (sz * 0.8)
                    pygame.draw.circle(surf, (150, 0, 255), (int(ox), int(oy)), 8)
                    pygame.draw.circle(surf, (255, 255, 255), (int(ox), int(oy)), 3)
            
            elif self.kind == "boss7" or self.kind == "boss7_ex":
                self._draw_boss7(surf, p, bob, t)
            
            elif self.kind == "boss5":
                # Green energy field for Juggernaut
                s = pygame.Surface((sz * 3, sz * 3), pygame.SRCALPHA)
                pygame.draw.circle(s, (100, 255, 150, 50), (sz * 1.5, sz * 1.5), sz * 1.2)
                surf.blit(s, (p[0] - sz * 1.5, p[1] - sz * 1.5))
                # Ball throw arm swing visual
                if self.attack_anim_t > 0:
                    ang = math.atan2(self.facing.y, self.facing.x) + math.sin(t * 12) * 0.8
                    hand_p = (p[0] + math.cos(ang) * sz, p[1] + math.sin(ang) * sz)
                    pygame.draw.circle(surf, (100, 255, 150), hand_p, 20)
                    pygame.draw.circle(surf, (255, 255, 255), hand_p, 8)

            elif self.kind == "boss6":
                # Purple erratic shadow orbs
                for i in range(4):
                    ang = t * 4 + i * (math.tau / 4)
                    dist_orb = sz * 0.9 + math.sin(t * 5 + i) * 15
                    ox = p[0] + math.cos(ang) * dist_orb
                    oy = p[1] + math.sin(ang) * dist_orb
                    pygame.draw.circle(surf, (180, 50, 255, 120), (int(ox), int(oy)), 14)
                # Shadow ball throw visual
                if self.attack_anim_t > 0:
                    ang = t * 20
                    hand_p = (p[0] + math.cos(ang) * (sz * 1.1), p[1] + math.sin(ang) * (sz * 1.1))
                    pygame.draw.circle(surf, (255, 255, 255, 200), hand_p, 12)

        # hit flash (Muted to show boss details)
        if self.hit_flash > 0:
            s = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 255, 255, 120), (sz // 2, sz // 2), sz // 2)
            surf.blit(s, (p[0] - sz // 2, p[1] - sz // 2))

        # health bar (only show if damaged or boss)
        if self.is_boss:
            # bosses get a big bar at top of screen handled elsewhere
            pass
        elif self.hp < self.max_hp:
            bar_w = max(28, sz)
            x = p[0] - bar_w // 2
            y = p[1] - sz // 2 - 10
            pygame.draw.rect(surf, (40, 0, 0), (x, y, bar_w, 4))
            pygame.draw.rect(surf, (220, 60, 60),
                             (x, y, int(bar_w * (self.hp / self.max_hp)), 4))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _draw_boss7(self, surf, p, bob, t):
        if self.sprites.get("down"):
            self._draw_animated_boss(surf, p, bob)
            return
        cx, cy = int(p[0]), int(p[1])
        sz = self.size
        # Energy ring
        s = pygame.Surface((sz * 3, sz * 3), pygame.SRCALPHA)
        pulse = (math.sin(t * 5) + 1) * 0.5
        col = (255, 20, 60, int(30 + pulse * 40))
        pygame.draw.circle(s, col, (sz * 1.5, sz * 1.5), sz * (1.1 + pulse * 0.2), 4)
        surf.blit(s, (cx - sz * 1.5, cy - sz * 1.5))

        # Cyber Cape (glitching)
        for i in range(5):
            off_y = i * 6
            w = sz + 10 - i * 4
            h = 10
            r_off = math.sin(t * 20 + i) * 4 if random.random() > 0.8 else 0
            pygame.draw.ellipse(surf, (40, 5, 25), (cx - w // 2 + r_off, cy - sz // 4 + off_y, w, sz))

        # Umbrella Mechanical Arms (6 arms)
        for i in range(6):
            ang = t * 2 + i * (math.tau / 6)
            dist = sz * 0.8
            ax = cx + math.cos(ang) * dist
            ay = cy + math.sin(ang) * dist
            # Arm joint
            pygame.draw.line(surf, (60, 60, 70), (cx, cy), (ax, ay), 4)
            # Arm weapon head (Umbrella spoke)
            pygame.draw.circle(surf, (40, 40, 45), (int(ax), int(ay)), 12)
            pygame.draw.circle(surf, (255, 30, 80), (int(ax), int(ay)), 5) # Glowing core

        # Body
        pygame.draw.rect(surf, (30, 30, 35), (cx - sz // 3, cy - sz // 3, int(sz * 0.66), int(sz * 0.7)), border_radius=8)
        pygame.draw.rect(surf, (255, 30, 80), (cx - sz // 3, cy - sz // 3, int(sz * 0.66), int(sz * 0.7)), 2, border_radius=8)
        
        # Visor
        pygame.draw.rect(surf, (20, 20, 25), (cx - sz // 4, cy - sz // 2, sz // 2, sz // 5), border_radius=4)
        pygame.draw.line(surf, (255, 0, 50), (cx - sz // 4 + 4, cy - sz // 2 + sz // 10), 
                         (cx + sz // 4 - 4, cy - sz // 2 + sz // 10), 3)

    def _draw_boss1(self, surf, p, bob):
        if "attack" in self.sprites:
            sz = self.size
            cx, cy = p[0], int(p[1] + bob)
            # Use attack sprite if attacking (hit cooldown or animation)
            if self.attack_anim_t > 0:
                s = self.sprites["attack"][0] if self.sprites["attack"] else None
                if s and self.facing.x < 0:
                    s = pygame.transform.flip(s, True, False)
            else:
                ang = math.degrees(math.atan2(self.facing.y, self.facing.x)) % 360
                if 45 <= ang < 135:
                    s = self.sprites.get("down", [None])[0]
                elif 135 <= ang < 225:
                    s = self.sprites.get("left", [None])[0]
                elif 225 <= ang < 315:
                    s = self.sprites.get("up", [None])[0]
                else:
                    s = self.sprites.get("right", [None])[0]
            
            if s:
                img = pygame.transform.smoothscale(s, (sz, int(sz * 1.3)))
                surf.blit(img, (cx - sz // 2, cy - sz // 2 - sz // 4))
                return
        
        # Fallback to big thief
        self._draw_thief(surf, p, bob, big=True, has_gun=False)

    # ------------------------------------------------------------------
    def _draw_zombie(self, surf, p, bob):
        if "down" in self.sprites:
            sz = self.size
            cx, cy = p[0], int(p[1] + bob)
            
            # Show attack sprite if attacking
            if self.attack_anim_t > 0:
                s = self.sprites.get("attack", [None])[0]
                if s and self.facing.x < 0:
                    s = pygame.transform.flip(s, True, False)
            else:
                ang = math.degrees(math.atan2(self.facing.y, self.facing.x)) % 360
                if 45 <= ang < 135:
                    s = self.sprites.get("down", [None])[0]
                elif 135 <= ang < 225:
                    s = self.sprites.get("left", [None])[0]
                elif 225 <= ang < 315:
                    s = self.sprites.get("up", [None])[0]
                else:
                    s = self.sprites.get("right", [None])[0]
            
            if s:
                img = pygame.transform.smoothscale(s, (sz, int(sz * 1.2)))
                if self.kind == "boss2":
                    img.fill((100, 150, 255), special_flags=pygame.BLEND_RGB_MULT)
                surf.blit(img, (cx - sz // 2, cy - sz // 2))
                return

        sz = self.size
        cx, cy = p[0], int(p[1] + bob)
        # body
        body_col = self.color
        pygame.draw.ellipse(surf, body_col,
                            (cx - sz // 2, cy - sz // 3, sz, int(sz * 0.85)))
        # ragged shirt
        pygame.draw.rect(surf, (60, 50, 40),
                         (cx - sz // 3, cy, int(sz * 0.66), sz // 3))
        # head
        head_col = (
            min(255, body_col[0] + 30),
            min(255, body_col[1] + 30),
            min(255, body_col[2] + 30),
        )
        pygame.draw.circle(surf, head_col, (cx, cy - sz // 3), sz // 4)
        # eyes
        pygame.draw.circle(surf, (0, 0, 0), (cx - 5, cy - sz // 3), 3)
        pygame.draw.circle(surf, (0, 0, 0), (cx + 5, cy - sz // 3), 3)
        pygame.draw.circle(surf, (220, 50, 50), (cx - 5, cy - sz // 3), 1)
        pygame.draw.circle(surf, (220, 50, 50), (cx + 5, cy - sz // 3), 1)
        # mouth
        pygame.draw.arc(surf, (60, 0, 0),
                        (cx - 7, cy - sz // 3 + 3, 14, 8), 3.14, 0, 2)
        # arms
        ax = int(math.cos(self.bobbing) * 6)
        pygame.draw.line(surf, body_col, (cx - sz // 3, cy - 2),
                         (cx - sz // 3 - 10 + ax, cy + 6), 5)
        pygame.draw.line(surf, body_col, (cx + sz // 3, cy - 2),
                         (cx + sz // 3 + 10 - ax, cy + 6), 5)
        # outline
        pygame.draw.ellipse(surf, (0, 0, 0),
                            (cx - sz // 2, cy - sz // 3, sz, int(sz * 0.85)), 2)
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy - sz // 3), sz // 4, 2)

    def _draw_thief(self, surf, p, bob, big=False, has_gun=True):
        sz = self.size
        cx, cy = p[0], int(p[1] + bob)
        body_col = self.color
        # body
        pygame.draw.rect(surf, body_col,
                         (cx - sz // 3, cy - sz // 4, int(sz * 0.66), int(sz * 0.6)))
        pygame.draw.rect(surf, (30, 30, 30),
                         (cx - sz // 3, cy + sz // 5, int(sz * 0.66), 8))
        # head with hood (mask)
        pygame.draw.circle(surf, (30, 30, 30),
                           (cx, cy - sz // 3), sz // 4 + 2)
        pygame.draw.rect(surf, (220, 200, 180),
                         (cx - 5, cy - sz // 3 - 1, 10, 6))
        # eyes
        pygame.draw.circle(surf, (0, 0, 0), (cx - 3, cy - sz // 3), 1)
        pygame.draw.circle(surf, (0, 0, 0), (cx + 3, cy - sz // 3), 1)
        # gun or knife in facing direction
        ang = math.atan2(self.facing.y, self.facing.x)
        hx = cx + int(math.cos(ang) * (sz // 2 + 2))
        hy = cy + int(math.sin(ang) * (sz // 2 + 2))
        if has_gun:
            pygame.draw.line(surf, (40, 40, 40), (cx, cy), (hx, hy), 5)
            pygame.draw.circle(surf, (40, 40, 40), (hx, hy), 4)
        else:
            # knife: short silver line
            tx = cx + int(math.cos(ang) * sz // 2)
            ty = cy + int(math.sin(ang) * sz // 2)
            pygame.draw.line(surf, (200, 200, 220), (cx, cy), (tx, ty), 4)
            pygame.draw.line(surf, (40, 40, 40), (cx, cy), (tx, ty), 1)
        # outline
        pygame.draw.rect(surf, (0, 0, 0),
                         (cx - sz // 3, cy - sz // 4, int(sz * 0.66), int(sz * 0.6)), 2)
        if big:
            # bandana for boss1
            pygame.draw.rect(surf, (200, 30, 30),
                             (cx - sz // 4, cy - sz // 3 - 6, sz // 2, 5))

    def _draw_tiger(self, surf, p, bob):
        sz = self.size
        cx, cy = p[0], int(p[1] + bob)
        # body (orange)
        pygame.draw.ellipse(surf, self.color,
                            (cx - sz // 2, cy - sz // 4, sz, int(sz * 0.6)))
        # stripes
        for sx in (-sz // 3, -sz // 6, 0, sz // 6, sz // 3):
            pygame.draw.line(surf, (50, 30, 10),
                             (cx + sx, cy - sz // 4),
                             (cx + sx, cy + sz // 3), 3)
        # head
        pygame.draw.circle(surf, self.color, (cx, cy - sz // 4), sz // 4)
        # ears
        pygame.draw.polygon(surf, self.color, [
            (cx - sz // 5, cy - sz // 3),
            (cx - sz // 6, cy - sz // 2),
            (cx - sz // 9, cy - sz // 3),
        ])
        pygame.draw.polygon(surf, self.color, [
            (cx + sz // 9, cy - sz // 3),
            (cx + sz // 6, cy - sz // 2),
            (cx + sz // 5, cy - sz // 3),
        ])
        # eyes
        pygame.draw.circle(surf, (255, 230, 0), (cx - 5, cy - sz // 4 - 2), 3)
        pygame.draw.circle(surf, (255, 230, 0), (cx + 5, cy - sz // 4 - 2), 3)
        pygame.draw.circle(surf, (0, 0, 0), (cx - 5, cy - sz // 4 - 2), 1)
        pygame.draw.circle(surf, (0, 0, 0), (cx + 5, cy - sz // 4 - 2), 1)
        # mouth (fangs)
        pygame.draw.polygon(surf, (255, 255, 255), [
            (cx - 3, cy - sz // 4 + 4),
            (cx, cy - sz // 4 + 9),
            (cx, cy - sz // 4 + 4),
        ])
        pygame.draw.polygon(surf, (255, 255, 255), [
            (cx + 3, cy - sz // 4 + 4),
            (cx, cy - sz // 4 + 9),
            (cx, cy - sz // 4 + 4),
        ])
        # outline
        pygame.draw.ellipse(surf, (0, 0, 0),
                            (cx - sz // 2, cy - sz // 4, sz, int(sz * 0.6)), 2)
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy - sz // 4), sz // 4, 2)

    def _draw_dog(self, surf, p, bob):
        sz = self.size
        cx, cy = p[0], int(p[1] + bob)
        pygame.draw.ellipse(surf, self.color,
                            (cx - sz // 2, cy - sz // 6, sz, int(sz * 0.5)))
        pygame.draw.circle(surf, self.color, (cx + sz // 3, cy - sz // 8), sz // 5)
        # ears
        pygame.draw.polygon(surf, (90, 60, 40), [
            (cx + sz // 3, cy - sz // 4),
            (cx + sz // 3 + 4, cy - sz // 3),
            (cx + sz // 3 + 8, cy - sz // 5),
        ])
        # tail
        pygame.draw.line(surf, self.color,
                         (cx - sz // 2 + 2, cy),
                         (cx - sz // 2 - 6, cy - 8), 4)
        # eyes
        pygame.draw.circle(surf, (0, 0, 0), (cx + sz // 3 + 4, cy - sz // 8), 1)
        pygame.draw.ellipse(surf, (0, 0, 0),
                            (cx - sz // 2, cy - sz // 6, sz, int(sz * 0.5)), 2)

    def _draw_boss_final(self, surf, p, bob):
        sz = self.size
        cx, cy = p[0], int(p[1] + bob)
        # cape
        cape = pygame.Surface((sz + 16, sz), pygame.SRCALPHA)
        pygame.draw.ellipse(cape, (60, 0, 30, 220),
                            (0, sz // 4, sz + 16, sz * 3 // 4))
        surf.blit(cape, (cx - sz // 2 - 8, cy - sz // 8))
        # body
        pygame.draw.rect(surf, self.color,
                         (cx - sz // 3, cy - sz // 4,
                          int(sz * 0.66), int(sz * 0.6)))
        pygame.draw.rect(surf, (0, 0, 0),
                         (cx - sz // 3, cy - sz // 4,
                          int(sz * 0.66), int(sz * 0.6)), 2)
        # belts
        pygame.draw.line(surf, (0, 0, 0),
                         (cx - sz // 3 + 4, cy - 4),
                         (cx + sz // 3 - 4, cy - 4), 3)
        # head + skull mask
        pygame.draw.circle(surf, (240, 230, 220),
                           (cx, cy - sz // 3), sz // 4)
        pygame.draw.circle(surf, (0, 0, 0),
                           (cx - 6, cy - sz // 3 - 2), 4)
        pygame.draw.circle(surf, (0, 0, 0),
                           (cx + 6, cy - sz // 3 - 2), 4)
        pygame.draw.polygon(surf, (0, 0, 0),
                            [(cx - 4, cy - sz // 3 + 6),
                             (cx, cy - sz // 3 + 11),
                             (cx + 4, cy - sz // 3 + 6)])
        pygame.draw.circle(surf, (0, 0, 0),
                           (cx, cy - sz // 3), sz // 4, 2)
        # crown
        pygame.draw.polygon(surf, (255, 215, 0), [
            (cx - sz // 4, cy - sz // 3 - sz // 5),
            (cx - sz // 5, cy - sz // 3 - sz // 3),
            (cx - sz // 8, cy - sz // 3 - sz // 5),
            (cx, cy - sz // 3 - sz // 3 + 2),
            (cx + sz // 8, cy - sz // 3 - sz // 5),
            (cx + sz // 5, cy - sz // 3 - sz // 3),
            (cx + sz // 4, cy - sz // 3 - sz // 5),
        ])
        pygame.draw.polygon(surf, (0, 0, 0), [
            (cx - sz // 4, cy - sz // 3 - sz // 5),
            (cx - sz // 5, cy - sz // 3 - sz // 3),
            (cx - sz // 8, cy - sz // 3 - sz // 5),
            (cx, cy - sz // 3 - sz // 3 + 2),
            (cx + sz // 8, cy - sz // 3 - sz // 5),
            (cx + sz // 5, cy - sz // 3 - sz // 3),
            (cx + sz // 4, cy - sz // 3 - sz // 5),
        ], 2)
        # gun
        ang = math.atan2(self.facing.y, self.facing.x)
        hx = cx + int(math.cos(ang) * (sz // 2 + 6))
        hy = cy + int(math.sin(ang) * (sz // 2 + 6))
        pygame.draw.line(surf, (40, 40, 40), (cx, cy), (hx, hy), 7)
        pygame.draw.circle(surf, (40, 40, 40), (hx, hy), 6)
    def _draw_animated_boss(self, surf, p, bob):
        sz = int(self.size * 2.5) # Bosses from spritesheet are big
        cx, cy = p[0], int(p[1] + bob)
        
        state = "down"
        if self.attack_anim_t > 0:
            state = "attack"
        else:
            ang = math.degrees(math.atan2(self.facing.y, self.facing.x)) % 360
            if 45 <= ang < 135: state = "down"
            elif 135 <= ang < 225: state = "left"
            elif 225 <= ang < 315: state = "up"
            else: state = "right"
            
        frames = self.sprites.get(state, [])
        if not frames: return
        
        idx = self.anim_frame % len(frames)
        img = frames[idx]
        
        # Scale to boss size
        scaled = pygame.transform.smoothscale(img, (sz, sz))
        surf.blit(scaled, (cx - sz // 2, cy - sz // 2))

    def _load_boss_sprites(self):
        from settings import SPRITES
        # Determine prefix and actions
        prefix = ""
        if self.is_boss:
            if self.kind == "boss1" or self.kind == "boss1_ex": prefix = "boss1"
            elif self.kind == "boss2" or self.kind == "boss2_ex": prefix = "boss2"
            elif self.kind == "boss3" or self.kind == "boss3_ex": prefix = "boss3"
            elif self.kind == "boss4" or self.kind == "boss4_ex": prefix = "boss4"
            elif self.kind == "boss7" or self.kind == "boss7_ex": prefix = "boss7"
            
            if self.kind in ("boss5", "boss6"):
                # Custom path for level 5-6 boss
                from pathlib import Path
                base_p = NHANVAT / "BOSS" / "mafn1-2" / "man5-6"
                if base_p.exists():
                    for act in ["up", "down", "left", "right"]:
                        p = base_p / f"boss_{act}.png"
                        if p.exists():
                            try:
                                img = pygame.image.load(str(p)).convert_alpha()
                                self.sprites[act] = [img]
                            except: pass
                    return
        elif self.kind in ("zombie", "zombie_fast"):
            # Load legacy zombie sprites into the new system
            try:
                self.sprites["down"] = [pygame.image.load(str(SPRITES / "zombie_front.png")).convert_alpha()]
                self.sprites["up"] = [pygame.image.load(str(SPRITES / "zombie_back.png")).convert_alpha()]
                self.sprites["left"] = [pygame.image.load(str(SPRITES / "zombie_side.png")).convert_alpha()]
                self.sprites["attack"] = [pygame.image.load(str(SPRITES / "zombie_attack.png")).convert_alpha()]
                self.sprites["right"] = [pygame.transform.flip(self.sprites["left"][0], True, False)]
                return
            except:
                pass
        
        if not prefix: return

        actions = ["up", "down", "left", "right", "attack"]
        for act in actions:
            self.sprites[act] = []
            for i in range(7):
                path = SPRITES / f"{prefix}_{act}_{i}.png"
                if path.exists():
                        # Load and ensure black background is transparent
                        img = pygame.image.load(str(path)).convert()
                        # Auto-detect background color (usually at 0,0)
                        bg_color = img.get_at((0, 0))
                        # If color is close to white or black, treat as background
                        if sum(bg_color[:3]) > 700 or sum(bg_color[:3]) < 25:
                            img.set_colorkey(bg_color)
                        else:
                            img.set_colorkey((0, 0, 0))
                        # Then convert to alpha for better blending if needed
                        img = img.convert_alpha()
                        self.sprites[act].append(img)
                        pass
        
        # If no right sprites, flip left ones
        if not self.sprites.get("right") and self.sprites.get("left"):
            self.sprites["right"] = [pygame.transform.flip(img, True, False) for img in self.sprites["left"]]
