#!/usr/bin/env python3
"""ui/house.py - окно информации о доме."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_STATUS_UP,
    HEADER_H, FOOTER_H,
)
from ui.base import Window
from ui.widgets import draw_fancy_button


class HouseWindow(Window):
    def __init__(self, house, screen_w, screen_h, game=None):
        w, h = 350, 250
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"Дом #{house['id']}")
        self.house = house
        self.game = game
        self._equip_btn = pygame.Rect(0, 0, 0, 0)

    def _house_loc(self):
        return (self.house["x"] + self.house["width"] // 2,
                self.house["y"] + self.house["height"] // 2)

    def _house_devices(self):
        if self.game is None:
            return []
        return self.game.equipment_at.get(self._house_loc(), [])

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._equip_btn.collidepoint(event.pos):
                self._open_equipment()
                return True
        return super().handle_event(event)

    def _open_equipment(self):
        if self.game is None:
            return
        loc = self._house_loc()
        devices = self.game.equipment_at.get(loc, [])
        if not devices:
            print(f"В доме #{self.house['id']} нет оборудования")
            return
        switches = [d for d in devices if d["type"] in ("switch_12", "switch_24")]
        routers = [d for d in devices if d["type"] == "router"]
        self.close()
        if switches:
            self.game.ui_manager.open_switch(switches)
        elif routers:
            self.game.ui_manager.open_router(routers)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        x = self.x + 18
        y = self.y + HEADER_H + 16
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
            screen.blit(surf, (x, y))
            y += 34
        self._equip_btn = pygame.Rect(self.x + self.width // 2 - 90,
                                      self.y + self.height - FOOTER_H + 2, 180, 34)
        mouse = pygame.mouse.get_pos()
        if not devices:
            draw_fancy_button(screen, small_font, self._equip_btn,
                              "Нет оборудования", state="disabled")
        else:
            state = "hover" if self._equip_btn.collidepoint(mouse) else "normal"
            draw_fancy_button(screen, small_font, self._equip_btn,
                              "⚙ Оборудование", state=state)
            