#!/usr/bin/env python3
"""
visualizer.py (v12) - сетевая песочница ISP Simulator.

НОВОЕ v12:
  - Подписи портов (label) + окна Config (SwitchConfigWindow/RouterConfigWindow).
  - MAX_CABLE_TILES = 30: длинный кабель создаётся, но signal_ok=False (красный).
  - Маршрутизация клавиатуры: ввод текста не вызывает игровые хоткеи.
"""

import argparse
import json
import math
import sys
from collections import deque

import pygame

from ui_windows import UIWindowManager

TILE = 8
PANEL_H = 60
START_BUDGET = 15000

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.1

SCISSORS_HIT_DIST = 1.5
MAX_CABLE_TILES = 30          # 30 тайлов = 150 метров

COLOR_BG = (30, 30, 30)
COLOR_GRASS = (100, 200, 100)
COLOR_ROAD = (60, 60, 60)
COLOR_HOUSE = (255, 255, 0)
COLOR_POLE = (0, 100, 0)
COLOR_DC = (255, 0, 0)
COLOR_EQUIP = (0, 150, 255)
COLOR_EQUIP_EDGE = (0, 70, 130)

COLOR_CABLE_100M = (0, 170, 0)
COLOR_CABLE_1G = (0, 200, 255)
COLOR_CABLE_ERROR = (255, 0, 0)          # кабель длиннее MAX_CABLE_TILES
COLOR_CABLE_NO_ROUTE = (255, 100, 100)
COLOR_SELECTED = (255, 255, 255)
COLOR_SCISSORS = (200, 200, 200)

COLOR_PANEL = (40, 40, 40)
COLOR_BTN = (80, 80, 80)
COLOR_BTN_ACTIVE = (60, 170, 60)
COLOR_BTN_EDGE = (150, 150, 150)
COLOR_TEXT = (255, 255, 255)

TERRAIN_COLORS = {
    "road": COLOR_ROAD,
    "house": COLOR_HOUSE,
    "datacenter": COLOR_DC,
}

TILE_NAMES = {
    "grass": "траву",
    "road": "дорогу",
    "datacenter": "ЦОД",
    "house": "дом",
    "power_line": "столб ЛЭП",
}

EQUIP_INFO = {
    "router": {"name": "Роутер", "prep": "Роутере"},
    "switch_12": {"name": "Свитч 12p", "prep": "Свитче 12p"},
    "switch_24": {"name": "Свитч 24p", "prep": "Свитче 24p"},
}

TOOLS = [
    {"kind": "cable", "type": "cable_100", "name": "Кабель 100Мб",
     "label": "Кабель 100Мб (5м/тайл)", "rate": 5, "color": COLOR_CABLE_100M,
     "accent": (0, 170, 0)},
    {"kind": "cable", "type": "cable_1000", "name": "Кабель 1Гб",
     "label": "Кабель 1Гб (10м/тайл)", "rate": 10, "color": COLOR_CABLE_1G,
     "accent": (0, 180, 230)},
    {"kind": "equipment", "type": "switch_12", "name": "Свитч 12p",
     "label": "Свитч 12p (20м)", "cost": 20, "ports": 12,
     "allowed": {"house", "power_line"}, "allowed_text": "дом или столб ЛЭП",
     "accent": (90, 120, 220)},
    {"kind": "equipment", "type": "switch_24", "name": "Свитч 24p",
     "label": "Свитч 24p (35м)", "cost": 35, "ports": 24,
     "allowed": {"house", "power_line"}, "allowed_text": "дом или столб ЛЭП",
     "accent": (130, 90, 220)},
    {"kind": "equipment", "type": "router", "name": "Роутер",
     "label": "Роутер (40м)", "cost": 40, "ports": 4,
     "allowed": {"house"}, "allowed_text": "обычный дом",
     "accent": (220, 140, 40)},
    {"kind": "scissors", "name": "Ножницы",
     "label": "Ножницы (Удалить кабель)", "color": COLOR_SCISSORS,
     "accent": (200, 70, 70)},
]

DIRS4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]


