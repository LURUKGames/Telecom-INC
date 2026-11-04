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
from ui.house import HouseWindow, EquipmentChoiceWindow
from ui.device import SwitchWindow, RouterWindow
from ui.lacp import LACPInputWindow
from ui.config_window import SwitchConfigWindow, RouterConfigWindow, UniversalConfigWindow
from ui.datacenter import DatacenterWindow, DCTariffWindow
from ui.port_select import PortSelectWindow
from ui.manager import UIWindowManager

__all__ = [
    "TextInput", "speed_label", "_vgrad_rect", "_screen_size",
    "draw_fancy_button", "draw_button_on", "draw_button_screen",
    "find_cable_for_port", "port_in_lacp", "toggle_port_speed",
    "toggle_lacp_speed", "equip_type_label", "port_status_text_color",
    "port_fill_color", "lacp_effective_label",
    "Window", "HouseWindow", "EquipmentChoiceWindow",
    "SwitchWindow", "RouterWindow", "LACPInputWindow",
    "SwitchConfigWindow", "RouterConfigWindow",
    "DatacenterWindow", "DCTariffWindow", "PortSelectWindow",
    "UIWindowManager", "UniversalConfigWindow",
]
