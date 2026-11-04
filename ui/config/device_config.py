#!/usr/bin/env python3
"""
ui/config/device_config.py - Обёртки для окон конфигурации.
Раньше здесь была сложная дублированная логика.
Теперь они просто открывают UniversalConfigWindow с одним устройством,
чтобы у игрока везде был единый интерфейс.
"""

from ui.net_helpers import equip_type_label
from ui.config.universal_config import UniversalConfigWindow


class SwitchConfigWindow(UniversalConfigWindow):
    """Окно конфигурации одного свитча (при клике на карте)."""
    def __init__(self, equip, screen_w, screen_h, game=None):
        # Передаем список из одного устройства в UniversalConfigWindow
        super().__init__([equip], screen_w, screen_h, game=game)
        # Меняем заголовок окна для точности
        self.title = f"Config: {equip_type_label(equip)} #{equip['id']}"


class RouterConfigWindow(UniversalConfigWindow):
    """Окно конфигурации одного роутера (при клике на карте)."""
    def __init__(self, equip, screen_w, screen_h, game=None):
        super().__init__([equip], screen_w, screen_h, game=game)
        self.title = f"Config: Роутер #{equip['id']}"