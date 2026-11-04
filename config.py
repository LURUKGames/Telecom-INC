#!/usr/bin/env python3
"""
config.py - единые константы, цвета и настройки Telecom INC.

Сюда вынесены все "магические числа" из visualizer.py и ui_windows.py:
  - размеры тайла/панели, бюджет, зум, лимиты кабеля;
  - цвета карты, кабелей, оборудования;
  - описания инструментов (TOOLS), оборудования (EQUIP_INFO), тайлов (TILE_NAMES);
  - цвета и размеры UI-окон.
"""

# --------------------------------------------------------------------------
# ИГРОВЫЕ КОНСТАНТЫ (карта / экономика / камера)
# --------------------------------------------------------------------------
TILE = 8
PANEL_H = 60
START_BUDGET = 15000

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.1

SCISSORS_HIT_DIST = 1.5
MAX_CABLE_TILES = 30          # 30 тайлов = 150 метров

DIRS4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]


# --------------------------------------------------------------------------
# ЦВЕТА КАРТЫ И ОБЪЕКТОВ
# --------------------------------------------------------------------------
COLOR_BG = (30, 30, 30)
COLOR_GRASS = (100, 200, 100)
COLOR_ROAD = (60, 60, 60)
COLOR_HOUSE = (255, 255, 0)
COLOR_POLE = (0, 100, 0)
COLOR_DC = (255, 0, 0)
COLOR_EQUIP = (0, 150, 255)
COLOR_EQUIP_EDGE = (0, 70, 130)
COLOR_HOUSE_EQUIP_FILTER = (0, 150, 255, 100)

COLOR_CABLE_100M = (0, 170, 0)
COLOR_CABLE_1G = (0, 200, 255)
COLOR_CABLE_ERROR = (255, 0, 0)
COLOR_CABLE_MISMATCH = (255, 20, 20)
COLOR_CABLE_NO_ROUTE = (255, 100, 100)
COLOR_CABLE_DC = (255, 215, 0)
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

SWITCH_TYPES = ("switch_12", "switch_24")
ROUTER_TYPES = ("router",)


# --------------------------------------------------------------------------
# ИНСТРУМЕНТЫ (панель снизу)
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# ЦВЕТА И РАЗМЕРЫ UI-ОКОН
# --------------------------------------------------------------------------
COLOR_WIN_BG = (0, 0, 0, 210)
COLOR_WIN_EDGE = (150, 150, 150)
COLOR_WIN_EDGE_GLOW = (90, 180, 255)
COLOR_TITLE = (255, 255, 255)
COLOR_TEXT_DIM = (170, 170, 170)

COLOR_BTN_TOP = (95, 95, 105)
COLOR_BTN_BOT = (60, 60, 68)
COLOR_BTN_HOVER_TOP = (120, 150, 200)
COLOR_BTN_HOVER_BOT = (70, 100, 150)
COLOR_BTN_ACTIVE_TOP = (90, 200, 110)
COLOR_BTN_ACTIVE_BOT = (45, 140, 70)
COLOR_BTN_DISABLED = (48, 48, 52)
COLOR_BTN_EDGE_UI = (160, 160, 170)
COLOR_BTN_EDGE_HOVER = (180, 210, 255)

COLOR_CLOSE = (170, 60, 60)
COLOR_CLOSE_HOVER = (230, 80, 80)

COLOR_TITLEBAR = (55, 55, 62)
COLOR_TITLEBAR_HOVER = (78, 92, 120)
COLOR_TITLEBAR_DRAG = (95, 120, 165)

COLOR_PORT_DOWN = (200, 50, 50)
COLOR_PORT_DOWN_HI = (235, 90, 90)
COLOR_PORT_UP = (50, 200, 50)
COLOR_PORT_UP_HI = (90, 235, 90)
COLOR_PORT_ERROR = (255, 50, 50)
COLOR_PORT_ERROR_HI = (255, 90, 90)
COLOR_PORT_MISMATCH = (255, 20, 20)
COLOR_PORT_LACP = (110, 110, 120)
COLOR_PORT_LACP_SEL = (90, 160, 240)
COLOR_PORT_EDGE = (220, 220, 220)
COLOR_PORT_EDGE_HOVER = (255, 255, 255)

COLOR_INPUT_BG = (30, 30, 34)
COLOR_INPUT_EDGE = (120, 120, 130)
COLOR_INPUT_EDGE_ACTIVE = (80, 200, 100)

COLOR_SCROLLBAR_BG = (45, 45, 50)
COLOR_SCROLLBAR = (120, 120, 130)
COLOR_SCROLLBAR_HOVER = (160, 170, 190)

COLOR_STATUS_UP = (80, 220, 80)
COLOR_STATUS_DOWN = (170, 170, 170)
COLOR_STATUS_ERROR = (255, 70, 70)
COLOR_STATUS_LACP = (150, 150, 160)

COLOR_TARIFF = (200, 170, 60)
COLOR_LACP_ROW = (120, 180, 255)

# геометрия окон
HEADER_H = 40
TITLEBAR_H = 30
SCROLL_STEP = 28
FOOTER_H = 44

# колонки Config-окна
COL_NUM = 10
COL_STATUS = 50
COL_INPUT = 180
COL_INPUT_W = 150
COL_SPEED = 350
COL_SPEED_W = 100
ROW_H_CFG = 40

# шрифты (имена для SysFont)
FONT_NAMES = "arial,dejavusans,liberationsans,freesans"


# --------------------------------------------------------------------------
# ТАРИФЫ ЦОД (name, speed, ips)
# --------------------------------------------------------------------------
DC_TARIFFS = [
    ("Тариф Эконом", 100, 1),
    ("Тариф Стандарт", 1000, 4),
    ("Тариф Премиум", 10000, 16),
]

