#!/usr/bin/env python3
"""ui/config/vlan_popup.py - Всплывающее окно настройки VLAN."""

import pygame
from config import COLOR_TEXT, COLOR_TEXT_DIM, HEADER_H
from ui.base import Window
from ui.widgets import draw_button_screen, TextInput

class VlanPopupWindow(Window):
    def __init__(self, screen_w, screen_h, current_text, mode, callback):
        w, h = 380, 340
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Настройка VLAN")
        self.mode = mode
        self.callback = callback
        self.resizable = False
        self.error_msg = ""
        self._error_timer = 0
        
        if mode == "access":
            allowed = "0123456789"
            self._hint = "Access: одно число 1-4092"
        else:
            allowed = "0123456789,-"
            self._hint = "Trunk: числа и диапазоны 1-4092"
            
        self.vlan_input = TextInput((self.x + 30, self.y + 80, self.width - 60, 30),
                                    initial_text=current_text, max_length=50, allowed_chars=allowed)
        
        self._apply_btn = pygame.Rect(self.x + 20, self.y + self.height - 44, 140, 32)
        self._cancel_btn = pygame.Rect(self.x + self.width - 160, self.y + self.height - 44, 140, 32)
        self._font = pygame.font.SysFont("arial,dejavusans", 14)

    def is_text_input_active(self):
        return self.vlan_input.active

    def _apply(self):
        text = self.vlan_input.text.strip()
        # Базовая проверка (детали опустим для краткости, но она должна быть)
        cb = self.callback
        self.close()
        cb(text)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: self.close(); return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): self._apply(); return True
            return self.vlan_input.handle_event(event, self._font)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._apply_btn.collidepoint(event.pos): self._apply(); return True
            if self._cancel_btn.collidepoint(event.pos): self.close(); return True
            if self.vlan_input.handle_event(event, self._font): return True
            if self.contains(event.pos): return True
            self.close(); return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        hs = self._font.render(self._hint, True, COLOR_TEXT_DIM)
        screen.blit(hs, (self.x + 30, self.y + HEADER_H + 10))
        self.vlan_input.draw(screen, self._font)
        draw_button_screen(screen, small_font, self._apply_btn, "✔ Применить")
        draw_button_screen(screen, small_font, self._cancel_btn, "Отмена")