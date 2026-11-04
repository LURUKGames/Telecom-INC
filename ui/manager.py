#!/usr/bin/env python3
"""ui/manager.py - менеджер активного окна (роутинг событий, открытие окон)."""

import pygame

from ui.house import HouseWindow, EquipmentChoiceWindow
from ui.device import SwitchWindow, RouterWindow
from ui.config_window import SwitchConfigWindow, RouterConfigWindow
from ui.datacenter import DatacenterWindow, DCTariffWindow
from ui.port_select import PortSelectWindow


class UIWindowManager:
    def __init__(self, game):
        self.game = game
        self.active_window = None

    def _screen_size(self):
        surf = pygame.display.get_surface()
        return surf.get_width(), surf.get_height()

    def open_house(self, house):
        if house is None:
            return
        sw, sh = self._screen_size()
        self.active_window = HouseWindow(house, sw, sh, game=self.game)

    def open_equipment_choice(self, devices, game):
        if not devices:
            return
        sw, sh = self._screen_size()
        self.active_window = EquipmentChoiceWindow(devices, sw, sh, game=game)

    def open_switch(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self.active_window = SwitchWindow(equipment_list, sw, sh,
                                         game=self.game, manager=self)

    def open_router(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self.active_window = RouterWindow(equipment_list, sw, sh,
                                         game=self.game, manager=self)

    def open_switch_config(self, equip):
        sw, sh = self._screen_size()
        self.active_window = SwitchConfigWindow(equip, sw, sh, game=self.game)

    def open_router_config(self, equip):
        sw, sh = self._screen_size()
        self.active_window = RouterConfigWindow(equip, sw, sh, game=self.game)
    
    def open_universal_config(self, devices):
        if not devices:
            return
        sw, sh = self._screen_size()
        from ui.config_window import UniversalConfigWindow
        self.active_window = UniversalConfigWindow(devices, sw, sh, game=self.game)
    
    def open_chassis_merge(self, base_equip):
        sw, sh = self._screen_size()
        from ui.chassis import ChassisMergeWindow
        self.active_window = ChassisMergeWindow(base_equip, sw, sh,
                                                game=self.game, manager=self)

    def open_datacenter(self, dc):
        sw, sh = self._screen_size()
        self.active_window = DatacenterWindow(dc, sw, sh)

    def open_dc_tariff_selection(self, callback, existing_tariff=None):
        sw, sh = self._screen_size()
        self.active_window = DCTariffWindow(callback, sw, sh,
                                            existing_tariff=existing_tariff)

    def open_port_selection(self, devices_list, is_second_click, callback):
        if not devices_list:
            return
        sw, sh = self._screen_size()
        self.active_window = PortSelectWindow(devices_list, is_second_click,
                                             callback, sw, sh, game=self.game)

    def close_active(self):
        if self.active_window is not None:
            self.active_window.close()
            self.active_window = None

    def has_active(self):
        return self.active_window is not None and not self.active_window.is_closed

    def is_port_selection_active(self):
        return (isinstance(self.active_window, PortSelectWindow)
                and not self.active_window.is_closed)

    def is_text_input_active(self):
        return (self.active_window is not None
                and not self.active_window.is_closed
                and self.active_window.is_text_input_active())

    def handle_event(self, event):
        if self.active_window is None:
            return False
        if self.active_window.is_closed:
            self.active_window = None
            return False

        win = self.active_window

        if event.type == pygame.MOUSEMOTION and win.dragging:
            handled = win.handle_event(event)
            if self.active_window is win and win.is_closed:
                self.active_window = None
            return handled

        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if win.contains(mouse):
                win.scroll(event.y)
                return True
            return False

        handled = win.handle_event(event)
        if self.active_window is win and win.is_closed:
            self.active_window = None
        return handled

    def draw(self, screen, font, small_font):
        if self.active_window is not None and not self.active_window.is_closed:
            self.active_window.draw(screen, font, small_font)
            
            