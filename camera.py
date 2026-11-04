
#!/usr/bin/env python3
"""
camera.py - камера мира (зум, панорамирование, преобразование координат).
"""

import math

import pygame

from config import TILE, ZOOM_MIN, ZOOM_MAX, ZOOM_STEP


class Camera:
    def __init__(self, view_w, view_h, map_px):
        self.view_w = view_w
        self.view_h = view_h
        self.map_px = map_px
        self.zoom = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.center_start()

    def center_start(self):
        scaled = self.map_px * self.zoom
        self.ox = (self.view_w - scaled) / 2.0
        self.oy = (self.view_h - scaled) / 2.0
        self.clamp()

    @staticmethod
    def _clamp_axis(off, view, scaled):
        if scaled <= view:
            return (view - scaled) / 2.0
        return min(0.0, max(view - scaled, off))

    def clamp(self):
        scaled = self.map_px * self.zoom
        self.ox = self._clamp_axis(self.ox, self.view_w, scaled)
        self.oy = self._clamp_axis(self.oy, self.view_h, scaled)

    def zoom_at(self, mx, my, steps):
        new_zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.zoom * (ZOOM_STEP ** steps)))
        wx = (mx - self.ox) / self.zoom
        wy = (my - self.oy) / self.zoom
        self.zoom = new_zoom
        self.ox = mx - wx * new_zoom
        self.oy = my - wy * new_zoom
        self.clamp()

    def pan(self, dx, dy):
        self.ox += dx
        self.oy += dy
        self.clamp()

    def screen_to_world(self, screen_x, screen_y):
        wx = (screen_x - self.ox) / self.zoom
        wy = (screen_y - self.oy) / self.zoom
        return int(math.floor(wx / TILE)), int(math.floor(wy / TILE))

    def tile_center(self, tx, ty):
        return (int(round((tx + 0.5) * TILE * self.zoom + self.ox)),
                int(round((ty + 0.5) * TILE * self.zoom + self.oy)))

    def tile_rect(self, tx, ty, w=1, h=1):
        x = int(round(tx * TILE * self.zoom + self.ox))
        y = int(round(ty * TILE * self.zoom + self.oy))
        x2 = int(round((tx + w) * TILE * self.zoom + self.ox))
        y2 = int(round((ty + h) * TILE * self.zoom + self.oy))
        return pygame.Rect(x, y, max(1, x2 - x), max(1, y2 - y))

    def on_screen(self, sx, sy, margin=30):
        return (-margin <= sx <= self.view_w + margin
                and -margin <= sy <= self.view_h + margin)
        
        