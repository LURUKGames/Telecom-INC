#!/usr/bin/env python3
"""
map_generator.py (v2) - процедурный генератор карты города для симулятора провайдера.

Запуск:
    python map_generator.py --seed 42 --output map.json [--size 100]

Только стандартная библиотека. Координаты: x - вправо, y - вниз.
tiles[y][x] - тайл в точке (x, y).

Алгоритм:
  1. Магистрали: 2-3 плавные кривые y = f(x) (сумма синусоид), пересекающие карту.
  2. Переулки: прямые ветки под прямым углом к магистрали, длиной 7-16 тайлов.
  3. Дома: идут рядами вдоль всех дорог, ровно 1 тайл газона между дорогой и домом.
     Из получившегося набора мест выбирается нужное число домов (плотнее у центра),
     3 места в разных частях карты отдаются под ЦОД.
  4. ЛЭП: столбы вдоль всех дорог каждые ~5 тайлов, связанные в цепочки.
"""

import argparse
import json
import math
import random
import sys
from collections import deque

TILE_SIZE_M = 5
POLE_STEP = 5            # шаг столбов вдоль дороги, тайлов (25 м)
DC_COUNT = 3

DIRS4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]
LABEL = {(0, -1): "north", (0, 1): "south", (1, 0): "east", (-1, 0): "west"}

# (длинная сторона, короткая сторона), вес
SHAPES = [((2, 2), 3), ((3, 2), 4), ((4, 2), 2), ((3, 3), 3), ((4, 3), 3), ((5, 3), 1)]
HOUSE_COLORS = ["yellow", "white", "gray", "beige", "brown", "blue", "green"]


def in_bounds(x, y, size):
    return 0 <= x < size and 0 <= y < size


# --------------------------------------------------------------------------
# Дороги
# --------------------------------------------------------------------------
def make_main(rng, size, horizontal, band):
    """Магистраль как гладкая функция: сумма двух синусоид. Возвращает упорядоченный путь."""
    base = rng.uniform(*band) * size
    amp = rng.uniform(0.05, 0.08) * size
    cycles = rng.uniform(0.7, 1.3)
    ph1 = rng.uniform(0, 2 * math.pi)
    ph2 = rng.uniform(0, 2 * math.pi)

    def f(t):
        return (base
                + amp * math.sin(2 * math.pi * cycles * t / size + ph1)
                + 0.3 * amp * math.sin(4 * math.pi * cycles * t / size + ph2))

    path = []
    prev = None
    for t in range(size):
        v = min(max(int(round(f(t))), 2), size - 3)
        if prev is None or v == prev:
            seq = [v]
        else:
            step = 1 if v > prev else -1
            seq = list(range(prev, v + step, step))   # вертикальная "ступенька": дорога остаётся связной
        for s in seq:
            path.append((t, s) if horizontal else (s, t))
        prev = v
    return path


def try_branch(rng, size, roads, start, d):
    """Прямая ветка от тайла магистрали в направлении d. Не прижимается к другим дорогам."""
    length = rng.randint(7, 16)
    tiles = []
    prev = start
    x, y = start
    for _ in range(length):
        x += d[0]
        y += d[1]
        if not (2 <= x <= size - 3 and 2 <= y <= size - 3):
            break
        if (x, y) in roads:
            break
        if any((x + dx, y + dy) != prev and (x + dx, y + dy) in roads for dx, dy in DIRS4):
            break
        tiles.append((x, y))
        prev = (x, y)
    return tiles if len(tiles) >= 5 else None


def build_roads(rng, size, factor):
    """Возвращает (множество тайлов дорог, список путей {"tiles", "horizontal"})."""
    n_main = rng.choice((2, 3))
    if n_main == 2:
        specs = [(True, (0.3, 0.7)), (False, (0.3, 0.7))]
    else:
        major = rng.choice((True, False))
        specs = [(major, (0.20, 0.32)), (major, (0.66, 0.80)), (not major, (0.40, 0.60))]

    roads = set()
    paths = []
    for horizontal, band in specs:
        tiles = make_main(rng, size, horizontal, band)
        roads.update(tiles)
        paths.append({"tiles": tiles, "horizontal": horizontal})
    mains = list(paths)

    lo_sp = max(5, int(9 / factor))
    hi_sp = max(8, int(15 / factor))
    for main in mains:
        tiles, horizontal = main["tiles"], main["horizontal"]
        i = rng.randint(5, 9)
        while i < len(tiles) - 5:
            sides = rng.choice([(1,), (-1,), (1, -1), (1, -1)])
            for sd in sides:
                d = (0, sd) if horizontal else (sd, 0)
                for di in (0, 1, -1, 2, -2):
                    j = i + di
                    if not 0 <= j < len(tiles):
                        continue
                    br = try_branch(rng, size, roads, tiles[j], d)
                    if br:
                        roads.update(br)
                        paths.append({"tiles": br, "horizontal": not horizontal})
                        break
            i += rng.randint(lo_sp, hi_sp)
    return roads, paths


