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

from ui import UIWindowManager
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
    COLOR_CABLE_100M, COLOR_CABLE_1G,          # ← ДОБАВЛЕНЫ
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

    def visible_devices_at(self, loc):
        """Устройства в локации, кроме поглощённых (is_merged_into)."""
        return [d for d in self.equipment_at.get(loc, [])
                if not d.get("is_merged_into")]

    def recompute_mismatch(self):
        recompute_speed_mismatch(self)

    # ---- заглушки для совместимости (до ЧАСТИ 3) ----
    def chassis_of(self, _eid):
        return None

    def equipment_in_chassis(self, _cid):
        return []

    # ==================================================================
    # MERGE / UNMERGE
    # ==================================================================
    def _next_board_id(self, equip):
        return max((b["board_id"] for b in equip["boards"]), default=0) + 1

    def _retarget_cables(self, from_id, to_id, offset):
        for cable in self.cables:
            if cable["a"] == from_id:
                cable["a"] = to_id
                cable["port_a"] += offset
            if cable.get("b") == from_id:
                cable["b"] = to_id
                cable["port_b"] += offset

    def _shift_cables(self, equip_id, start, delta):
        for cable in self.cables:
            if cable["a"] == equip_id and cable["port_a"] >= start:
                cable["port_a"] += delta
            if (cable.get("b") == equip_id
                    and cable.get("port_b") is not None
                    and cable["port_b"] >= start):
                cable["port_b"] += delta

    def merge_equipment(self, host, other):
        if host is other:
            print("Merge: нельзя объединить с самим собой")
            return False
        # Проверяем, что оба устройства - свитчи ИЛИ оба - роутеры
        is_switch_host = host["type"] in ("switch_12", "switch_24")
        is_switch_other = other["type"] in ("switch_12", "switch_24")
        is_router_host = host["type"] == "router"
        is_router_other = other["type"] == "router"

        if not ((is_switch_host and is_switch_other) or (is_router_host and is_router_other)):
            print("Merge: нельзя объединять свитчи и роутеры вместе")
            return False
        if other.get("is_merged_into"):
            print("Merge: устройство уже объединено")
            return False
        if host.get("is_merged_into"):
            print("Merge: нельзя присоединять к поглощённому")
            return False
        if (host["x"], host["y"]) != (other["x"], other["y"]):
            print("Merge: устройства в разных локациях")
            return False

        offset = len(host["ports"])
        n = len(other["ports"])

        host["ports"].extend(other["ports"])

        host.setdefault("lacp_groups", [])
        next_lacp_id = max((g["id"] for g in host["lacp_groups"]), default=0) + 1
        for grp in other.get("lacp_groups", []):
            new_grp = dict(grp)
            new_grp["id"] = next_lacp_id
            new_grp["name"] = f"LACP-{next_lacp_id}"
            new_grp["ports"] = [p + offset for p in grp["ports"]]
            host["lacp_groups"].append(new_grp)
            next_lacp_id += 1

        new_bid = self._next_board_id(host)
        host["boards"].append({"board_id": new_bid,
                               "port_range": (offset, offset + n)})

        self._retarget_cables(other["id"], host["id"], offset)

        other["is_merged_into"] = host["id"]
        other["merged_offset"] = offset
        other["merged_board_id"] = new_bid

        if (self.first_connection_point is not None and
                self.first_connection_point["equipment"] is other):
            self.first_connection_point = {
                "equipment": host,
                "port": self.first_connection_point["port"] + offset,
            }

        self.recompute_mismatch()
        print(f"Merge: #{other['id']} поглощён #{host['id']} "
              f"как плата {new_bid} (портов +{n})")
        return True

    def can_unmerge(self, host, board_id):
        board = next((b for b in host["boards"]
                      if b["board_id"] == board_id), None)
        if board is None:
            return False, []
        start, end = board["port_range"]
        mixed = []
        for grp in host.get("lacp_groups", []):
            inside = [p for p in grp["ports"] if start <= p < end]
            outside = [p for p in grp["ports"] if not (start <= p < end)]
            if inside and outside:
                mixed.append(grp["name"])
        return True, mixed

    def unmerge_equipment(self, host, board_id, force=False):
        board = next((b for b in host["boards"]
                      if b["board_id"] == board_id), None)
        if board is None:
            print(f"Unmerge: плата {board_id} не найдена")
            return False
        if board is host["boards"][0]:
            print("Unmerge: нельзя отсоединить базовую плату 1")
            return False

        ok, mixed = self.can_unmerge(host, board_id)
        if mixed and not force:
            print(f"Unmerge: LACP будет сломан ({', '.join(mixed)}). "
                  f"Повторите с подтверждением.")
            return False

        start, end = board["port_range"]
        n = end - start

        other = None
        for d in self.equipment:
            if (d.get("is_merged_into") == host["id"]
                    and d.get("merged_board_id") == board_id):
                other = d
                break
        if other is None:
            print(f"Unmerge: не найдено скрытое устройство для платы {board_id}")
            return False
        other_id = other["id"]

        # Разбор LACP
        new_host_lacp = []
        other_lacp = []
        next_other_id = 1
        for grp in host.get("lacp_groups", []):
            inside = [p for p in grp["ports"] if start <= p < end]
            outside = [p for p in grp["ports"] if not (start <= p < end)]
            if inside and outside:
                continue   # смешанные удаляются
            if inside and not outside:
                new_grp = dict(grp)
                new_grp["id"] = next_other_id
                new_grp["name"] = f"LACP-{next_other_id}"
                new_grp["ports"] = [p - start for p in inside]
                other_lacp.append(new_grp)
                next_other_id += 1
            else:
                new_host_lacp.append(grp)
        host["lacp_groups"] = new_host_lacp
        other["lacp_groups"] = other_lacp

        # Кабели платы -> на other
        for cable in self.cables:
            if cable["a"] == host["id"] and start <= cable["port_a"] < end:
                cable["a"] = other_id
                cable["port_a"] -= start
            if (cable.get("b") == host["id"]
                    and cable.get("port_b") is not None
                    and start <= cable["port_b"] < end):
                cable["b"] = other_id
                cable["port_b"] -= start

        # Срез портов
        other["ports"] = host["ports"][start:end]
        del host["ports"][start:end]

        # Сдвиг плат, идущих после
        new_boards = []
        for b in host["boards"]:
            if b["board_id"] == board_id:
                continue
            bs, be = b["port_range"]
            if bs >= end:
                new_boards.append({"board_id": b["board_id"],
                                   "port_range": (bs - n, be - n)})
            else:
                new_boards.append(b)
        host["boards"] = new_boards

        # Сдвиг индексов в LACP host'а
        for grp in host["lacp_groups"]:
            grp["ports"] = [p - n if p >= end else p for p in grp["ports"]]

        # Сдвиг кабелей host'а после end
        self._shift_cables(host["id"], end, -n)

        # Снимаем флаги
        other.pop("is_merged_into", None)
        other.pop("merged_offset", None)
        other.pop("merged_board_id", None)

        # Курсор прокладки
        if self.first_connection_point is not None:
            fcp = self.first_connection_point
            if fcp["equipment"] is host:
                if start <= fcp["port"] < end:
                    self.first_connection_point = None
                elif fcp["port"] >= end:
                    self.first_connection_point = {
                        "equipment": host,
                        "port": fcp["port"] - n,
                    }

        self.recompute_mismatch()
        print(f"Unmerge: плата {board_id} отсоединена от #{host['id']} "
              f"→ #{other_id} (возвращено портов {n})")
        return True

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
        devices = self.visible_devices_at(loc) if loc is not None else []
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
        if not in_house and self.visible_devices_at(loc):
            print("Ошибка: на этом столбе уже стоит оборудование")
            return False

        if self.budget < tool["cost"]:
            print(f"Ошибка: недостаточно монет (нужно {tool['cost']}, есть {self.budget})")
            return False

        self.budget -= tool["cost"]
        n_ports = tool["ports"]
        obj = {
            "id": self._next_equipment_id,
            "type": tool["type"],
            "x": loc[0], "y": loc[1],
            "ports": make_ports(n_ports),
            "lacp_groups": [],
            "boards": [{"board_id": 1, "port_range": (0, n_ports)}],
        }
        self._next_equipment_id += 1
        self.equipment.append(obj)
        self.equipment_at.setdefault(loc, []).append(obj)
        print(f"Установлен {tool['name']} (центр: {loc})")
        return True

    # ---- прокладка кабеля ----
    def phantom_path(self, tx, ty):
        if self.first_connection_point is None:
            return None
        a = self.first_connection_point["equipment"]
        a_loc = (a["x"], a["y"])
        target = self.equipment_location(tx, ty)
        if target is None:
            target = (tx, ty)
        points, length, found = find_route_via_power_graph(
            a_loc, target, self.power_lines)
        return {"points": points, "length": length, "found_route": found,
                "signal_ok": length <= MAX_CABLE_TILES}

    def connect_click(self, tool, tx, ty):
        loc = self.equipment_location(tx, ty)
        dc = find_datacenter(self.datacenters, tx, ty)
        devices = self.visible_devices_at(loc) if loc is not None else []

        if dc is not None and not devices:
            if self.first_connection_point is None:
                print("Ошибка: сначала выберите порт Роутера, затем кликните по ЦОД")
                return False
            a = self.first_connection_point["equipment"]
            if a["type"] != "router":
                print("Ошибка: к ЦОД можно подключить только Роутер (магистраль)")
                self.first_connection_point = None
                return False
            self._open_dc_tariff(tool, a, self.first_connection_point["port"], dc)
            return True

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
                self.first_connection_point = {"equipment": device,
                                               "port": port_index}
                info = EQUIP_INFO[device["type"]]
                print(f"Выбран порт {port_index + 1} на {info['prep']} "
                      f"#{device['id']}")

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

    # ---- подключение к ЦОД ----
    def _existing_dc_tariff(self, router_id, dc_id):
        for cable in self.cables:
            if (cable.get("to_dc") and cable.get("a") == router_id
                    and cable.get("dc_id") == dc_id):
                return (cable.get("tariff", "Тариф"),
                        cable.get("dc_speed", 1000),
                        cable.get("dc_ips", 1))
        return None

    def _open_dc_tariff(self, tool, router, port_a, dc):
        dc_loc = self.equipment_location(dc["x"], dc["y"])
        existing = self._existing_dc_tariff(router["id"], dc.get("id"))

        def on_tariff_chosen(speed, name, ips):
            self._finish_cable_to_dc(tool, router, port_a, dc, dc_loc,
                                     speed, name, ips)

        print(f"Выбор тарифа: Роутер #{router['id']} -> ЦОД "
              f"'{dc.get('name', 'DC')}'"
              f"{' (есть активный тариф)' if existing else ''}")
        self.ui_manager.open_dc_tariff_selection(on_tariff_chosen,
                                                 existing_tariff=existing)

    def _finish_cable_to_dc(self, tool, router, port_a, dc, dc_loc,
                            speed, tariff_name, ips):
        if not router["ports"][port_a]["free"]:
            print("Ошибка: порт Роутера уже занят")
            self.first_connection_point = None
            return False

        points, length, found_route = find_route_via_power_graph(
            (router["x"], router["y"]), dc_loc, self.power_lines)

        if not found_route:
            print("Ошибка: НЕТ ПУТИ ПО СЕТИ ЛЭП между Роутером и ЦОД")
            self.first_connection_point = None
            return False

        cost = length * tool["rate"]
        if self.budget < cost:
            print(f"Ошибка: недостаточно монет (нужно {cost}, есть {self.budget})")
            self.first_connection_point = None
            return False

        signal_ok = length <= MAX_CABLE_TILES
        if not signal_ok:
            print(f"⚠️ Длина магистрали {length} > {MAX_CABLE_TILES} тайл. "
                  f"Кабель проложен, но СИГНАЛ ПОТЕРЯН!")

        self.budget -= cost
        router["ports"][port_a]["free"] = False
        router["ports"][port_a]["connection"] = {
            "to_dc": True, "dc_id": dc.get("id"),
            "dc_name": dc.get("name", "DC"), "tariff": tariff_name,
            "to_id": None, "to_port": None,}
        router["ports"][port_a]["label"] = "Магистраль"

        cable = {
            "id": self._next_cable_id,
            "type": tool["type"],
            "a": router["id"], "port_a": port_a,
            "b": None, "port_b": None,
            "points": points,
            "length": length,
            "cost": cost,
            "signal_ok": signal_ok,
            "to_dc": True,
            "dc_id": dc.get("id"),
            "tariff": tariff_name,
            "dc_speed": speed,
            "dc_ips": ips,
        }
        self._next_cable_id += 1
        self.cables.append(cable)
        self.first_connection_point = None

        status = "OK" if signal_ok else "СИГНАЛ ПОТЕРЯН"
        print(f"Проложена МАГИСТРАЛЬ к ЦОД '{dc.get('name', 'DC')}': "
              f"Роутер #{router['id']} (порт {port_a + 1}), тариф "
              f"'{tariff_name}' ({speed} Мбит, {ips} IP), "
              f"{length} тайл., {cost} монет, {status}")
        return True

    def _finish_cable(self, tool, a, port_a, b, port_b):
        # ФИКС: Если устройства в одном доме (координаты совпадают), делаем кабель коротким
        if a["x"] == b["x"] and a["y"] == b["y"]:
            points = [(a["x"], a["y"]), (b["x"], b["y"])]
            length = 2 # Фиксированная длина 2 тайла для коммутации внутри здания
            found_route = True
        else:
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
        
        # ... остальной код метода остается без изменений ...
        
        

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
    dc_w = max(3, int(round(3 * cam.zoom)))
    for cable in game.cables:
        if cable.get("speed_mismatch"):
            color = COLOR_CABLE_MISMATCH
            width = err_w
        elif cable.get("to_dc"):
            color = COLOR_CABLE_DC
            width = dc_w
            if not cable.get("signal_ok", True):
                color = COLOR_CABLE_ERROR
                width = err_w
        elif not cable.get("signal_ok", True):
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
    is_dc_target = find_datacenter(game.datacenters, tx, ty) is not None

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
    elif is_dc_target:
        if game.first_connection_point["equipment"]["type"] == "router":
            color = COLOR_CABLE_DC
            line_style = "solid"
            text = f"МАГИСТРАЛЬ К ЦОД | Длина: {length} | Цена: {cost}"
            text_color = COLOR_CABLE_DC
        else:
            color = COLOR_CABLE_NO_ROUTE
            line_style = "dashed"
            text = "К ЦОД можно только РОУТЕР"
            text_color = COLOR_CABLE_NO_ROUTE
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