def load_map(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"Файл не найден: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"Некорректный JSON в {path}: {e}")


def find_datacenter(datacenters, tx, ty):
    for dc in datacenters:
        w = dc.get("width", 1)
        h = dc.get("height", 1)
        if dc["x"] <= tx < dc["x"] + w and dc["y"] <= ty < dc["y"] + h:
            return dc
    return None


def polyline_length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def point_to_segment_dist(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def find_cable_at_pos(tx, ty, cables):
    best = None
    best_dist = SCISSORS_HIT_DIST
    for cable in cables:
        pts = cable["points"]
        for a, b in zip(pts, pts[1:]):
            d = point_to_segment_dist(tx + 0.5, ty + 0.5,
                                     a[0] + 0.5, a[1] + 0.5,
                                     b[0] + 0.5, b[1] + 0.5)
            if d < best_dist:
                best_dist = d
                best = cable
    return best


# --- ЛЭП граф ---
def find_nearest_pole(loc_x, loc_y, power_lines):
    if not power_lines:
        return None, None
    best_pole = None
    best_dist = math.inf
    for pole in power_lines:
        px, py = pole["x"], pole["y"]
        dist = math.hypot(loc_x - px, loc_y - py)
        if dist < best_dist:
            best_dist = dist
            best_pole = pole
    return best_pole, best_dist


def find_path_in_graph(start_pole_id, end_pole_id, power_lines):
    if start_pole_id is None or end_pole_id is None:
        return None
    if start_pole_id == end_pole_id:
        return [start_pole_id]
    poles_by_id = {p["id"]: p for p in power_lines}
    if start_pole_id not in poles_by_id or end_pole_id not in poles_by_id:
        return None
    visited = set()
    queue = deque([(start_pole_id, [start_pole_id])])
    visited.add(start_pole_id)
    while queue:
        pole_id, path = queue.popleft()
        if pole_id == end_pole_id:
            return path
        pole = poles_by_id.get(pole_id)
        if not pole:
            continue
        for neighbor_id in pole.get("connected_to", []):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append((neighbor_id, path + [neighbor_id]))
    return None


def find_route_via_power_graph(eq_a_loc, eq_b_loc, power_lines):
    start_pole, _ = find_nearest_pole(eq_a_loc[0], eq_a_loc[1], power_lines)
    end_pole, _ = find_nearest_pole(eq_b_loc[0], eq_b_loc[1], power_lines)
    if start_pole is None or end_pole is None:
        return [eq_a_loc, eq_b_loc], 0, False
    path_ids = find_path_in_graph(start_pole["id"], end_pole["id"], power_lines)
    if path_ids is None:
        return [eq_a_loc, eq_b_loc], 0, False
    poles_by_id = {p["id"]: p for p in power_lines}
    points = [eq_a_loc]
    for pole_id in path_ids:
        pole = poles_by_id[pole_id]
        pole_loc = (pole["x"], pole["y"])
        if pole_loc != points[-1]:
            points.append(pole_loc)
    if points[-1] != eq_b_loc:
        points.append(eq_b_loc)
    length = polyline_length(points)
    return points, max(1, round(length)), True


# --------------------------------------------------------------------------
# КАМЕРА
# --------------------------------------------------------------------------
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

    def on_screen(self, sx, sy, margin=30):
        return (-margin <= sx <= self.view_w + margin
                and -margin <= sy <= self.view_h + margin)


# --------------------------------------------------------------------------
# ИГРОВОЕ СОСТОЯНИЕ
# --------------------------------------------------------------------------
def make_ports(count):
    return [{"free": True, "connection": None, "speed": 1000,
             "mode": "access", "vlan": 1, "label": ""} for _ in range(count)]


class Game:
    def __init__(self, data):
        self.size = data["size"]
        self.tiles = data["tiles"]
        self.houses = data["houses"]
        self.datacenters = data["datacenters"]
        self.power_lines = data["power_lines"]

        self.selected_tool = None
        self.equipment = []
        self.cables = []
        self.budget = START_BUDGET
        self.first_connection_point = None

        self.equipment_at = {}
        self._next_equipment_id = 1
        self._next_cable_id = 1

        self.ui_manager = None

        self.house_at = {}
        for h in self.houses:
            if h.get("type", "house") != "house":
                continue
            for yy in range(h["y"], h["y"] + h["height"]):
                for xx in range(h["x"], h["x"] + h["width"]):
                    self.house_at[(xx, yy)] = h

    def tile_type(self, x, y):
        return self.tiles[y][x]["type"]

    @staticmethod
    def free_ports(equip):
        return [i for i, p in enumerate(equip["ports"]) if p["free"]]

    def equipment_location(self, tx, ty):
        house = self.house_at.get((tx, ty))
        if house is not None:
            return house["x"] + house["width"] // 2, house["y"] + house["height"] // 2
        if self.tile_type(tx, ty) == "power_line":
            return tx, ty
        return None

    def equipment_by_id(self, eid):
        for e in self.equipment:
            if e["id"] == eid:
                return e
        return None

    def select_tool(self, tool):
        self.selected_tool = None if tool is self.selected_tool else tool
        self.first_connection_point = None

    def cancel(self):
        if self.ui_manager is not None and self.ui_manager.has_active():
            self.ui_manager.close_active()
            return False
        if self.first_connection_point is not None:
            self.first_connection_point = None
            print("Прокладка кабеля отменена")
            return False
        if self.selected_tool is not None:
            self.selected_tool = None
            return False
        return True

    def on_map_click(self, tx, ty):
        tool = self.selected_tool
        if tool is None:
            self.handle_info_or_window(tx, ty)
        elif tool["kind"] == "equipment":
            self.place_equipment(tool, tx, ty)
        elif tool["kind"] == "scissors":
            self.cut_cable(tx, ty)
        else:
            self.connect_click(tool, tx, ty)

    def cut_cable(self, tx, ty):
        cable = find_cable_at_pos(tx, ty, self.cables)
        if cable is None:
            return
        a = self.equipment_by_id(cable["a"])
        b = self.equipment_by_id(cable["b"])
        if a is not None:
            a["ports"][cable["port_a"]]["free"] = True
            a["ports"][cable["port_a"]]["connection"] = None
        if b is not None:
            b["ports"][cable["port_b"]]["free"] = True
            b["ports"][cable["port_b"]]["connection"] = None
        self.cables.remove(cable)
        print("Кабель перерезан. Деньги не возвращены.")

    def handle_info_or_window(self, tx, ty):
        loc = self.equipment_location(tx, ty)
        devices = self.equipment_at.get(loc, []) if loc is not None else []

        if devices:
            switches = [d for d in devices if d["type"] in ("switch_12", "switch_24")]
            routers = [d for d in devices if d["type"] == "router"]
            if switches:
                self.ui_manager.open_switch(switches)
            elif routers:
                self.ui_manager.open_router(routers)
            return

        dc = find_datacenter(self.datacenters, tx, ty)
        if dc is not None:
            self.ui_manager.open_datacenter(dc)
            return

        house = self.house_at.get((tx, ty))
        if house is not None:
            print(f"Дом ID: {house['id']}, Позиция: ({house['x']}, {house['y']}), "
                  f"Этажей: {house['floors']}, Клиентов: {house['clients']}")

    def place_equipment(self, tool, tx, ty):
        in_house = (tx, ty) in self.house_at
        tile_type = "house" if in_house else self.tile_type(tx, ty)

        if tile_type not in tool["allowed"]:
            print(f"Ошибка: {tool['name']} нельзя установить на "
                  f"{TILE_NAMES.get(tile_type, tile_type)}. Допустимо: {tool['allowed_text']}")
            return False

        loc = self.equipment_location(tx, ty)
        if not in_house and self.equipment_at.get(loc):
            print("Ошибка: на этом столбе уже стоит оборудование")
            return False

        if self.budget < tool["cost"]:
            print(f"Ошибка: недостаточно монет (нужно {tool['cost']}, есть {self.budget})")
            return False

        self.budget -= tool["cost"]
        obj = {
            "id": self._next_equipment_id,
            "type": tool["type"],
            "x": loc[0], "y": loc[1],
            "ports": make_ports(tool["ports"]),
        }
        self._next_equipment_id += 1
        self.equipment.append(obj)
        self.equipment_at.setdefault(loc, []).append(obj)
        print(f"Установлен {tool['name']} (центр: {loc})")
        return True

    def phantom_path(self, tx, ty):
        if self.first_connection_point is None:
            return None
        a = self.first_connection_point["equipment"]
        a_loc = (a["x"], a["y"])
        target = self.equipment_location(tx, ty)
        if target is None:
            target = (tx, ty)
        points, length, found = find_route_via_power_graph(a_loc, target, self.power_lines)
        return {"points": points, "length": length, "found_route": found,
                "signal_ok": length <= MAX_CABLE_TILES}

    def connect_click(self, tool, tx, ty):
        loc = self.equipment_location(tx, ty)
        devices = self.equipment_at.get(loc, []) if loc is not None else []

        if not devices:
            if self.first_connection_point is not None:
                print("Отмена: клик по пустому месту")
                self.first_connection_point = None
            else:
                print("Ошибка: на этом тайле нет оборудования")
            return False

        if self.first_connection_point is None:
            avail = [d for d in devices if self.free_ports(d)]
            if not avail:
                print("Ошибка: на этом оборудовании нет свободных портов")
                return False

            def on_first_port(device, port_index):
                self.first_connection_point = {"equipment": device, "port": port_index}
                info = EQUIP_INFO[device["type"]]
                print(f"Выбран порт {port_index + 1} на {info['prep']} #{device['id']}")

            self.ui_manager.open_port_selection(avail, False, on_first_port)
            return True

        first = self.first_connection_point
        a, port_a = first["equipment"], first["port"]
        avail = [d for d in devices if d is not a and self.free_ports(d)]
        if not avail:
            print("Ошибка: нет другого оборудования со свободными портами")
            self.first_connection_point = None
            return False

        def on_second_port(device_b, port_b):
            self._finish_cable(tool, a, port_a, device_b, port_b)

        self.ui_manager.open_port_selection(avail, True, on_second_port)
        return True

    def _finish_cable(self, tool, a, port_a, b, port_b):
        points, length, found_route = find_route_via_power_graph(
            (a["x"], a["y"]), (b["x"], b["y"]), self.power_lines)

        if not found_route:
            print("Ошибка: НЕТ ПУТИ ПО СЕТИ ЛЭП между этими устройствами")
            self.first_connection_point = None
            return False

        cost = length * tool["rate"]
        if self.budget < cost:
            print(f"Ошибка: недостаточно монет (нужно {cost}, есть {self.budget})")
            self.first_connection_point = None
            return False

        cable_speed = 100 if tool["type"] == "cable_100" else 1000

        # сигнал ok?
        signal_ok = length <= MAX_CABLE_TILES
        if not signal_ok:
            print(f"⚠️ ВНИМАНИЕ: длина кабеля {length} тайл. > {MAX_CABLE_TILES} "
                  f"({MAX_CABLE_TILES * 5}м). Кабель проложен, но СИГНАЛ ПОТЕРЯН!")

        # кабель физически создаётся в любом случае
        self.budget -= cost
        a["ports"][port_a]["free"] = False
        a["ports"][port_a]["connection"] = {"to_id": b["id"], "to_port": port_b}
        a["ports"][port_a]["speed"] = cable_speed
        b["ports"][port_b]["free"] = False
        b["ports"][port_b]["connection"] = {"to_id": a["id"], "to_port": port_a}
        b["ports"][port_b]["speed"] = cable_speed

        cable = {
            "id": self._next_cable_id,
            "type": tool["type"],
            "a": a["id"], "port_a": port_a,
            "b": b["id"], "port_b": port_b,
            "points": points,
            "length": length,
            "cost": cost,
            "signal_ok": signal_ok,
        }
        self._next_cable_id += 1
        self.cables.append(cable)
        self.first_connection_point = None

        status = "OK" if signal_ok else "СИГНАЛ ПОТЕРЯН"
        print(f"Проложен {tool['name']}: {EQUIP_INFO[a['type']]['name']} #{a['id']} "
              f"(порт {port_a + 1}) - {EQUIP_INFO[b['type']]['name']} #{b['id']} "
              f"(порт {port_b + 1}), {length} тайл., стоимость {cost}, {status}")
        return True


# --------------------------------------------------------------------------
# ОТРИСОВКА
# --------------------------------------------------------------------------
def _vgrad_rect_vis(surface, rect, top_color, bot_color, radius=6):
    tmp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    h = max(1, rect.height)
    for i in range(h):
        t = i / h
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
        pygame.draw.line(tmp, (r, g, b), (0, i), (rect.width, i))
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255),
                     (0, 0, rect.width, rect.height), border_radius=radius)
    tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(tmp, (rect.x, rect.y))


