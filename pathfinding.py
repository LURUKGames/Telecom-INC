#!/usr/bin/env python3
"""
pathfinding.py - геометрия и маршрутизация по сети ЛЭП (без pygame).

Чистые функции (легко тестировать отдельно):
  - геометрия: polyline_length, point_to_segment_dist;
  - поиск кабеля под курсором: find_cable_at_pos;
  - поиск ЦОД по тайлу: find_datacenter;
  - ЛЭП-граф: find_nearest_pole, find_path_in_graph (BFS),
    find_route_via_power_graph.
"""

import math
from collections import deque

from config import SCISSORS_HIT_DIST


# --------------------------------------------------------------------------
# Геометрия
# --------------------------------------------------------------------------
def polyline_length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(points, points[1:]))


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


# --------------------------------------------------------------------------
# Поиск объектов
# --------------------------------------------------------------------------
def find_datacenter(datacenters, tx, ty):
    for dc in datacenters:
        w = dc.get("width", 1)
        h = dc.get("height", 1)
        if dc["x"] <= tx < dc["x"] + w and dc["y"] <= ty < dc["y"] + h:
            return dc
    return None


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


# --------------------------------------------------------------------------
# ЛЭП-граф
# --------------------------------------------------------------------------
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