def _house_centers(game):
    centers = set()
    for h in game.houses:
        if h.get("type", "house") == "house":
            centers.add(game.house_center(h))
    return centers


def draw_houses(screen, game, cam, fonts):
    """Дома с оборудованием — синий фильтр + иконка + цифра; пустые остаются жёлтыми."""
    for house in game.houses:
        if house.get("type", "house") != "house":
            continue
        loc = game.house_center(house)
        devices = game.equipment_at.get(loc, [])
        if not devices:
            continue

        rect = cam.tile_rect(house["x"], house["y"],
                             house["width"], house["height"])
        if not cam.on_screen(rect.centerx, rect.centery, margin=80):
            continue

        if rect.width > 0 and rect.height > 0:
            filt = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            filt.fill(COLOR_HOUSE_EQUIP_FILTER)
            screen.blit(filt, (rect.x, rect.y))
            pygame.draw.rect(screen, COLOR_EQUIP_EDGE, rect, 1)

        cx, cy = cam.tile_center(loc[0], loc[1])
        z = cam.zoom
        icon_r = max(4, int(round(6 * z)))
        has_router = any(e["type"] == "router" for e in devices)
        if has_router:
            pts = hexagon_points(cx, cy, icon_r)
            pygame.draw.polygon(screen, COLOR_EQUIP, pts)
            pygame.draw.polygon(screen, COLOR_EQUIP_EDGE, pts, 1)
        else:
            irect = pygame.Rect(0, 0, icon_r * 2, icon_r * 2)
            irect.center = (cx, cy)
            pygame.draw.rect(screen, COLOR_EQUIP, irect)
            pygame.draw.rect(screen, COLOR_EQUIP_EDGE, irect, 1)

        font = fonts.get(max(11, min(40, int(round(14 * z)))))
        text = str(len(devices))
        th = font.size(text)[1]
        draw_outlined_text(screen, font, text,
                           (int(cx + icon_r + 2), int(cy - th / 2)))


