#!/usr/bin/env python3
"""ui/port_select.py - окно выбора порта при прокладке кабеля.
Фильтр LACP снят: физпорты в LACP доступны для кабеля."""

import pygame

from config import COLOR_TITLE, COLOR_TEXT_DIM
from ui.base import Window
from ui.widgets import draw_fancy_button
from ui.net_helpers import equip_type_label
from ui.chassis import port_name


class PortSelectWindow(Window):
    def __init__(self, devices_list, is_second_click, callback, screen_w, screen_h,
                 game=None):
        w, h = 340, 440
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.devices_list = [d for d in devices_list if not d.get("is_merged_into")]
        self.is_second_click = is_second_click
        self.callback = callback
        self.game = game
        title = "Выбор порта (цель)" if is_second_click else "Выбор порта (старт)"
        super().__init__(x, y, w, h, title)
        self.cols = 4
        self.box = 48
        self.gap = 10
        self.header_gap = 26
        self.block_gap = 16
        self._hit_ports = []
        self._compute_content_height()

    def _free_ports(self, device):
        """Свободные физпорты — БЕЗ фильтра port_in_lacp."""
        return [i for i, p in enumerate(device["ports"]) if p["free"]]

    def _block_h(self, device):
        free = self._free_ports(device)
        if not free:
            return 0
        h = self.header_gap
        rows = (len(free) + self.cols - 1) // self.cols
        h += rows * (self.box + self.gap)
        return h + self.block_gap

    def _compute_content_height(self):
        y = 8
        for d in self.devices_list:
            y += self._block_h(d)
        self.content_height = y + 8

    def _layout(self):
        self._hit_ports = []
        start_x = 14
        y = 8
        for d in self.devices_list:
            free = self._free_ports(d)
            if not free:
                continue
            y += self.header_gap
            for idx, pi in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap)
                self._hit_ports.append(
                    (pygame.Rect(px, py, self.box, self.box), d, pi))
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap)
            y += self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        cx = local_x - cr.x
        cy = local_y - cr.y
        self._layout()
        for rect, device, pi in self._hit_ports:
            if rect.collidepoint(cx, cy):
                cb = self.callback
                self.close()
                cb(device, pi)
                return

    def _render_content(self, surface, font, small_font):
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        start_x = 14
        y = 8
        for d in self.devices_list:
            free = self._free_ports(d)
            if not free:
                continue
            boards_n = len(d.get("boards", []))
            title = (f"{equip_type_label(d)} #{d['id']}"
                     + (f"  [шасси, плат: {boards_n}]" if boards_n > 1 else ""))
            hdr = small_font.render(title, True, COLOR_TITLE)
            surface.blit(hdr, (start_x, y - self.scroll_y + 4))
            y += self.header_gap
            for idx, pi in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap) - self.scroll_y
                if py + self.box < 0 or py > surface.get_height():
                    continue
                prect = pygame.Rect(px, py, self.box, self.box)
                hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                label = (port_name(self.game, d, pi) if self.game else str(pi + 1))
                draw_fancy_button(surface, tiny, prect, label,
                                  state="hover" if hover else "normal")
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap)
            y += self.block_gap
            
            