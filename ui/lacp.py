#!/usr/bin/env python3
"""ui/lacp.py - мини-окно создания LACP (выбор портов кликом по сетке)."""

import pygame

from config import (
    COLOR_TEXT, COLOR_PORT_EDGE, COLOR_PORT_LACP, COLOR_PORT_LACP_SEL,
    HEADER_H,
)
from ui.base import Window
from ui.widgets import _vgrad_rect, draw_button_screen


class LACPInputWindow(Window):
    def __init__(self, callback, screen_w, screen_h, equip, is_selectable):
        self.equip = equip
        self.is_selectable = is_selectable      # func(port_index) -> bool
        n = len(equip["ports"])
        self.cols = 6
        self.box = 40
        self.gap = 8
        rows = (n + self.cols - 1) // self.cols
        grid_h = rows * (self.box + self.gap)
        w = 60 + self.cols * (self.box + self.gap)
        h = HEADER_H + 40 + grid_h + 60
        w = max(w, 360)
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "LACP: выбери порты кликом")
        self.callback = callback
        self.selected = set()
        self._cells = []
        self._ok_btn = pygame.Rect(0, 0, 0, 0)
        self._cancel_btn = pygame.Rect(0, 0, 0, 0)
        self._tiny = pygame.font.SysFont("arial,dejavusans", 12)

    def is_text_input_active(self):
        return False

    def _layout(self):
        self._cells = []
        start_x = self.x + 30
        start_y = self.y + HEADER_H + 34
        for i in range(len(self.equip["ports"])):
            c = i % self.cols
            r = i // self.cols
            px = start_x + c * (self.box + self.gap)
            py = start_y + r * (self.box + self.gap)
            self._cells.append((pygame.Rect(px, py, self.box, self.box), i))
        by = self.y + self.height - 44
        self._ok_btn = pygame.Rect(self.x + 20, by, 140, 32)
        self._cancel_btn = pygame.Rect(self.x + self.width - 160, by, 140, 32)

    def _submit(self):
        cb = self.callback
        sel = set(self.selected)
        self.close()
        cb(sel)

    def handle_event(self, event):
        self._layout()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit()
                return True
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self._ok_btn.collidepoint(event.pos):
                self._submit()
                return True
            if self._cancel_btn.collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            for rect, i in self._cells:
                if rect.collidepoint(event.pos):
                    if not self.is_selectable(i):
                        print(f"Порт {i + 1} уже занят LACP-группой")
                        return True
                    if i in self.selected:
                        self.selected.discard(i)
                    else:
                        self.selected.add(i)
                    return True
            return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        mouse = pygame.mouse.get_pos()
        hint = small_font.render(f"Выбрано: {len(self.selected)} (мин. 2)",
                                 True, COLOR_TEXT)
        screen.blit(hint, (self.x + 30, self.y + HEADER_H + 8))
        for rect, i in self._cells:
            selectable = self.is_selectable(i)
            hover = rect.collidepoint(mouse)
            if not selectable:
                base = COLOR_PORT_LACP
            elif i in self.selected:
                base = COLOR_PORT_LACP_SEL
            else:
                base = (70, 120, 70) if not hover else (90, 150, 90)
            _vgrad_rect(screen, rect,
                        tuple(min(255, c + 30) for c in base), base, radius=6)
            edge = (255, 255, 255) if (i in self.selected) else COLOR_PORT_EDGE
            pygame.draw.rect(screen, edge, rect, 2 if (hover or i in self.selected) else 1,
                             border_radius=6)
            num = small_font.render(str(i + 1), True, COLOR_TEXT)
            screen.blit(num, (rect.centerx - num.get_width() // 2,
                              rect.centery - num.get_height() // 2))
        draw_button_screen(screen, small_font, self._ok_btn,
                           f"✔ Создать ({len(self.selected)})")
        draw_button_screen(screen, small_font, self._cancel_btn, "Отмена")
        