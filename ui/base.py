#!/usr/bin/env python3
"""ui/base.py - базовый класс окна (рамка, стек-кнопка, скролл, drag, resize)."""

import pygame

from config import (
    COLOR_WIN_BG, COLOR_WIN_EDGE, COLOR_WIN_EDGE_GLOW, COLOR_TITLE,
    COLOR_CLOSE, COLOR_CLOSE_HOVER,
    COLOR_TITLEBAR, COLOR_TITLEBAR_HOVER, COLOR_TITLEBAR_DRAG,
    COLOR_SCROLLBAR_BG, COLOR_SCROLLBAR, COLOR_SCROLLBAR_HOVER,
    HEADER_H, TITLEBAR_H, SCROLL_STEP,
)
from ui.widgets import _vgrad_rect, _screen_size

MIN_W = 280
MIN_H = 180
RESIZE_GRIP = 14          # размер зоны ручки ресайза
BACK_BTN_SIZE = 20


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

        # drag title
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # resize
        self.resizable = True
        self.resizing = False
        self.resize_offset_x = 0
        self.resize_offset_y = 0

        # scroll drag
        self.scroll_dragging = False
        self.scroll_drag_offset = 0

        # менеджер проставляет при открытии (для кнопки «Назад»)
        self.manager = None

    # ---- геометрия ----
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def back_rect(self):
        return pygame.Rect(self.x + 6, self.y + 6, BACK_BTN_SIZE, BACK_BTN_SIZE)

    def close_rect(self):
        return pygame.Rect(self.x + self.width - 28, self.y + 8, 20, 20)

    def titlebar_rect(self):
        return pygame.Rect(self.x, self.y, self.width, TITLEBAR_H)

    def resize_rect(self):
        return pygame.Rect(self.x + self.width - RESIZE_GRIP,
                           self.y + self.height - RESIZE_GRIP,
                           RESIZE_GRIP, RESIZE_GRIP)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H)

    def contains(self, mouse_pos):
        return self.rect().collidepoint(mouse_pos)

    # ---- жизненный цикл ----
    def close(self):
        self.is_closed = True

    def max_scroll(self):
        visible = self.content_rect().height
        return max(0, self.content_height - visible)

    def scroll(self, direction):
        self.scroll_y -= direction * SCROLL_STEP
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll()))

    def _clamp_scroll(self):
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll()))

    def _clamp_to_screen(self):
        sw, sh = _screen_size()
        self.x = max(0, min(self.x, sw - self.width))
        self.y = max(0, min(self.y, sh - self.height))

    def _clamp_size(self):
        sw, sh = _screen_size()
        self.width = max(MIN_W, min(self.width, sw - self.x))
        self.height = max(MIN_H, min(self.height, sh - self.y))

    def on_resized(self):
        """Хук: вызывается после изменения размера окна. Пересчёт контента."""
        self._clamp_scroll()

    def is_text_input_active(self):
        return False

    # ---- scrollbar hit-boxes ----
    def _scrollbar_track(self):
        visible = self.content_rect().height
        if self.content_height <= visible:
            return None
        return pygame.Rect(self.x + self.width - 9,
                           self.y + HEADER_H, 6, visible - 6)

    def _scrollbar_thumb(self):
        track = self._scrollbar_track()
        if track is None:
            return None
        visible = self.content_rect().height
        frac = visible / self.content_height
        thumb_h = max(20, int(track.height * frac))
        max_s = self.max_scroll()
        pos_frac = (self.scroll_y / max_s) if max_s > 0 else 0
        thumb_y = track.y + int((track.height - thumb_h) * pos_frac)
        return pygame.Rect(track.x, thumb_y, track.width, thumb_h)

    def _update_scroll_from_mouse(self, mouse_y):
        track = self._scrollbar_track()
        thumb = self._scrollbar_thumb()
        if track is None or thumb is None:
            return
        max_s = self.max_scroll()
        if max_s <= 0:
            return
        new_thumb_y = mouse_y - self.scroll_drag_offset
        new_thumb_y = max(track.y, min(track.y + track.height - thumb.height,
                                       new_thumb_y))
        if track.height - thumb.height <= 0:
            return
        pos_frac = (new_thumb_y - track.y) / (track.height - thumb.height)
        self.scroll_y = int(pos_frac * max_s)
        self._clamp_scroll()

    # ---- события ----
    def handle_event(self, event):
        # Drag by title
        if event.type == pygame.MOUSEMOTION and self.dragging:
            mx, my = event.pos
            self.x = mx - self.drag_offset_x
            self.y = my - self.drag_offset_y
            self._clamp_to_screen()
            return True

        # Resize
        if event.type == pygame.MOUSEMOTION and self.resizing:
            mx, my = event.pos
            self.width = mx - self.x + self.resize_offset_x
            self.height = my - self.y + self.resize_offset_y
            self._clamp_size()
            self.on_resized()
            return True

        # Scrollbar drag
        if event.type == pygame.MOUSEMOTION and self.scroll_dragging:
            self._update_scroll_from_mouse(event.pos[1])
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            consumed = self.dragging or self.resizing or self.scroll_dragging
            self.dragging = False
            self.resizing = False
            self.scroll_dragging = False
            return consumed

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 1) «Назад»
            if self.back_rect().collidepoint(event.pos):
                if self.manager is not None:
                    self.manager.go_back()
                else:
                    self.close()
                return True

            # 2) Крестик — полный close + очистка стека
            if self.close_rect().collidepoint(event.pos):
                if self.manager is not None:
                    self.manager.close_all()
                else:
                    self.close()
                return True

            # 3) Resize grip
            if self.resizable and self.resize_rect().collidepoint(event.pos):
                self.resizing = True
                self.resize_offset_x = (self.x + self.width) - event.pos[0]
                self.resize_offset_y = (self.y + self.height) - event.pos[1]
                return True

            # 4) Scrollbar thumb
            thumb = self._scrollbar_thumb()
            if thumb is not None and thumb.collidepoint(event.pos):
                self.scroll_dragging = True
                self.scroll_drag_offset = event.pos[1] - thumb.y
                return True

            # 5) Scrollbar track (вне ползунка) — прыжок
            track = self._scrollbar_track()
            if track is not None and track.collidepoint(event.pos):
                th = self._scrollbar_thumb()
                if th is not None:
                    self.scroll_drag_offset = th.height // 2
                    self._update_scroll_from_mouse(event.pos[1])
                self.scroll_dragging = True
                return True

            # 6) Титлбар — drag
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True

            # 7) Контент
            if self.contains(event.pos):
                if self.content_rect().collidepoint(event.pos):
                    self._on_content_click(event.pos[0],
                                           event.pos[1] + self.scroll_y)
                return True

            # 8) Клик вне окна — полный close + очистка стека
            if self.manager is not None:
                self.manager.close_all()
            else:
                self.close()
            return True
        return False

    def _on_content_click(self, local_x, local_y):
        pass

    # ---- отрисовка ----
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

        # Кнопка «Назад» — стрелка
        br = self.back_rect()
        br_hover = br.collidepoint(mouse)
        back_bg = (90, 120, 170) if br_hover else (70, 90, 130)
        pygame.draw.rect(screen, back_bg, br, border_radius=5)
        pygame.draw.rect(screen, (200, 210, 230), br, 1, border_radius=5)
        # треугольная стрелка влево
        cx, cy = br.center
        pts = [(cx - 4, cy), (cx + 3, cy - 5), (cx + 3, cy + 5)]
        pygame.draw.polygon(screen, (240, 245, 255), pts)

        # Заголовок (сдвинули правее из-за кнопки «Назад»)
        title_surf = font.render(self.title, True, COLOR_TITLE)
        screen.blit(title_surf, (self.x + 34, self.y + 6))

        # Крестик
        cr = self.close_rect()
        cc = COLOR_CLOSE_HOVER if cr.collidepoint(mouse) else COLOR_CLOSE
        pygame.draw.rect(screen, cc, cr, border_radius=5)
        cxx, cyy = cr.center
        pygame.draw.line(screen, (255, 255, 255),
                         (cxx - 5, cyy - 5), (cxx + 5, cyy + 5), 2)
        pygame.draw.line(screen, (255, 255, 255),
                         (cxx - 5, cyy + 5), (cxx + 5, cyy - 5), 2)

    def _draw_scrollbar(self, screen):
        track = self._scrollbar_track()
        if track is None:
            return
        pygame.draw.rect(screen, COLOR_SCROLLBAR_BG, track, border_radius=3)
        thumb = self._scrollbar_thumb()
        mouse = pygame.mouse.get_pos()
        col = (COLOR_SCROLLBAR_HOVER
               if (thumb.collidepoint(mouse) or self.scroll_dragging)
               else COLOR_SCROLLBAR)
        pygame.draw.rect(screen, col, thumb, border_radius=3)

    def _draw_resize_grip(self, screen):
        if not self.resizable:
            return
        rr = self.resize_rect()
        mouse = pygame.mouse.get_pos()
        hover = rr.collidepoint(mouse) or self.resizing
        col = (210, 220, 240) if hover else (150, 160, 180)
        # три диагональные насечки
        for i, off in enumerate((2, 6, 10)):
            pygame.draw.line(screen, col,
                             (rr.right - off, rr.bottom - 2),
                             (rr.right - 2, rr.bottom - off), 2)

    def _draw_content(self, screen, font, small_font):
        cr = self.content_rect()
        content_surf = pygame.Surface((cr.width, cr.height), pygame.SRCALPHA)
        self._render_content(content_surf, font, small_font)
        screen.blit(content_surf, (cr.x, cr.y))
        self._draw_scrollbar(screen)
        self._draw_resize_grip(screen)

    def _render_content(self, surface, font, small_font):
        pass

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        
        
class MessageBox(Window):
    """Простое окно с сообщением и кнопкой OK."""
    def __init__(self, title, text, screen_w, screen_h):
        w, h = 380, 200
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, title)
        self.text = text
        self._ok_btn = pygame.Rect(self.x + self.width//2 - 60, self.y + h - 55, 120, 32)
        self._small_font = pygame.font.SysFont("arial,dejavusans", 14)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._ok_btn.collidepoint(event.pos):
                self.close()
                return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        lines = self.text.split("\n")
        y = self.y + HEADER_H + 20
        for line in lines:
            txt = self._small_font.render(line, True, (255,255,255))
            screen.blit(txt, (self.x + 20, y))
            y += 20
        # Кнопка OK (используем простой прямоугольник, чтобы не зависеть от widgets)
        pygame.draw.rect(screen, (60, 170, 60), self._ok_btn, border_radius=6)
        pygame.draw.rect(screen, (150, 200, 150), self._ok_btn, 1, border_radius=6)
        ok_txt = self._small_font.render("OK", True, (255,255,255))
        screen.blit(ok_txt, (self._ok_btn.centerx - ok_txt.get_width()//2, self._ok_btn.centery - ok_txt.get_height()//2))