#!/usr/bin/env python3
"""ui/port_select.py - окно выбора порта для прокладки кабеля."""

import pygame

from config import COLOR_TITLE
from ui.base import Window
from ui.widgets import draw_fancy_button
from ui.net_helpers import port_in_lacp, equip_type_label


class PortSelectWindow(Window):
    def __init__(self, devices_list, is_second_click, callback, screen_w, screen_h):
        w, h = 300, 400
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.devices_list = devices_list
        self.is_second_click = is_second_click
        self.callback = callback
        title = "Выбор порта (цель)" if is_second_click else "Выбор порта (старт)"
        super().__init__(x, y, w, h, title)
        self.cols = 4
        self.box = 40
        self.gap = 10
        self.header_gap = 26
        self.block_gap = 16
        self._hit_ports = []
        self._compute_content_height()

    def _free_ports(self, device):
        return [i for i, p in enumerate(device["ports"])
                if p["free"] and port_in_lacp(device, i) is None]

    def _compute_content_height(self):
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            y += self.header_gap
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap
        self.content_height = y + 8

    def _layout(self):
        self._hit_ports = []
        start_x = 12
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            y += self.header_gap
            for idx, port_index in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap)
                self._hit_ports.append((pygame.Rect(px, py, self.box, self.box),
                                       device, port_index))
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        content_x = local_x - cr.x
        content_y = local_y - cr.y
        self._layout()
        for rect, device, port_index in self._hit_ports:
            if rect.collidepoint(content_x, content_y):
                cb = self.callback
                self.close()
                cb(device, port_index)
                return

    def _render_content(self, surface, font, small_font):
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        start_x = 12
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            hdr = small_font.render(f"{equip_type_label(device)} #{device['id']}",
                                    True, COLOR_TITLE)
            surface.blit(hdr, (start_x, y - self.scroll_y + 4))
            y += self.header_gap
            for idx, port_index in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap) - self.scroll_y
                if py + self.box < 0 or py > surface.get_height():
                    continue
                prect = pygame.Rect(px, py, self.box, self.box)
                hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                draw_fancy_button(surface, tiny, prect, str(port_index + 1),
                                  state="hover" if hover else "normal")
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap
            