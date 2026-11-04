#!/usr/bin/env python3
"""
visualizer.py (v17) - сетевая песочница Telecom INC.

Рефакторинг (Этап 1):
  - константы      -> config.py
  - камера         -> camera.py
  - ЛЭП-граф/гео    -> pathfinding.py
Здесь остаётся: игровое состояние (Game), отрисовка карты, run_game.
"""

import math

import pygame

from ui_windows import UIWindowManager
from camera import Camera
from pathfinding import (
    find_datacenter,
    find_cable_at_pos,
    find_route_via_power_graph,
)
from config import (
    TILE, PANEL_H, START_BUDGET,
    MAX_CABLE_TILES,
    COLOR_BG, COLOR_GRASS, COLOR_ROAD, COLOR_HOUSE, COLOR_POLE, COLOR_DC,
    COLOR_EQUIP, COLOR_EQUIP_EDGE, COLOR_HOUSE_EQUIP_FILTER,
    COLOR_CABLE_ERROR, COLOR_CABLE_MISMATCH, COLOR_CABLE_NO_ROUTE,
    COLOR_CABLE_DC, COLOR_SELECTED, COLOR_TEXT,
    TERRAIN_COLORS, TILE_NAMES, EQUIP_INFO, TOOLS,
    FONT_NAMES,
)


# --------------------------------------------------------------------------
# СЕТЕВЫЕ ХЕЛПЕРЫ (временно здесь; на Этапе 2 уедут в network_model.py)
# --------------------------------------------------------------------------
def make_ports(count):
    return [{"free": True, "connection": None, "speed": 1000,
             "mode": "access", "vlan": 1, "label": ""} for _ in range(count)]


def _effective_port_speed(equip, port_index):
    """Эффективная скорость порта: если он в LACP — берём скорость группы."""
    for grp in equip.get("lacp_groups", []):
        if port_index in grp["ports"]:
            return grp.get("speed", 1000)
    return equip["ports"][port_index]["speed"]


def recompute_speed_mismatch(game):
    """Пересчитывает cable['speed_mismatch'] по ТЕКУЩИМ скоростям портов.
    Кабель 100Мб форсит 100 на обоих концах — у него mismatch невозможен."""
    for cable in game.cables:
        if cable.get("to_dc"):
            cable["speed_mismatch"] = False
            continue
        a = game.equipment_by_id(cable["a"])
        b = game.equipment_by_id(cable.get("b")) if cable.get("b") is not None else None
        if a is None or b is None:
            cable["speed_mismatch"] = False
            continue
        if cable["type"] == "cable_100":
            a["ports"][cable["port_a"]]["speed"] = 100
            b["ports"][cable["port_b"]]["speed"] = 100
            cable["speed_mismatch"] = False
            continue
        sa = _effective_port_speed(a, cable["port_a"])
        sb = _effective_port_speed(b, cable["port_b"])
        cable["speed_mismatch"] = (sa != sb)


# --------------------------------------------------------------------------
# ИГРОВОЕ СОСТОЯНИЕ
# --------------------------------------------------------------------------
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

    # ---- справочники ----
    def tile_type(self, x, y):
        return self.tiles[y][x]["type"]

    @staticmethod
    def free_ports(equip):
        return [i for i, p in enumerate(equip["ports"]) if p["free"]]

    def house_center(self, house):
        return (house["x"] + house["width"] // 2,
                house["y"] + house["height"] // 2)

    def equipment_location(self, tx, ty):
        house = self.house_at.get((tx, ty))
        if house is not None:
            return self.house_center(house)
        dc = find_datacenter(self.datacenters, tx, ty)
        if dc is not None:
            w = dc.get("width", 1)
            h = dc.get("height", 1)
            return dc["x"] + w // 2, dc["y"] + h // 2
        if self.tile_type(tx, ty) == "power_line":
            return tx, ty
        return None

    def equipment_by_id(self, eid):
        for e in self.equipment:
            if e["id"] == eid:
                return e
        return None

    def recompute_mismatch(self):
        recompute_speed_mismatch(self)

    # ---- выбор инструмента / отмена ----
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

    # ---- клик по карте ----
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
        b = self.equipment_by_id(cable.get("b")) if cable.get("b") is not None else None
        if a is not None:
            a["ports"][cable["port_a"]]["free"] = True
            a["ports"][cable["port_a"]]["connection"] = None
        if b is not None:
            b["ports"][cable["port_b"]]["free"] = True
            b["ports"][cable["port_b"]]["connection"] = None
        self.cables.remove(cable)
        if cable.get("to_dc"):
            print("Магистральный кабель к ЦОД перерезан.")
        else:
            print("Кабель перерезан. Деньги не возвращены.")

    def handle_info_or_window(self, tx, ty):
        dc = find_datacenter(self.datacenters, tx, ty)
        if dc is not None:
            self.ui_manager.open_datacenter(dc)
            return
        house = self.house_at.get((tx, ty))
        if house is not None:
            self.ui_manager.open_house(house)
            return
        loc = self.equipment_location(tx, ty)
        devices = self.equipment_at.get(loc, []) if loc is not None else []
        if devices:
            switches = [d for d in devices if d["type"] in ("switch_12", "switch_24")]
            routers = [d for d in devices if d["type"] == "router"]
            if switches:
                self.ui_manager.open_switch(switches)
            elif routers:
                self.ui_manager.open_router(routers)

    def place_equipment(self, tool, tx, ty):
        in_house = (tx, ty) in self.house_at
        tile_type = "house" if in_house else self.tile_type(tx, ty)

        if tile_type not in tool["allowed"]:
            print(f"Ошибка: {tool['name']} нельзя установить на "
                  f"{TILE_NAMES.get(tile_type, tile_type)}. "
                  f"Допустимо: {tool['allowed_text']}")
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
            "lacp_groups": [],
        }
        self._next_equipment_id += 1
        self.equipment.append(obj)
        self.equipment_at.setdefault(loc, []).append(obj)
        print(f"Установлен {tool['name']} (центр: {loc})")
        return True