def render_terrain(data):
    size = data["size"]
    surface = pygame.Surface((size * TILE, size * TILE))
    surface.fill(COLOR_GRASS)
    for y, row in enumerate(data["tiles"]):
        for x, tile in enumerate(row):
            t = tile["type"]
            if t == "power_line":
                continue
            color = TERRAIN_COLORS.get(t)
            if color is not None:
                pygame.draw.rect(surface, color, (x * TILE, y * TILE, TILE, TILE))
    return surface


def draw_terrain(screen, terrain, cam):
    z = cam.zoom
    wx0 = max(0.0, -cam.ox / z)
    wy0 = max(0.0, -cam.oy / z)
    wx1 = min(float(cam.map_px), (cam.view_w - cam.ox) / z)
    wy1 = min(float(cam.map_px), (cam.view_h - cam.oy) / z)
    if wx1 <= wx0 or wy1 <= wy0:
        return
    sx0, sy0 = int(math.floor(wx0)), int(math.floor(wy0))
    sx1, sy1 = int(math.ceil(wx1)), int(math.ceil(wy1))
    sub = terrain.subsurface((sx0, sy0, sx1 - sx0, sy1 - sy0))
    dw = max(1, int(round((sx1 - sx0) * z)))
    dh = max(1, int(round((sy1 - sy0) * z)))
    scaled = pygame.transform.scale(sub, (dw, dh))
    screen.blit(scaled, (int(round(sx0 * z + cam.ox)), int(round(sy0 * z + cam.oy))))