# --------------------------------------------------------------------------
# Дома
# --------------------------------------------------------------------------
def pick_shape(rng, d):
    """Размер (w, h); длинная сторона чаще идёт вдоль дороги."""
    (a, b) = rng.choices([s for s, _ in SHAPES], weights=[w for _, w in SHAPES])[0]
    along = a if rng.random() < 0.75 else b
    across = b if along == a else a
    if d[1] != 0:       # дом севернее/южнее горизонтальной дороги -> вдоль дороги ширина
        return along, across
    return across, along


def rect_for(rx, ry, d, w, h):
    """Левый верхний угол дома так, чтобы между дорогой (rx, ry) и домом был ровно 1 тайл."""
    if d == (0, -1):    # дом севернее дороги
        return rx, ry - 1 - h
    if d == (0, 1):     # южнее
        return rx, ry + 2
    if d == (1, 0):     # восточнее
        return rx + 2, ry
    return rx - 1 - w, ry   # западнее


def fits(x, y, w, h, size, roads, occ):
    """Дом и кольцо в 1 тайл вокруг него свободны от дорог и других домов."""
    if x < 0 or y < 0 or x + w > size or y + h > size:
        return False
    for yy in range(y - 1, y + h + 1):
        for xx in range(x - 1, x + w + 1):
            if (xx, yy) in roads or (xx, yy) in occ:
                return False
    return True


def pack_houses(rng, size, roads, paths):
    """Заполняет обе стороны каждой дороги рядами домов. Возвращает список мест."""
    occ = set()
    pool = []
    for path in paths:
        dirs = DIRS4[:]
        rng.shuffle(dirs)
        for d in dirs:
            for rx, ry in path["tiles"]:
                for _ in range(3):
                    w, h = pick_shape(rng, d)
                    x, y = rect_for(rx, ry, d, w, h)
                    if fits(x, y, w, h, size, roads, occ):
                        for yy in range(y, y + h):
                            for xx in range(x, x + w):
                                occ.add((xx, yy))
                        pool.append({"x": x, "y": y, "width": w, "height": h,
                                     "facing": LABEL[(-d[0], -d[1])]})
                        break
    return pool


def center_of(p):
    return p["x"] + p["width"] / 2.0, p["y"] + p["height"] / 2.0


def pick_datacenter_spots(rng, pool, size):
    """3 места, по возможности далеко друг от друга."""
    best = None
    for _ in range(500):
        trio = rng.sample(range(len(pool)), DC_COUNT)
        cs = [center_of(pool[i]) for i in trio]
        md = min(math.dist(cs[a], cs[b]) for a in range(DC_COUNT) for b in range(a + 1, DC_COUNT))
        if best is None or md > best[0]:
            best = (md, trio)
        if md >= size * 0.33:
            break
    return best[1]


def assign_floors_and_clients(rng, houses, lo, hi):
    """floors 2..12; сумма клиентов около 70 на дом, но всегда в [lo, hi]."""
    n = len(houses)
    for h in houses:
        h["floors"] = rng.randint(2, 12)
    total = int(round(70 * n * rng.uniform(0.92, 1.08)))
    total = min(max(total, lo), hi)
    weights = [h["floors"] * rng.uniform(0.7, 1.3) for h in houses]
    sw = sum(weights)
    clients = [max(1, round(w * total / sw)) for w in weights]
    diff = total - sum(clients)
    while diff != 0:
        i = rng.randrange(n)
        if diff > 0:
            clients[i] += 1
            diff -= 1
        elif clients[i] > 1:
            clients[i] -= 1
            diff += 1
    for h, c in zip(houses, clients):
        h["clients"] = c