def draw_equipment(screen, game, cam, fonts):
    """Оборудование на столбах ЛЭП (дома рисует draw_houses)."""
    centers = _house_centers(game)
    groups = {}
    for e in game.equipment:
        key = (e["x"], e["y"])
        if key in centers:
            continue
        groups.setdefault(key, []).append(e)

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
        if abs(mouse[0] - cx) <= 10 and abs(mouse[1] - cy) <= 10:
            pygame.draw.circle(screen, (255, 255, 180), (cx, cy),
                               max(8, int(round(11 * z))), 1)

    if game.first_connection_point is not None:
        dev = game.first_connection_point["equipment"]
        cx, cy = cam.tile_center(dev["x"], dev["y"])
        pygame.draw.circle(screen, COLOR_SELECTED, (cx, cy), max(6, int(round(10 * z))), 2)


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
# ЗАПУСК ИГРЫ (вызывается из main_menu.py)
# --------------------------------------------------------------------------
def run_game(map_data, screen, screen_w, screen_h):
    """Игровой цикл на готовом экране. pygame инициализирован снаружи.
    Возврат: "quit" (закрыли окно) или "menu" (Esc -> в меню)."""
    pygame.display.set_caption("Telecom INC - Песочница")

    game = Game(map_data)

    print(f"Карта загружена: {game.size}x{game.size} тайлов, "
          f"домов: {len(game.houses)}, ЦОД: {len(game.datacenters)}, "
          f"столбов ЛЭП: {len(game.power_lines)}")
    print(f"Стартовый бюджет: {game.budget} монет")
    print("Управление:")
    print("  Колесо - зум / прокрутка в окне, ПКМ+тащить - панорамирование")
    print("  ЛКМ по дому - окно дома -> 'Оборудование'")
    print("  Config -> +ADD_LACP (выбор портов кликом), +ADD_VLAN (в разработке)")
    print("  Магистраль: порт Роутера -> клик по ЦОД -> выбор тарифа")
    print("  Esc - закрыть окно / отмена / выход в меню")

    names = FONT_NAMES
    font = pygame.font.SysFont(names, 18)
    small_font = pygame.font.SysFont(names, 13)
    fonts = FontCache(names)

    ui_manager = UIWindowManager(game)
    game.ui_manager = ui_manager

    terrain = render_terrain(map_data)
    map_px = game.size * TILE

    view_w = screen_w
    view_h = screen_h - PANEL_H

    cam = Camera(view_w, view_h, map_px)
    buttons = make_buttons(screen_w, screen_h)
    map_rect = pygame.Rect(0, 0, view_w, view_h)
    clock = pygame.time.Clock()
    dragging = False

    result = "menu"
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                result = "quit"
                continue

            if ui_manager.handle_event(event):
                continue

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
        draw_houses(screen, game, cam, fonts)
        draw_poles(screen, game, cam)
        draw_cables(screen, game, cam)
        draw_equipment(screen, game, cam, fonts)
        draw_phantom(screen, game, cam, mouse_pos, fonts)
        screen.set_clip(None)
        draw_ui(screen, font, small_font, screen_w, screen_h, buttons, game)
        ui_manager.draw(screen, font, small_font)
        pygame.display.flip()
        clock.tick(60)

    print("Выход из игры.")
    return result


# для отладки без меню: python visualizer.py --map map.json
def _standalone():
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Telecom INC (отладочный запуск)")
    parser.add_argument("--map", type=str, default="map.json",
                        help="путь к JSON-файлу карты")
    args = parser.parse_args()

    try:
        with open(args.map, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit(f"Файл не найден: {args.map}. Запустите main_menu.py.")
    except json.JSONDecodeError as e:
        sys.exit(f"Некорректный JSON в {args.map}: {e}")

    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    run_game(data, screen, 1280, 720)
    pygame.quit()


if __name__ == "__main__":
    _standalone()
    
    