def draw_poles(screen, game, cam):
    z = cam.zoom
    radius = max(1, int(round(2 * z)))
    stick = max(2, int(round(3 * z)))
    for y in range(game.size):
        for x in range(game.size):
            if game.tile_type(x, y) == "power_line":
                cx, cy = cam.tile_center(x, y)
                if not cam.on_screen(cx, cy):
                    continue
                pygame.draw.line(screen, COLOR_POLE, (cx, cy), (cx, cy - stick), max(1, int(z)))
                pygame.draw.circle(screen, COLOR_POLE, (cx, cy), radius)


def draw_cables(screen, game, cam):
    tool_colors = {t["type"]: t["color"] for t in TOOLS if t.get("kind") == "cable"}
    base_w = max(2, int(round(2 * cam.zoom)))
    err_w = max(3, int(round(3 * cam.zoom)))
    for cable in game.cables:
        if not cable.get("signal_ok", True):
            color = COLOR_CABLE_ERROR
            width = err_w
        else:
            color = tool_colors.get(cable["type"], COLOR_CABLE_1G)
            width = base_w
        pts = [cam.tile_center(x, y) for x, y in cable["points"]]
        if len(set(pts)) == 1:
            pygame.draw.circle(screen, color, pts[0], max(4, int(round(9 * cam.zoom))), width)
        else:
            pygame.draw.lines(screen, color, False, pts, width)