# --------------------------------------------------------------------------
# ЛЭП (столбы с промежутками, граф по расстоянию)
# --------------------------------------------------------------------------
def place_power_lines(rng, grid, paths, size):
    """
    Новая система ЛЭП:
    1. Вдоль дорог ставим столбы РЕДКО (с шагом 5 тайлов вдоль дороги).
    2. Столбы соединяются в граф, если расстояние между ними <= 5 тайлов.
    3. Кабель в игре будет прыгать между столбами по воздуху.
    """
    POLE_SPACING = 5  # шаг между столбами вдоль дороги
    MAX_LINK_DIST = 6  # максимальное расстояние связи между столбами

    poles = []
    pole_at = {}  # (x, y) -> pole_id

    # Собираем все тайлы дорог
    all_road_tiles = set()
    for path in paths:
        all_road_tiles.update(path["tiles"])

    # ---- ШАГ 1: расставляем столбы РЕДКО вдоль каждой дороги ----
    power_positions = set()

    for path in paths:
        tiles = path["tiles"]
        # идём вдоль дороги с шагом POLE_SPACING
        for i in range(0, len(tiles), POLE_SPACING):
            rx, ry = tiles[i]
            # ищем свободный газон рядом с дорогой для столба
            placed = False
            for dx, dy in DIRS4:
                px, py = rx + dx, ry + dy
                if in_bounds(px, py, size) and grid[py][px] == "grass":
                    power_positions.add((px, py))
                    placed = True
                    break
        # обязательно ставим столб в конце дороги
        if tiles:
            rx, ry = tiles[-1]
            for dx, dy in DIRS4:
                px, py = rx + dx, ry + dy
                if in_bounds(px, py, size) and grid[py][px] == "grass":
                    power_positions.add((px, py))
                    break

    # ---- ШАГ 2: индексируем столбы ----
    pole_index = {}
    for i, (x, y) in enumerate(sorted(power_positions), start=1):
        pole_index[(x, y)] = i
        poles.append({"id": i, "x": x, "y": y, "connected_to": []})
        pole_at[(x, y)] = i
        grid[y][x] = "power_line"

    # ---- ШАГ 3: строим связи по РАССТОЯНИЮ (<= MAX_LINK_DIST) ----
    pole_list = list(pole_index.items())
    for i in range(len(pole_list)):
        (x1, y1), id1 = pole_list[i]
        for j in range(i + 1, len(pole_list)):
            (x2, y2), id2 = pole_list[j]
            dist = math.hypot(x1 - x2, y1 - y2)
            if dist <= MAX_LINK_DIST:
                if id2 not in poles[id1 - 1]["connected_to"]:
                    poles[id1 - 1]["connected_to"].append(id2)
                if id1 not in poles[id2 - 1]["connected_to"]:
                    poles[id2 - 1]["connected_to"].append(id1)

    # ---- ШАГ 4: проверяем связность, соединяем компоненты ----
    def components():
        seen, out = set(), []
        for p in poles:
            if p["id"] in seen:
                continue
            comp, dq = {p["id"]}, deque([p["id"]])
            seen.add(p["id"])
            while dq:
                cur = dq.popleft()
                for q in poles[cur - 1]["connected_to"]:
                    if q not in seen:
                        seen.add(q)
                        comp.add(q)
                        dq.append(q)
            out.append(comp)
        return out

    guard = 0
    while guard < 100:
        guard += 1
        comps = components()
        if len(comps) <= 1:
            break
        # соединяем две ближайшие компоненты
        main = max(comps, key=len)
        best = None
        for comp in comps:
            if comp is main:
                continue
            for a in comp:
                pa = poles[a - 1]
                for b in main:
                    pb = poles[b - 1]
                    d = math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
                    if best is None or d < best[0]:
                        best = (d, a, b)
        if best is None:
            break
        # соединяем, даже если дальше MAX_LINK_DIST (принудительный мост)
        _, a, b = best
        if b not in poles[a - 1]["connected_to"]:
            poles[a - 1]["connected_to"].append(b)
            poles[b - 1]["connected_to"].append(a)

    # сортируем связи
    for p in poles:
        p["connected_to"].sort()

    return poles

