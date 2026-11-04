#!/usr/bin/env python3
"""ui/widgets.py - базовые виджеты и хелперы рисования (без игровой логики)."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TEXT_DIM,
    COLOR_BTN_TOP, COLOR_BTN_BOT,
    COLOR_BTN_HOVER_TOP, COLOR_BTN_HOVER_BOT,
    COLOR_BTN_ACTIVE_TOP, COLOR_BTN_ACTIVE_BOT,
    COLOR_BTN_DISABLED, COLOR_BTN_EDGE_UI, COLOR_BTN_EDGE_HOVER,
    COLOR_INPUT_BG, COLOR_INPUT_EDGE, COLOR_INPUT_EDGE_ACTIVE,
)


def speed_label(speed):
    if speed >= 10000:
        return "10G"
    if speed >= 1000:
        return "1G"
    return "100M"


def _screen_size():
    surf = pygame.display.get_surface()
    return surf.get_width(), surf.get_height()


def _vgrad_rect(surface, rect, top_color, bot_color, radius=6):
    tmp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    h = max(1, rect.height)
    for i in range(h):
        t = i / h
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
        pygame.draw.line(tmp, (r, g, b), (0, i), (rect.width, i))
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255),
                     (0, 0, rect.width, rect.height), border_radius=radius)
    tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(tmp, (rect.x, rect.y))


def draw_fancy_button(surface, font, rect, text, state="normal", radius=6):
    if state == "disabled":
        pygame.draw.rect(surface, COLOR_BTN_DISABLED, rect, border_radius=radius)
        edge = COLOR_BTN_EDGE_UI
        tcol = COLOR_TEXT_DIM
    else:
        if state == "active":
            top, bot = COLOR_BTN_ACTIVE_TOP, COLOR_BTN_ACTIVE_BOT
            edge = COLOR_BTN_EDGE_HOVER
        elif state == "hover":
            top, bot = COLOR_BTN_HOVER_TOP, COLOR_BTN_HOVER_BOT
            edge = COLOR_BTN_EDGE_HOVER
        else:
            top, bot = COLOR_BTN_TOP, COLOR_BTN_BOT
            edge = COLOR_BTN_EDGE_UI
        _vgrad_rect(surface, rect, top, bot, radius)
        tcol = COLOR_TEXT
        hi = pygame.Surface((rect.width, max(1, rect.height // 2)), pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 35),
                         (0, 0, rect.width, rect.height // 2),
                         border_top_left_radius=radius, border_top_right_radius=radius)
        surface.blit(hi, (rect.x, rect.y))
    pygame.draw.rect(surface, edge, rect, 1, border_radius=radius)
    surf = font.render(text, True, tcol)
    surface.blit(surf, (rect.centerx - surf.get_width() // 2,
                        rect.centery - surf.get_height() // 2))


def draw_button_on(surface, font, rect, text, active=False, enabled=True):
    state = "disabled" if not enabled else ("active" if active else "normal")
    draw_fancy_button(surface, font, rect, text, state)


def draw_button_screen(screen, font, rect, text, active=False):
    mouse = pygame.mouse.get_pos()
    state = "active" if active else ("hover" if rect.collidepoint(mouse) else "normal")
    draw_fancy_button(screen, font, rect, text, state)


class TextInput:
    def __init__(self, rect, initial_text="", max_length=15):
        self.rect = pygame.Rect(rect)
        self.text = initial_text
        self.active = False
        self.max_length = max_length
        self.cursor_pos = len(initial_text)
        self._cursor_timer = 0

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def _cursor_from_x(self, font, mouse_x):
        rel_x = mouse_x - (self.rect.x + 5)
        if rel_x <= 0:
            return 0
        for i in range(len(self.text)):
            w1 = font.size(self.text[:i])[0]
            w2 = font.size(self.text[:i + 1])[0]
            if w1 <= rel_x <= w2:
                return i if (rel_x - w1) < (w2 - rel_x) else i + 1
        return len(self.text)

    def handle_event(self, event, font=None):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True
                self._cursor_timer = 0
                if font is not None:
                    self.cursor_pos = self._cursor_from_x(font, event.pos[0])
                else:
                    self.cursor_pos = len(self.text)
                return True
            else:
                self.active = False
                return False

        if event.type == pygame.KEYDOWN and self.active:
            k = event.key
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False
                return True
            if k == pygame.K_ESCAPE:
                self.active = False
                return True
            if k == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
                self._cursor_timer = 0
                return True
            if k == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                self._cursor_timer = 0
                return True
            if k == pygame.K_HOME:
                self.cursor_pos = 0
                self._cursor_timer = 0
                return True
            if k == pygame.K_END:
                self.cursor_pos = len(self.text)
                self._cursor_timer = 0
                return True
            if k == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                self._cursor_timer = 0
                return True
            if k == pygame.K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                self._cursor_timer = 0
                return True
            ch = event.unicode
            if ch and ch.isprintable() and len(self.text) < self.max_length:
                self.text = self.text[:self.cursor_pos] + ch + self.text[self.cursor_pos:]
                self.cursor_pos += 1
                self._cursor_timer = 0
            return True

        return False

    def draw(self, surface, font):
        pygame.draw.rect(surface, COLOR_INPUT_BG, self.rect, border_radius=4)
        edge = COLOR_INPUT_EDGE_ACTIVE if self.active else COLOR_INPUT_EDGE
        pygame.draw.rect(surface, edge, self.rect, 1, border_radius=4)
        txt = font.render(self.text, True, COLOR_TEXT)
        surface.blit(txt, (self.rect.x + 5,
                          self.rect.centery - txt.get_height() // 2))
        if self.active:
            self._cursor_timer = (self._cursor_timer + 1) % 60
            if self._cursor_timer < 30:
                cx = self.rect.x + 5 + font.size(self.text[:self.cursor_pos])[0]
                pygame.draw.line(surface, COLOR_TEXT,
                               (cx, self.rect.y + 4),
                               (cx, self.rect.bottom - 4), 1)
                