def draw_dashed_line(surface, color, start, end, dash_length=6):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    distance = math.hypot(dx, dy)
    if distance == 0:
        return
    dx_norm = dx / distance
    dy_norm = dy / distance
    current_dist = 0
    on = True
    while current_dist < distance:
        next_dist = min(current_dist + dash_length, distance)
        xs = x1 + dx_norm * current_dist
        ys = y1 + dy_norm * current_dist
        xe = x1 + dx_norm * next_dist
        ye = y1 + dy_norm * next_dist
        if on:
            pygame.draw.line(surface, color, (int(xs), int(ys)), (int(xe), int(ye)), 2)
        on = not on
        current_dist = next_dist


def draw_phantom(screen, game, cam, mouse_pos, fonts):
    if game.first_connection_point is None or game.selected_tool is None:
        return
    if game.selected_tool["kind"] != "cable":
        return
    tx, ty = cam.screen_to_world(*mouse_pos)
    if not (0 <= tx < game.size and 0 <= ty < game.size):
        return
    phantom = game.phantom_path(tx, ty)
    if phantom is None:
        return

    length = phantom["length"]
    cost = length * game.selected_tool["rate"]
    found_route = phantom["found_route"]
    signal_ok = phantom["signal_ok"]

    if not found_route:
        color = COLOR_CABLE_NO_ROUTE
        line_style = "dashed"
        text = "НЕТ ПУТИ ПО СЕТИ ЛЭП"
        text_color = COLOR_CABLE_NO_ROUTE
    elif not signal_ok:
        color = COLOR_CABLE_ERROR
        line_style = "dashed"
        text = f"СЛИШКОМ ДЛИННО ({length} > {MAX_CABLE_TILES}) | Цена: {cost}"
        text_color = COLOR_CABLE_ERROR
    else:
        color = game.selected_tool["color"]
        line_style = "solid"
        text = f"Длина: {length} тайл. | Цена: {cost} монет"
        text_color = COLOR_TEXT

    pts = [cam.tile_center(x, y) for x, y in phantom["points"]]
    if len(pts) >= 2:
        layer = pygame.Surface((cam.view_w, cam.view_h), pygame.SRCALPHA)
        if line_style == "dashed":
            for i in range(len(pts) - 1):
                draw_dashed_line(layer, (*color, 170), pts[i], pts[i + 1], dash_length=8)
        else:
            rgba = (color[0], color[1], color[2], 150)
            w = max(2, int(round(3 * cam.zoom)))
            pygame.draw.lines(layer, rgba, False, pts, w)
        screen.blit(layer, (0, 0))
    elif len(pts) == 1:
        pygame.draw.circle(screen, color, pts[0], max(4, int(round(9 * cam.zoom))))

    font = fonts.get(16)
    draw_outlined_text(screen, font, text, (mouse_pos[0] + 14, mouse_pos[1] + 14),
                      text_color=text_color)