# --------------------------------------------------------------------------
# Общая генерация
# --------------------------------------------------------------------------
def generate(seed, size):
    rng = random.Random(seed)
    scale = (size / 100.0) ** 2
    min_h, max_h = round(100 * scale), round(150 * scale)
    lo_clients, hi_clients = min_h * 70, max_h * 70      # 7000 .. 10500

    for attempt in range(20):
        factor = 1.0 + 0.15 * attempt                    # при нехватке мест - больше переулков
        roads, paths = build_roads(rng, size, factor)
        pool = pack_houses(rng, size, roads, paths)
        n_target = rng.randint(min_h, max_h)
        if len(pool) >= n_target + DC_COUNT + 10:
            break
    else:
        raise RuntimeError("Не удалось сгенерировать карту, попробуйте другой seed или размер")

    dc_idx = set(pick_datacenter_spots(rng, pool, size))
    dc_spots = [pool[i] for i in sorted(dc_idx)]
    rest = [p for i, p in enumerate(pool) if i not in dc_idx]

    # дома плотнее у центра: сортировка по расстоянию до центра с шумом
    c = size / 2.0
    rest.sort(key=lambda p: math.dist(center_of(p), (c, c)) * rng.uniform(0.6, 1.4))
    chosen = rest[:n_target]
    chosen.sort(key=lambda p: (p["y"], p["x"]))

    houses = []
    for i, p in enumerate(chosen, 1):
        houses.append({"id": i, "type": "house", "x": p["x"], "y": p["y"],
                       "width": p["width"], "height": p["height"],
                       "facing": p["facing"], "color": rng.choice(HOUSE_COLORS)})
    assign_floors_and_clients(rng, houses, lo_clients, hi_clients)

    datacenters = []
    for k, p in enumerate(dc_spots, 1):
        hid = len(houses) + 1
        houses.append({"id": hid, "type": "datacenter", "x": p["x"], "y": p["y"],
                       "width": p["width"], "height": p["height"],
                       "facing": p["facing"], "color": "red",
                       "floors": rng.randint(1, 3), "clients": 0,
                       "name": f"Competitor DC {k}"})
        datacenters.append({"id": k, "house_id": hid, "x": p["x"], "y": p["y"],
                            "width": p["width"], "height": p["height"],
                            "color": "red", "name": f"Competitor DC {k}"})

    # тайлы
    grid = [["grass"] * size for _ in range(size)]
    for x, y in roads:
        grid[y][x] = "road"
    for h in houses:
        t = "datacenter" if h["type"] == "datacenter" else "house"
        for yy in range(h["y"], h["y"] + h["height"]):
            for xx in range(h["x"], h["x"] + h["width"]):
                grid[yy][xx] = t

    poles = place_power_lines(rng, grid, paths, size)

    ordered = []
    for h in houses:
        ordered.append({k: h[k] for k in ("id", "type", "x", "y", "width", "height",
                                          "facing", "floors", "clients", "color")
                        } | ({"name": h["name"]} if "name" in h else {}))

    return {
        "seed": seed,
        "size": size,
        "tile_size_m": TILE_SIZE_M,
        "tiles": [[{"type": t} for t in row] for row in grid],
        "houses": ordered,
        "power_lines": poles,
        "datacenters": datacenters,
    }


# --------------------------------------------------------------------------
# Проверки
# --------------------------------------------------------------------------
def road_sides(x, y, w, h, roads):
    """
    Стороны дома, к которым ровно через 1 тайл газона примыкает дорога.
    None, если в кольце шириной 1 тайл вокруг дома есть дорога (отступ меньше 1).
    """
    for yy in range(y - 1, y + h + 1):
        for xx in range(x - 1, x + w + 1):
            if (xx, yy) in roads:
                return None
    sides = []
    if any((xx, y - 2) in roads for xx in range(x, x + w)):
        sides.append("north")
    if any((xx, y + h + 1) in roads for xx in range(x, x + w)):
        sides.append("south")
    if any((x - 2, yy) in roads for yy in range(y, y + h)):
        sides.append("west")
    if any((x + w + 1, yy) in roads for yy in range(y, y + h)):
        sides.append("east")
    return sides


def road_components(roads):
    seen, out = set(), []
    for t in roads:
        if t in seen:
            continue
        comp, dq = {t}, deque([t])
        seen.add(t)
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in DIRS4:
                n = (cx + dx, cy + dy)
                if n in roads and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    dq.append(n)
        out.append(comp)
    return out


