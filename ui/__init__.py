#!/usr/bin/env python3
"""ui - пакет оконного интерфейса Telecom INC. Реэкспорт публичного API."""

from ui.widgets import (
    TextInput, speed_label, _vgrad_rect, _screen_size,
    draw_fancy_button, draw_button_on, draw_button_screen,
)
from ui.net_helpers import (
    find_cable_for_port, port_in_lacp, toggle_port_speed, toggle_lacp_speed,
    equip_type_label, port_status_text_color, port_fill_color,
    lacp_effective_label,
)
from ui.base import Window

# --- Окна на карте ---
from ui.windows.house import HouseWindow
from ui.windows.device import SwitchWindow, RouterWindow
from ui.windows.datacenter import DatacenterWindow, DCTariffWindow
from ui.windows.port_select import PortSelectWindow

# --- Окна конфигурации ---
from ui.config.lacp import LACPInputWindow
from ui.config.commut import CommutWindow
from ui.config.vlan_popup import VlanPopupWindow
from ui.config.universal_config import UniversalConfigWindow
from ui.config.device_config import SwitchConfigWindow, RouterConfigWindow

# --- Менеджер и хелперы ---
from ui.manager import UIWindowManager
from ui.chassis import port_name, board_of_port, boards_summary


__all__ = [
    # widgets
    "TextInput", "speed_label", "_vgrad_rect", "_screen_size",
    "draw_fancy_button", "draw_button_on", "draw_button_screen",
    # helpers
    "find_cable_for_port", "port_in_lacp", "toggle_port_speed",
    "toggle_lacp_speed", "equip_type_label", "port_status_text_color",
    "port_fill_color", "lacp_effective_label",
    # base
    "Window",
    # карта
    "HouseWindow", "SwitchWindow", "RouterWindow",
    "DatacenterWindow", "DCTariffWindow", "PortSelectWindow",
    # конфигурация
    "LACPInputWindow", "CommutWindow", "VlanPopupWindow",
    "UniversalConfigWindow", "SwitchConfigWindow", "RouterConfigWindow",
    # менеджер
    "UIWindowManager",
    # хелперы портов
    "port_name", "board_of_port", "boards_summary",
]