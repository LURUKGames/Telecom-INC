#!/usr/bin/env python3
"""ui/manager.py - менеджер активного окна + стек предыдущих."""

import pygame

from ui.house import HouseWindow
from ui.device import SwitchWindow, RouterWindow
from ui.config_window import (
    SwitchConfigWindow, RouterConfigWindow, UniversalConfigWindow,
)
from ui.datacenter import DatacenterWindow, DCTariffWindow
from ui.port_select import PortSelectWindow


class UIWindowManager:
    def __init__(self, game):
        self.game = game
        self.active_window = None
        self.window_stack = []

    def _screen_size(self):
        surf = pygame.display.get_surface()
        return surf.get_width(), surf.get_height()

    def _set_active(self, win, push=True):
        if win is None:
            return
        win.manager = self
        if push and self.active_window is not None and not self.active_window.is_closed:
            self.window_stack.append(self.active_window)
        self.active_window = win

    def go_back(self):
        if self.active_window is not None:
            self.active_window.is_closed = True
        if self.window_stack:
            prev = self.window_stack.pop()
            prev.is_closed = False
            self.active_window = prev
        else:
            self.active_window = None

    def close_all(self):
        if self.active_window is not None:
            self.active_window.is_closed = True
        self.active_window = None
        self.window_stack.clear()

    # ---- открытие окон ----
    def open_house(self, house):
        if house is None:
            return
        sw, sh = self._screen_size()
        self._set_active(HouseWindow(house, sw, sh, game=self.game))

    def open_universal_config(self, devices):
        if not devices:
            return
        sw, sh = self._screen_size()
        self._set_active(UniversalConfigWindow(devices, sw, sh, game=self.game))

    def open_switch(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self._set_active(SwitchWindow(equipment_list, sw, sh,
                                      game=self.game, manager=self))

    def open_router(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self._set_active(RouterWindow(equipment_list, sw, sh,
                                      game=self.game, manager=self))

    def open_switch_config(self, equip):
        sw, sh = self._screen_size()
        self._set_active(SwitchConfigWindow(equip, sw, sh, game=self.game))

    def open_router_config(self, equip):
        sw, sh = self._screen_size()
        self._set_active(RouterConfigWindow(equip, sw, sh, game=self.game))

    def open_datacenter(self, dc):
        sw, sh = self._screen_size()
        self._set_active(DatacenterWindow(dc, sw, sh))

    def open_dc_tariff_selection(self, callback, existing_tariff=None):
        sw, sh = self._screen_size()
        self._set_active(DCTariffWindow(callback, sw, sh,
                                        existing_tariff=existing_tariff))

    def open_port_selection(self, devices_list, is_second_click, callback):
        if not devices_list:
            return
        sw, sh = self._screen_size()
        self._set_active(PortSelectWindow(devices_list, is_second_click,
                                          callback, sw, sh, game=self.game))

    # ---- старое API ----
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
            if self.window_stack:
                prev = self.window_stack.pop()
                prev.is_closed = False
                self.active_window = prev
            else:
                self.active_window = None
            return False

        win = self.active_window

        if event.type == pygame.MOUSEMOTION and (
                win.dragging or win.resizing or win.scroll_dragging):
            return win.handle_event(event)

        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if win.contains(mouse):
                win.scroll(event.y)
                return True
            return False

        handled = win.handle_event(event)
        if self.active_window is win and win.is_closed:
            if self.window_stack:
                prev = self.window_stack.pop()
                prev.is_closed = False
                self.active_window = prev
            else:
                self.active_window = None
        return handled

    def draw(self, screen, font, small_font):
        if self.active_window is not None and not self.active_window.is_closed:
            self.active_window.draw(screen, font, small_font)
            
            