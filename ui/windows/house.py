#!/usr/bin/env python3
"""ui/windows/house.py - окно дома."""

import pygame
from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_STATUS_UP,
)
from ui.app_window import AppWindow

class HouseWindow(AppWindow):
    def __init__(self, house, screen_w, screen_h, game=None):
        w, h = 400, 280
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.house = house
        self.game = game
        
        devices = self._house_devices()
        
        buttons = [
            {
                "text": "⚙ Оборудование" if devices else "Нет оборудования",
                "callback": self._open_universal_config,
                "disabled": not devices
            },
            {
                "text": "Инфо (тест)",
                "callback": lambda: print("Инфо"),
            }
        ]
        
        super().__init__(x, y, w, h, f"Дом #{house['id']}", buttons=buttons)
        
        # Задаем высоту контента (чтобы работал скролл, если окно сжать)
        self.content_height = 16 + 3 * 34 + 16 

    def _house_loc(self):
        return (self.house["x"] + self.house["width"] // 2,
                self.house["y"] + self.house["height"] // 2)

    def _house_devices(self):
        if self.game is None:
            return []
        return [d for d in self.game.equipment_at.get(self._house_loc(), [])
                if not d.get("is_merged_into")]

    def _open_universal_config(self):
        if self.game is None:
            return
        devices = self._house_devices()
        if not devices:
            return
        self.game.ui_manager.open_universal_config(devices)

    def _render_content(self, surface, font, small_font):
        x = 18
        y = 16
        floors = self.house.get("floors", "?")
        clients = self.house.get("clients", "?")
        devices = self._house_devices()
        
        lines = [
            (f"Этажей: {floors}", COLOR_TEXT),
            (f"Жителей: {clients}", COLOR_TEXT),
            (f"Оборудования: {len(devices)}",
             COLOR_STATUS_UP if devices else COLOR_TEXT_DIM),
        ]
        for text, col in lines:
            surf = font.render(text, True, col)
            surface.blit(surf, (x, y))
            y += 34
            
            