def hexagon_points(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * i)),
             cy + r * math.sin(math.radians(60 * i))) for i in range(6)]


class FontCache:
    def __init__(self, names):
        self.names = names
        self.cache = {}

    def get(self, size):
        if size not in self.cache:
            self.cache[size] = pygame.font.SysFont(self.names, size)
        return self.cache[size]


def draw_outlined_text(screen, font, text, pos, text_color=COLOR_TEXT):
    black = font.render(text, True, (0, 0, 0))
    colored = font.render(text, True, text_color)
    x, y = pos
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                screen.blit(black, (x + dx, y + dy))
    screen.blit(colored, (x, y))


def draw_equipment(screen, game, cam, fonts):
    groups = {}
    for e in game.equipment:
        groups.setdefault((e["x"], e["y"]), []).append(e)

    z = cam.zoom
    half = 6 * z
    mouse = pygame.mouse.get_pos()

    for (x, y), items in groups.items():
        cx, cy = cam.tile_center(x, y)
        if not cam.on_screen(cx, cy):
            continue
        if any(e["type"] == "router" for e in items):
            pts = hexagon_points(cx, cy, half)
            pygame.draw.polygon(screen, COLOR_EQUIP, pts)
            pygame.draw.polygon(screen, COLOR_EQUIP_EDGE, pts, 1)
        else:
            rect = pygame.Rect(0, 0, max(4, int(round(12 * z))), max(4, int(round(12 * z))))
            rect.center = (cx, cy)
            pygame.draw.rect(screen, COLOR_EQUIP, rect)
            pygame.draw.rect(screen, COLOR_EQUIP_EDGE, rect, 1)
        if len(items) > 1:
            font = fonts.get(max(10, min(40, int(round(14 * z)))))
            text = str(len(items))
            h = font.size(text)[1]
            draw_outlined_text(screen, font, text,
                               (int(cx + half + 2), int(cy - h / 2)))

    if game.first_connection_point is not None:
        dev = game.first_connection_point["equipment"]
        cx, cy = cam.tile_center(dev["x"], dev["y"])
        pygame.draw.circle(screen, COLOR_SELECTED, (cx, cy), max(6, int(round(10 * z))), 2)

    for (x, y), items in groups.items():
        cx, cy = cam.tile_center(x, y)
        if abs(mouse[0] - cx) <= 10 and abs(mouse[1] - cy) <= 10:
            pygame.draw.circle(screen, (255, 255, 180), (cx, cy),
                               max(8, int(round(11 * z))), 1)


