#!/usr/bin/env python3
"""
ui/app_window.py - Универсальное окно приложения (AppWindow).
Содержит шапку, футер с кнопками и скролл.
"""

import pygame
from config import HEADER_H
from ui.base import Window, MIN_W, MIN_H
from ui.widgets import draw_button_screen, screen_size

FOOTER_H = 50

class AppWindow(Window):
    def __init__(self, x, y, width, height, title, buttons=None):
        super().__init__(x, y, width, height, title)
        self.buttons = buttons or []
        
        self._footer_rect = pygame.Rect(0, 0, 0, 0)
        self._button_rects = []
        self._btn_font = pygame.font.SysFont("arial,dejavusans", 14)
        
        self._update_footer_layout()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H, self.width, self.height - HEADER_H - FOOTER_H)

    def _get_min_width_for_footer(self):
        n = len(self.buttons)
        if n == 0: return MIN_W
        margin, gap = 10, 8
        min_widths = []
        for btn in self.buttons:
            text_w = self._btn_font.size(btn.get("text", ""))[0]
            min_widths.append(text_w + 24)
        return sum(min_widths) + (n - 1) * gap + 2 * margin

    def _clamp_size(self):
        sw, sh = screen_size()
        self.width = max(self._get_min_width_for_footer(), min(self.width, sw - self.x))
        self.height = max(MIN_H, min(self.height, sh - self.y))

    def on_resized(self):
        self._update_footer_layout()
        self._clamp_scroll()

    def _update_footer_layout(self):
        n = len(self.buttons)
        self._footer_rect = pygame.Rect(self.x, self.y + self.height - FOOTER_H, self.width, FOOTER_H)
        self._button_rects = []
        
        if n == 0: return
        
        margin, gap, btn_h = 10, 8, 32
        available_w = self.width - 2 * margin - (n - 1) * gap
        
        min_widths = []
        for btn in self.buttons:
            text_w = self._btn_font.size(btn.get("text", ""))[0]
            min_widths.append(text_w + 24)
            
        total_weight = sum(min_widths)
        actual_widths = []
        if total_weight > 0:
            for w in min_widths:
                actual_widths.append(int(available_w * (w / total_weight)))
        else:
            actual_widths = [available_w // n] * n
            
        diff = available_w - sum(actual_widths)
        actual_widths[-1] += diff

        y = self._footer_rect.y + (FOOTER_H - btn_h) // 2
        x = self.x + margin
        
        for btn, w in zip(self.buttons, actual_widths):
            rect = pygame.Rect(x, y, w, btn_h)
            self._button_rects.append((rect, btn))
            x += w + gap

    def handle_event(self, event):
        self._update_footer_layout()
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 1. Ручка ресайза
            if self.resizable and self.resize_rect().collidepoint(event.pos):
                return super().handle_event(event)
                
            # 2. Футер
            if self._footer_rect.collidepoint(event.pos):
                for rect, btn in self._button_rects:
                    if rect.collidepoint(event.pos):
                        if not btn.get("disabled", False) and btn.get("callback"):
                            btn["callback"]()
                        return True
                return True
                
            # 3. Шапка (назад, закрыть, перетаскивание)
            if (self.titlebar_rect().collidepoint(event.pos) or 
                self.close_rect().collidepoint(event.pos) or 
                self.back_rect().collidepoint(event.pos)):
                return super().handle_event(event)
                
            # 4. Скроллбар (отдаем базовому классу для перетаскивания ползунка)
            thumb = self._scrollbar_thumb()
            track = self._scrollbar_track()
            if (thumb and thumb.collidepoint(event.pos)) or (track and track.collidepoint(event.pos)):
                return super().handle_event(event)
                
            # 5. Клик по контенту - возвращаем False, чтобы наследник (draw_overlay) перехватил
            return False
            
        # Для колесика, драга и ресайза
        return super().handle_event(event)
    

    def _draw_footer(self, screen):
        pygame.draw.rect(screen, (40, 42, 50), self._footer_rect)
        pygame.draw.line(screen, (90, 90, 100), 
                         (self._footer_rect.x, self._footer_rect.y), 
                         (self._footer_rect.right, self._footer_rect.y), 1)
        
        for rect, btn in self._button_rects:
            text = btn.get("text", "")
            disabled = btn.get("disabled", False)
            
            if disabled:
                pygame.draw.rect(screen, (60, 60, 66), rect, border_radius=6)
                pygame.draw.rect(screen, (95, 95, 105), rect, 1, border_radius=6)
                surf = self._btn_font.render(text, True, (140, 140, 150))
                screen.blit(surf, (rect.centerx - surf.get_width()//2, rect.centery - surf.get_height()//2))
            else:
                draw_button_screen(screen, self._btn_font, rect, text)

    def draw(self, screen, font, small_font):
        self._update_footer_layout()
        self._draw_frame(screen, font)
        self._clamp_scroll()
        
        cr = self.content_rect()
        surf_h = max(cr.height, self.content_height)
        content_surf = pygame.Surface((cr.width, surf_h), pygame.SRCALPHA)
        
        self._render_content(content_surf, font, small_font)
        
        old_clip = screen.get_clip()
        screen.set_clip(cr)
        
        screen.blit(content_surf, (cr.x, cr.y - self.scroll_y))
        self.draw_overlay(screen, font, small_font)
        
        screen.set_clip(old_clip)
        
        self._draw_footer(screen)
        self._draw_scrollbar(screen)
        self._draw_resize_grip(screen)
        
        # Рисуем всплывающие окна в самом конце
        self.draw_popup(screen, font, small_font)

    def _render_content(self, surface, font, small_font):
        pass

    def draw_overlay(self, screen, font, small_font):
        pass

    def draw_popup(self, screen, font, small_font):
        pass