def run_checks(data):
    size = data["size"]
    tiles = data["tiles"]
    houses = data["houses"]
    poles = data["power_lines"]
    scale = (size / 100.0) ** 2
    min_h, max_h = round(100 * scale), round(150 * scale)
    lo, hi = min_h * 70, max_h * 70
    regular = [h for h in houses if h["type"] == "house"]
    dcs = [h for h in houses if h["type"] == "datacenter"]
    roads = {(x, y) for y in range(size) for x in range(size) if tiles[y][x]["type"] == "road"}
    results = []

    def add(label, ok):
        results.append(ok)
        print(f"  {label}: {'да' if ok else 'нет'}")

    add(f"Домов (без ЦОД): {len(regular)} (нужно {min_h}-{max_h})", min_h <= len(regular) <= max_h)
    add(f"ЦОД: {len(dcs)}, у всех clients = 0",
        len(dcs) == DC_COUNT and all(h["clients"] == 0 for h in dcs))
    total = sum(h["clients"] for h in regular)
    add(f"Сумма клиентов (без ЦОД): {total} (нужно {lo}-{hi})", lo <= total <= hi)
    add("Этажность домов 2-12", all(2 <= h["floors"] <= 12 for h in regular))

    inb = all(0 <= h["x"] and 0 <= h["y"] and h["x"] + h["width"] <= size
              and h["y"] + h["height"] <= size for h in houses)
    inb &= all(0 <= p["x"] < size and 0 <= p["y"] < size for p in poles)
    add(f"Все объекты в пределах карты (0..{size - 1})", inb)

    occ = set()
    clean = True
    for h in houses:
        want = "datacenter" if h["type"] == "datacenter" else "house"
        for yy in range(h["y"], h["y"] + h["height"]):
            for xx in range(h["x"], h["x"] + h["width"]):
                if (xx, yy) in occ:
                    clean = False
                occ.add((xx, yy))
                if in_bounds(xx, yy, size) and tiles[yy][xx]["type"] != want:
                    clean = False
    add("Нет пересечений домов друг с другом и с дорогами", clean)

    near = True
    shapes = set()
    for h in houses:
        sides = road_sides(h["x"], h["y"], h["width"], h["height"], roads)
        if not sides or h["facing"] not in sides:
            near = False
        shapes.add((h["width"], h["height"]))
    add(f"Все дома стоят вдоль дороги с отступом ровно 1 тайл "
        f"(форм домов: {len(shapes)})", near)

    adj = all(any((p["x"] + dx, p["y"] + dy) in roads for dx, dy in DIRS4) for p in poles)
    on_tile = all(tiles[p["y"]][p["x"]]["type"] == "power_line" for p in poles)
    ids = {p["id"] for p in poles}
    links_ok = all(p["connected_to"] and all(q in ids and p["id"] in poles[q - 1]["connected_to"]
                                             for q in p["connected_to"]) for p in poles)
    covered = all(any(abs(p["x"] - rx) <= 6 and abs(p["y"] - ry) <= 6 for p in poles)
                  for rx, ry in roads)
    add(f"ЛЭП идут вдоль дорог: столбов {len(poles)}, каждый рядом с дорогой, "
        f"вся сеть дорог покрыта", adj and on_tile and covered)
    add("Связи между столбами корректны (взаимные, без пустых)", links_ok)

    comps = road_components(roads)
    add(f"Дороги образуют единую связную сеть (тайлов дорог: {len(roads)})", len(comps) == 1)

    return all(results)


def main():
    parser = argparse.ArgumentParser(description="Генератор карты города (JSON)")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed генерации (по умолчанию случайный)")
    parser.add_argument("--output", type=str, default="map.json",
                        help="путь к выходному JSON-файлу")
    parser.add_argument("--size", type=int, default=100,
                        help="размер карты в тайлах (по умолчанию 100, минимум 60)")
    args = parser.parse_args()

    if args.size < 60:
        parser.error("--size должен быть не меньше 60")
    seed = args.seed if args.seed is not None else random.randrange(2 ** 31)

    data = generate(seed, args.size)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))

    print(f"Карта сохранена: {args.output} (seed={seed}, size={args.size}, "
          f"{args.size * TILE_SIZE_M}x{args.size * TILE_SIZE_M} м)")
    print("Проверки:")
    ok = run_checks(data)
    print("Итог: все проверки пройдены" if ok else "Итог: ЕСТЬ ОШИБКИ")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
    
    