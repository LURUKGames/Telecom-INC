#!/usr/bin/env python3
"""ui/base.py - базовый класс окна (рамка, титлбар, скролл, перетаскивание)."""

import pygame

from config import (
    COLOR_WIN_BG, COLOR_WIN_EDGE, COLOR_WIN_EDGE_GLOW, COLOR_TITLE,
    COLOR_CLOSE, COLOR_CLOSE_HOVER,
    COLOR_TITLEBAR, COLOR_TITLEBAR_HOVER, COLOR_TITLEBAR_DRAG,
    COLOR_SCROLLBAR_BG, COLOR_SCROLLBAR, COLOR_SCROLLBAR_HOVER,
    HEADER_H, TITLEBAR_H, SCROLL_STEP,
)
from ui.widgets import _vgrad_rect, _screen_size


class Window:
    def __init__(self, x, y, width, height, title):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title
        self.is_closed = False
        self.scroll_y = 0
        self.content_height = 0
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def close_rect(self):
        return pygame.Rect(self.x + self.width - 28, self.y + 8, 20, 20)

    def titlebar_rect(self):
        return pygame.Rect(self.x, self.y, self.width, TITLEBAR_H)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H)

    def contains(self, mouse_pos):
        return self.rect().collidepoint(mouse_pos)

    def close(self):
        self.is_closed = True

    def max_scroll(self):
        visible = self.content_rect().height
        return max(0, self.content_height - visible)

    def scroll(self, direction):
        self.scroll_y -= direction * SCROLL_STEP
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll()))

    def _clamp_to_screen(self):
        sw, sh = _screen_size()
        self.x = max(0, min(self.x, sw - self.width))
        self.y = max(0, min(self.y, sh - self.height))

    def is_text_input_active(self):
        return False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.dragging:
            mx, my = event.pos
            self.x = mx - self.drag_offset_x
            self.y = my - self.drag_offset_y
            self._clamp_to_screen()
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            if self.contains(event.pos):
                if self.content_rect().collidepoint(event.pos):
                    self._on_content_click(event.pos[0], event.pos[1] + self.scroll_y)
                return True
            self.close()
            return True
        return False

    def _on_content_click(self, local_x, local_y):
        pass

    def _draw_frame(self, screen, font):
        panel = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, COLOR_WIN_BG, (0, 0, self.width, self.height),
                         border_radius=12)
        screen.blit(panel, (self.x, self.y))

        glow = pygame.Surface((self.width + 12, self.height + 12), pygame.SRCALPHA)
        for i, a in enumerate((30, 20, 12)):
            pygame.draw.rect(glow, (*COLOR_WIN_EDGE_GLOW, a),
                             (6 - i * 2, 6 - i * 2,
                              self.width + i * 4, self.height + i * 4),
                             2, border_radius=14)
        screen.blit(glow, (self.x - 6, self.y - 6))

        pygame.draw.rect(screen, COLOR_WIN_EDGE, self.rect(), 2, border_radius=12)

        mouse = pygame.mouse.get_pos()
        if self.dragging:
            bar_top, bar_bot = COLOR_TITLEBAR_DRAG, COLOR_TITLEBAR
        elif self.titlebar_rect().collidepoint(mouse):
            bar_top, bar_bot = COLOR_TITLEBAR_HOVER, COLOR_TITLEBAR
        else:
            bar_top, bar_bot = COLOR_TITLEBAR, (42, 42, 48)
        bar = pygame.Rect(self.x + 1, self.y + 1, self.width - 2, TITLEBAR_H)
        _vgrad_rect(screen, bar, bar_top, bar_bot, radius=11)

        for i in range(3):
            pygame.draw.circle(screen, (200, 200, 210),
                               (self.x + 10, self.y + 11 + i * 5), 1)

        title_surf = font.render(self.title, True, COLOR_TITLE)
        screen.blit(title_surf, (self.x + 22, self.y + 6))

        cr = self.close_rect()
        cc = COLOR_CLOSE_HOVER if cr.collidepoint(mouse) else COLOR_CLOSE
        pygame.draw.rect(screen, cc, cr, border_radius=5)
        cx, cy = cr.center
        pygame.draw.line(screen, (255, 255, 255), (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(screen, (255, 255, 255), (cx - 5, cy + 5), (cx + 5, cy - 5), 2)

    def _draw_scrollbar(self, screen):
        visible = self.content_rect().height
        if self.content_height <= visible:
            return
        track = pygame.Rect(self.x + self.width - 9, self.y + HEADER_H,
                           6, visible - 6)
        pygame.draw.rect(screen, COLOR_SCROLLBAR_BG, track, border_radius=3)
        frac = visible / self.content_height
        thumb_h = max(20, int(track.height * frac))
        max_s = self.max_scroll()
        pos_frac = (self.scroll_y / max_s) if max_s > 0 else 0
        thumb_y = track.y + int((track.height - thumb_h) * pos_frac)
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        mouse = pygame.mouse.get_pos()
        col = COLOR_SCROLLBAR_HOVER if thumb.collidepoint(mouse) else COLOR_SCROLLBAR
        pygame.draw.rect(screen, col, thumb, border_radius=3)

    def _draw_content(self, screen, font, small_font):
        cr = self.content_rect()
        content_surf = pygame.Surface((cr.width, cr.height), pygame.SRCALPHA)
        self._render_content(content_surf, font, small_font)
        screen.blit(content_surf, (cr.x, cr.y))
        self._draw_scrollbar(screen)

    def _render_content(self, surface, font, small_font):
        pass

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        