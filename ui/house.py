#!/usr/bin/env python3
"""ui/house.py - окно дома и выбора оборудования в доме."""

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
                self._open_equipment_choice()
                return True
        return super().handle_event(event)

    def _open_equipment_choice(self):
        if self.game is None:
            return
        loc = self._house_loc()
        devices = self.game.equipment_at.get(loc, [])
        if not devices:
            print(f"В доме #{self.house['id']} нет оборудования")
            return
        self.close()
        self.game.ui_manager.open_equipment_choice(devices, self.game)

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


class EquipmentChoiceWindow(Window):
    def __init__(self, devices, screen_w, screen_h, game=None):
        w, h = 300, 250
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Выбор оборудования")
        self.game = game
        self.switches = [d for d in devices if d["type"] in ("switch_12", "switch_24")]
        self.routers = [d for d in devices if d["type"] == "router"]
        self._switch_btn = pygame.Rect(0, 0, 0, 0)
        self._router_btn = pygame.Rect(0, 0, 0, 0)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.switches and self._switch_btn.collidepoint(event.pos):
                self.close()
                if self.game is not None:
                    self.game.ui_manager.open_switch(self.switches)
                return True
            if self.routers and self._router_btn.collidepoint(event.pos):
                self.close()
                if self.game is not None:
                    self.game.ui_manager.open_router(self.routers)
                return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        mouse = pygame.mouse.get_pos()
        bw, bh = 260, 48
        bx = self.x + self.width // 2 - bw // 2
        y = self.y + HEADER_H + 28

        self._switch_btn = pygame.Rect(bx, y, bw, bh)
        if self.switches:
            sstate = "hover" if self._switch_btn.collidepoint(mouse) else "normal"
        else:
            sstate = "disabled"
        draw_fancy_button(screen, small_font, self._switch_btn,
                          f"Свитчи ({len(self.switches)})", state=sstate)

        y += bh + 20
        self._router_btn = pygame.Rect(bx, y, bw, bh)
        if self.routers:
            rstate = "hover" if self._router_btn.collidepoint(mouse) else "normal"
        else:
            rstate = "disabled"
        draw_fancy_button(screen, small_font, self._router_btn,
                          f"Роутеры ({len(self.routers)})", state=rstate)
        
        