def make_buttons(width, screen_h):
    n = len(TOOLS)
    margin, gap, btn_h = 10, 8, 44
    btn_w = (width - 2 * margin - gap * (n - 1)) // n
    panel_top = screen_h - PANEL_H
    y0 = panel_top + (PANEL_H - btn_h) // 2
    return [pygame.Rect(margin + i * (btn_w + gap), y0, btn_w, btn_h) for i in range(n)]


def draw_button_label(screen, font, text, rect):
    head, sep, tail = text.partition(" (")
    lines = [head] + (["(" + tail] if sep else [])
    surfaces = [font.render(line, True, COLOR_TEXT) for line in lines]
    total = sum(s.get_height() for s in surfaces)
    y = rect.centery - total // 2
    for s in surfaces:
        screen.blit(s, (rect.centerx - s.get_width() // 2, y))
        y += s.get_height()


def draw_ui(screen, font, small_font, width, screen_h, buttons, game):
    mouse = pygame.mouse.get_pos()

    text = font.render(f"Бюджет: {game.budget} монет", True, COLOR_TEXT)
    bg = pygame.Rect(6, 4, text.get_width() + 20, text.get_height() + 10)
    _vgrad_rect_vis(screen, bg, (40, 60, 40), (20, 35, 20), radius=8)
    pygame.draw.rect(screen, (90, 160, 90), bg, 1, border_radius=8)
    screen.blit(text, (16, 9))

    if game.selected_tool is not None:
        acc = game.selected_tool.get("accent", (150, 150, 150))
        info = font.render(f"Инструмент: {game.selected_tool['name']}", True, COLOR_TEXT)
        ibg = pygame.Rect(width - info.get_width() - 24, 4,
                          info.get_width() + 18, info.get_height() + 10)
        _vgrad_rect_vis(screen, ibg,
                        tuple(min(255, c + 30) for c in acc),
                        tuple(max(0, c - 40) for c in acc), radius=8)
        pygame.draw.rect(screen, (230, 230, 230), ibg, 1, border_radius=8)
        screen.blit(info, (width - info.get_width() - 16, 9))

    panel_top = screen_h - PANEL_H
    panel_rect = pygame.Rect(0, panel_top, width, PANEL_H)
    _vgrad_rect_vis(screen, panel_rect, (52, 52, 58), (32, 32, 36), radius=0)
    pygame.draw.line(screen, (90, 90, 100), (0, panel_top), (width, panel_top), 1)

    for tool, rect in zip(TOOLS, buttons):
        acc = tool.get("accent", (90, 90, 100))
        is_active = tool is game.selected_tool
        is_hover = rect.collidepoint(mouse)

        if is_active:
            top = tuple(min(255, c + 50) for c in acc)
            bot = tuple(max(0, c - 20) for c in acc)
            edge = (255, 255, 255)
        elif is_hover:
            top = tuple(min(255, c + 25) for c in acc)
            bot = tuple(max(0, c - 55) for c in acc)
            edge = (230, 230, 235)
        else:
            top = (88, 88, 96)
            bot = (58, 58, 64)
            edge = (140, 140, 150)

        _vgrad_rect_vis(screen, rect, top, bot, radius=8)
        hi = pygame.Surface((rect.width, rect.height // 2), pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 40),
                         (0, 0, rect.width, rect.height // 2),
                         border_top_left_radius=8, border_top_right_radius=8)
        screen.blit(hi, (rect.x, rect.y))
        pygame.draw.rect(screen, acc,
                         (rect.x + 6, rect.bottom - 5, rect.width - 12, 3),
                         border_radius=2)
        pygame.draw.rect(screen, edge, rect, 2 if (is_active or is_hover) else 1,
                         border_radius=8)
        draw_button_label(screen, small_font, tool["label"], rect)


# --------------------------------------------------------------------------
# ГЛАВНЫЙ ЦИКЛ
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Сетевая песочница ISP Simulator")
    parser.add_argument("--map", type=str, default="map.json",
                        help="путь к JSON-файлу карты (по умолчанию map.json)")
    args = parser.parse_args()

    data = load_map(args.map)
    game = Game(data)

    print(f"Карта загружена: {game.size}x{game.size} тайлов, "
          f"домов: {len(game.houses)}, ЦОД: {len(game.datacenters)}, "
          f"столбов ЛЭП: {len(game.power_lines)}")
    print(f"Стартовый бюджет: {game.budget} монет")
    print(f"Макс. длина кабеля без потери сигнала: {MAX_CABLE_TILES} тайл. "
          f"({MAX_CABLE_TILES * 5}м)")
    print("Управление:")
    print("  Колесо - зум (или прокрутка в окне), ПКМ+тащить - панорамирование")
    print("  ЛКМ по кнопке - инструмент, ЛКМ по карте - применить")
    print("  Кабель: клик по оборудованию -> выбор порта")
    print("  Ножницы: клик по кабелю -> перерезать")
    print("  ЛКМ по оборудованию без инструмента - окно; в нём 'Config' -> подписи")
    print("  Esc - закрыть окно / отмена / выход")

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    screen_w, screen_h = screen.get_size()
    pygame.display.set_caption("ISP Simulator - Сетевая песочница")

    names = "arial,dejavusans,liberationsans,freesans"
    font = pygame.font.SysFont(names, 18)
    small_font = pygame.font.SysFont(names, 13)
    fonts = FontCache(names)

    ui_manager = UIWindowManager(game)
    game.ui_manager = ui_manager

    terrain = render_terrain(data)
    map_px = game.size * TILE

    view_w = screen_w
    view_h = screen_h - PANEL_H

    cam = Camera(view_w, view_h, map_px)
    buttons = make_buttons(screen_w, screen_h)
    map_rect = pygame.Rect(0, 0, view_w, view_h)
    clock = pygame.time.Clock()
    dragging = False

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            # 1) СНАЧАЛА событие идёт в окна (включая ввод текста, drag, клики).
            #    Если окно поглотило событие — дальше не обрабатываем.
            if ui_manager.handle_event(event):
                continue

            # 2) ESC — только если его НЕ поглотило окно/поле ввода.
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if game.cancel():
                    running = False
                continue

            window_open = ui_manager.has_active()

            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if map_rect.collidepoint(mx, my):
                    cam.zoom_at(mx, my, event.y)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if map_rect.collidepoint(event.pos):
                    dragging = True

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                dragging = False

            elif event.type == pygame.MOUSEMOTION and dragging:
                cam.pan(event.rel[0], event.rel[1])

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if window_open:
                    continue
                mx, my = event.pos
                if my >= screen_h - PANEL_H:
                    for tool, rect in zip(TOOLS, buttons):
                        if rect.collidepoint(mx, my):
                            game.select_tool(tool)
                    continue
                tx, ty = cam.screen_to_world(mx, my)
                if 0 <= tx < game.size and 0 <= ty < game.size:
                    game.on_map_click(tx, ty)

        # --- ОТРИСОВКА ---
        screen.fill(COLOR_BG)
        screen.set_clip(map_rect)
        draw_terrain(screen, terrain, cam)
        draw_poles(screen, game, cam)
        draw_cables(screen, game, cam)
        draw_equipment(screen, game, cam, fonts)
        draw_phantom(screen, game, cam, mouse_pos, fonts)
        screen.set_clip(None)
        draw_ui(screen, font, small_font, screen_w, screen_h, buttons, game)
        ui_manager.draw(screen, font, small_font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
    
    