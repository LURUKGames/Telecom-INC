#!/usr/bin/env python3
"""ui/datacenter.py - окно информации о ЦОД и окно выбора тарифа магистрали."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TEXT_DIM,
    HEADER_H, DC_TARIFFS,
)
from ui.base import Window
from ui.widgets import _vgrad_rect, speed_label


class DatacenterWindow(Window):
    def __init__(self, dc, screen_w, screen_h):
        w, h = 300, 180
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"ЦОД: {dc.get('name', 'DC')}")
        self.dc = dc

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        lbl = small_font.render("Магистральный узел конкурента.", True, COLOR_TEXT)
        screen.blit(lbl, (self.x + 14, self.y + HEADER_H + 20))
        note = small_font.render("Подключите роутер кабелем к ЦОД,", True, COLOR_TEXT_DIM)
        screen.blit(note, (self.x + 14, self.y + HEADER_H + 50))
        note2 = small_font.render("чтобы выбрать тариф аплинка.", True, COLOR_TEXT_DIM)
        screen.blit(note2, (self.x + 14, self.y + HEADER_H + 75))


class DCTariffWindow(Window):
    TARIFFS = DC_TARIFFS

    def __init__(self, callback, screen_w, screen_h, existing_tariff=None):
        w, h = 400, 340
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Подключение к ЦОД")
        self.callback = callback
        self.existing = existing_tariff   # (name, speed, ips) или None
        self._buttons = []

    def _layout(self):
        self._buttons = []
        bw, bh = self.width - 60, 42
        bx = self.x + 30
        by = self.y + HEADER_H + 30
        if self.existing is not None:
            name, speed, ips = self.existing
            rect = pygame.Rect(bx, by, bw, bh)
            self._buttons.append((rect, f"Использовать текущий: {name}",
                                  speed, ips, True))
            by += bh + 14
        for (label, speed, ips) in self.TARIFFS:
            rect = pygame.Rect(bx, by, bw, bh)
            full = f"{label} ({speed_label(speed)}, {ips} IP)"
            self._buttons.append((rect, full, speed, ips, False))
            by += bh + 12

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.dragging:
            return super().handle_event(event)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            return super().handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            self._layout()
            for rect, label, speed, ips, is_existing in self._buttons:
                if rect.collidepoint(event.pos):
                    cb = self.callback
                    name = label.replace("Использовать текущий: ", "")
                    name = name.split(" (")[0]
                    self.close()
                    print(f"Выбран тариф: {name} "
                          f"({speed_label(speed)}, {ips} IP)"
                          f"{' [повтор]' if is_existing else ''}")
                    cb(speed, name, ips)
                    return True
            if self.contains(event.pos):
                return True
            self.close()
            return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        mouse = pygame.mouse.get_pos()
        hint = small_font.render("Выберите тариф магистрали:", True, COLOR_TEXT_DIM)
        screen.blit(hint, (self.x + 30, self.y + HEADER_H + 6))
        for rect, label, speed, ips, is_existing in self._buttons:
            hover = rect.collidepoint(mouse)
            if is_existing:
                top = (90, 180, 120) if hover else (60, 130, 85)
                bot = (60, 130, 85) if hover else (40, 90, 60)
                edge = (150, 255, 180) if hover else (90, 180, 120)
                tcol = (240, 255, 245)
            else:
                top = (210, 180, 70) if hover else (160, 135, 55)
                bot = (150, 120, 45) if hover else (110, 90, 35)
                edge = (255, 230, 150) if hover else (200, 170, 90)
                tcol = (30, 25, 10)
            _vgrad_rect(screen, rect, top, bot, radius=8)
            pygame.draw.rect(screen, edge, rect, 2 if hover else 1, border_radius=8)
            txt = small_font.render(label, True, tcol)
            screen.blit(txt, (rect.centerx - txt.get_width() // 2,
                              rect.centery - txt.get_height() // 2))
            