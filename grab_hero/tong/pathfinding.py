import pygame
import heapq
from collections import deque
from settings import TILE
import math

class Pathfinder:
    def __init__(self, world, ignore_boss_gates=False):
        self.world = world
        self.cols = world.w
        self.rows = world.h
        self.walkable = world.get_walkable_grid(ignore_boss_gates)

    def _get_neighbors(self, node, target=None):
        """Lấy các ô lân cận (Trên, Dưới, Trái, Phải) có thể đi được."""
        dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        result = []
        for dx, dy in dirs:
            nx, ny = node[0] + dx, node[1] + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                # Nếu là ô đích, cho phép đi vào kể cả khi nó là vật thể rắn (Solid)
                if (nx, ny) == target or self.walkable[ny][nx]:
                    result.append((nx, ny))
        return result

    def _reconstruct_path(self, came_from, current):
        """Truy vết ngược từ đích về điểm xuất phát để tạo thành danh sách đường đi."""
        path = []
        while current in came_from:
            # Lưu toạ độ trung tâm của ô lưới để AI đi tới giữa ô
            path.append(pygame.Vector2(current[0] * TILE + TILE // 2, current[1] * TILE + TILE // 2))
            current = came_from[current]
        path.reverse()
        return path

    def _pos_to_grid(self, pos):
        """Chuyển đổi toạ độ Pixel sang toạ độ Ô lưới (Grid)."""
        return (int(pos.x // TILE), int(pos.y // TILE))

    # ==========================================
    # 1. BREADTH-FIRST SEARCH (BFS)
    # ==========================================
    def bfs(self, start_pos, target_pos):
        start = self._pos_to_grid(start_pos)
        target = self._pos_to_grid(target_pos)
        if start == target: return []

        queue = deque([start])
        came_from = {start: None}

        while queue:
            current = queue.popleft()
            if current == target:
                return self._reconstruct_path(came_from, current)

            for next_node in self._get_neighbors(current, target):
                if next_node not in came_from:
                    queue.append(next_node)
                    came_from[next_node] = current
        return []

    # ==========================================
    # 2. DEPTH-FIRST SEARCH (DFS)
    # ==========================================
    def dfs(self, start_pos, target_pos):
        start = self._pos_to_grid(start_pos)
        target = self._pos_to_grid(target_pos)
        if start == target: return []

        stack = [start]
        came_from = {start: None}

        while stack:
            current = stack.pop() # LIFO -> Đi sâu
            if current == target:
                return self._reconstruct_path(came_from, current)

            for next_node in self._get_neighbors(current, target):
                if next_node not in came_from:
                    stack.append(next_node)
                    came_from[next_node] = current
        return []

    # ==========================================
    # 3. DIJKSTRA
    # ==========================================
    def dijkstra(self, start_pos, target_pos):
        start = self._pos_to_grid(start_pos)
        target = self._pos_to_grid(target_pos)
        if start == target: return []

        pq = [(0, start)] # (Cost, Node)
        came_from = {start: None}
        cost_so_far = {start: 0}

        while pq:
            current_cost, current = heapq.heappop(pq)
            if current == target:
                return self._reconstruct_path(came_from, current)

            for next_node in self._get_neighbors(current, target):
                tile_type = self.world.tiles[next_node[1]][next_node[0]]
                # 1 = T_ROAD_H, 4 = T_DIRT
                terrain_cost = 2
                if tile_type == 1: terrain_cost = 1
                elif tile_type == 4: terrain_cost = 3
                
                new_cost = cost_so_far[current] + terrain_cost
                if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                    cost_so_far[next_node] = new_cost
                    priority = new_cost
                    heapq.heappush(pq, (priority, next_node))
                    came_from[next_node] = current
        return []

    # ==========================================
    # 4. A-STAR (A*)
    # ==========================================
    def a_star(self, start_pos, target_pos):
        start = self._pos_to_grid(start_pos)
        target = self._pos_to_grid(target_pos)
        if start == target: return []

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1]) # Manhattan

        pq = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}

        while pq:
            _, current = heapq.heappop(pq)
            if current == target:
                return self._reconstruct_path(came_from, current)

            for next_node in self._get_neighbors(current, target):
                tile_type = self.world.tiles[next_node[1]][next_node[0]]
                terrain_cost = 2
                if tile_type == 1: terrain_cost = 1
                elif tile_type == 4: terrain_cost = 3
                
                new_cost = cost_so_far[current] + terrain_cost
                if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                    cost_so_far[next_node] = new_cost
                    priority = new_cost + heuristic(next_node, target)
                    heapq.heappush(pq, (priority, next_node))
                    came_from[next_node] = current
        return []
