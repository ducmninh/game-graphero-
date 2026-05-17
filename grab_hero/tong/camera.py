"""Camera: world->screen transform with smooth follow + screen shake."""
from __future__ import annotations
import pygame
import random
from utils import Vec, clamp
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, SHAKE_DECAY


class Camera:
    def __init__(self, world_w: int, world_h: int):
        self.world_w = world_w
        self.world_h = world_h
        self.offset = Vec(0, 0)
        self.target = Vec(0, 0)
        self.shake = 0.0
        self.shake_offset = Vec(0, 0)

    def set_world_size(self, w, h):
        self.world_w = w
        self.world_h = h

    def follow(self, target_pos: Vec, dt: float, lerp: float = 8.0):
        self.target = Vec(target_pos.x - SCREEN_WIDTH / 2,
                          target_pos.y - SCREEN_HEIGHT / 2)
        t = min(1.0, dt * lerp)
        self.offset += (self.target - self.offset) * t
        self.offset.x = clamp(self.offset.x, 0, max(0, self.world_w - SCREEN_WIDTH))
        self.offset.y = clamp(self.offset.y, 0, max(0, self.world_h - SCREEN_HEIGHT))

        # shake
        if self.shake > 0:
            self.shake = max(0, self.shake - SHAKE_DECAY * dt)
            mag = self.shake
            self.shake_offset = Vec(random.uniform(-mag, mag),
                                    random.uniform(-mag, mag))
        else:
            self.shake_offset = Vec(0, 0)

    def add_shake(self, amount: float):
        self.shake = min(60, self.shake + amount)

    def apply(self, pos: Vec) -> tuple[int, int]:
        return (int(pos.x - self.offset.x + self.shake_offset.x),
                int(pos.y - self.offset.y + self.shake_offset.y))

    def apply_rect(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-self.offset.x + self.shake_offset.x,
                         -self.offset.y + self.shake_offset.y)

    def screen_to_world(self, sx, sy) -> Vec:
        return Vec(sx + self.offset.x - self.shake_offset.x,
                   sy + self.offset.y - self.shake_offset.y)
