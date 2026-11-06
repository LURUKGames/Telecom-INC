#!/usr/bin/env python3
"""ui/config/lacp.py - Окно создания/редактирования LACP-группы."""

import pygame
from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_PORT_EDGE, COLOR_PORT_LACP,
    COLOR_PORT_LACP_SEL,
)
from ui.app_window import AppWindow
from ui.widgets import _vgrad_rect, TextInput, aggregate_speed_label
from ui.chassis import port_name
from ui.net_helpers import equip_type_label

class LACPInputWindow(AppWindow):
    def __init__(self, devices, game, existing_group, callback, screen_w, screen_h):
        w, h = 760, 560
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        
        self.devices = devices
        self.game = game
        self.existing = existing_group
        self.callback = callback
        self.selected = []
        
        if existing_group:
            self.group_id = existing_group["id"]
            self.descriptor = existing_group.get("label", "")
            for eq in self.devices:
                for grp in eq.get("lacp_groups", []):
                    if grp["id"] == self.group_id:
                        self.selected = [(eq["id"], p) for p in grp["ports"]]
                        break
        else:
            all_ids = [g["id"] for eq in self.devices for g in eq.get("lacp_groups", [])]
            self.group_id = max(all_ids, default=0) + 1
            self.descriptor = ""
            
        self.id_input = TextInput((0, 0, 60, 26), initial_text=str(self.group_id), max_length=2, allowed_chars="0123456789")
        self.name_input = TextInput((0, 0, 200, 26), initial_text=self.descriptor, max_length=20)
        
        self._cells = []
        self._font = pygame.font.SysFont("arial,dejavusans", 14)
        self._small = pygame.font.SysFont("arial,dejavusans", 11)

        buttons = [
            {"text": "Сохранить" if self.existing else "Создать", "callback": self._validate_and_submit},
            {"text": "Отмена", "callback": self.close}
        ]
        
        title = "Редактирование LACP" if existing_group else "Создание LACP"
        super().__init__(x, y, w, h, title, buttons=buttons)
        
        self._update_content_height()

    def _update_content_height(self):
        box, gap, cols = 40, 6, 10
        total_h = 0
        for eq in self.devices:
            total_h += 24 
            rows = (len(eq["ports"]) + cols - 1) // cols
            total_h += rows * (box + gap) + 20
        self.content_height = total_h + 80 

    def is_text_input_active(self):
        return self.id_input.active or self.name_input.active

    def _layout(self):
        self._cells = []
        start_x = self.x + 20
        start_y = self.content_rect().y + 70 - self.scroll_y
        
        box, gap, cols = 40, 6, 10

        self.id_input.set_rect((self.x + 100, self.content_rect().y + 10, 50, 26))
        self.name_input.set_rect((self.x + 280, self.content_rect().y + 10, 200, 26))

        row_y = start_y
        for eq in self.devices:
            row_y += 24
            for i in range(len(eq["ports"])):
                c = i % cols
                r = i // cols
                px = start_x + c * (box + gap)
                py = row_y + r * (box + gap)
                self._cells.append((pygame.Rect(px, py, box, box), eq, i))
            rows = (len(eq["ports"]) + cols - 1) // cols
            row_y += rows * (box + gap) + 20

    def _validate_and_submit(self):
        try:
            gid = int(self.id_input.text)
            if not (1 <= gid <= 20): raise ValueError
        except ValueError:
            self.game.ui_manager.open_message_box("Ошибка", "Номер LACP должен быть от 1 до 20.")
            return

        if not self.existing:
            for eq in self.devices:
                for g in eq.get("lacp_groups", []):
                    if g["id"] == gid:
                        self.game.ui_manager.open_message_box("Ошибка", f"LACP-{gid} уже существует.")
                        return

        if len(self.selected) < 2:
            self.game.ui_manager.open_message_box("Ошибка", "Нужно выбрать минимум 2 порта.")
            return

        eids = {eid for eid, _ in self.selected}
        if len(eids) > 1:
            self.game.ui_manager.open_message_box("Ошибка", "Порты должны быть на одном устройстве.")
            return

        speeds = []
        for eid, pi in self.selected:
            for eq in self.devices:
                if eq["id"] == eid and 0 <= pi < len(eq["ports"]):
                    speeds.append(eq["ports"][pi].get("speed", 1000))
                    break
        base_speed = min(speeds) if speeds else 1000

        cb = self.callback
        sel = list(self.selected)
        desc = self.name_input.text.strip()
        self.close()
        cb(sel, gid, desc, self.existing is not None, base_speed)

    def handle_event(self, event):
        self._layout()
        
        # AppWindow проверит кнопки футера, ресайз и шапку
        if super().handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            if self.id_input.active: return self.id_input.handle_event(event, self._font)
            if self.name_input.active: return self.name_input.handle_event(event, self._font)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Поля ввода
            if self.id_input.handle_event(event, self._font): return True
            if self.name_input.handle_event(event, self._font): return True

            # Клик по контенту
            if self.content_rect().collidepoint(event.pos):
                for rect, eq, pi in self._cells:
                    if rect.collidepoint(event.pos):
                        in_other = any(pi in g["ports"] and (not self.existing or g["id"] != self.existing["id"]) for g in eq.get("lacp_groups", []))
                        if in_other:
                            self.game.ui_manager.open_message_box("Ошибка", "Этот порт уже занят.")
                            return True
                            
                        key = (eq["id"], pi)
                        if key in self.selected: self.selected.remove(key)
                        else: self.selected.append(key)
                        return True
        return False

    def draw_overlay(self, screen, font, small_font):
        self._layout()
        cr = self.content_rect()
        
        # 1. Отрисовка полей ввода (они в шапке)
        screen.blit(small_font.render("Номер (1-20):", True, COLOR_TEXT), (self.x + 20, cr.y + 16))
        self.id_input.draw(screen, self._font)
        screen.blit(small_font.render("Дескрипшн:", True, COLOR_TEXT), (self.x + 220, cr.y + 16))
        self.name_input.draw(screen, self._font)
        
        # 2. Итоговая скорость
        if self.selected:
            speeds = []
            for eid, pi in self.selected:
                for eq in self.devices:
                    if eq["id"] == eid and 0 <= pi < len(eq["ports"]):
                        speeds.append(eq["ports"][pi].get("speed", 1000))
                        break
            if speeds:
                base = min(speeds)
                total = base * len(speeds)
                if len(set(speeds)) > 1:
                    sp_text = f"Итог: {aggregate_speed_label(total)} (смешанные → min)"
                    sp_color = (255, 200, 100)
                else:
                    sp_text = f"Итог: {aggregate_speed_label(total)}"
                    sp_color = (100, 255, 100)
                sp_surf = self._font.render(sp_text, True, sp_color)
                screen.blit(sp_surf, (self.x + 500, cr.y + 16))

        # 3. Отрисовка сетки портов
        mouse = pygame.mouse.get_pos()
        for rect, eq, pi in self._cells:
            if not cr.colliderect(rect): continue
            
            is_selected = (eq["id"], pi) in self.selected
            in_other = any(pi in g["ports"] and (not self.existing or g["id"] != self.existing["id"]) for g in eq.get("lacp_groups", []))
            
            if in_other: color = (110, 110, 120)
            elif is_selected: color = (50, 200, 50)
            else: color = (200, 50, 50)
                
            hover = rect.collidepoint(mouse)
            edge = (255,255,255) if (is_selected or hover) else (150,150,150)
            
            _vgrad_rect(screen, rect, tuple(min(255, c + 30) for c in color), color, radius=6)
            pygame.draw.rect(screen, edge, rect, 2 if (is_selected or hover) else 1, border_radius=6)
            
            pname = port_name(self.game, eq, pi)
            txt = self._small.render(pname, True, (255,255,255))
            screen.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))
            
        # 4. Заголовки устройств
        start_x = self.x + 20
        row_y = cr.y + 70 - self.scroll_y
        box, gap, cols = 40, 6, 10
        for eq in self.devices:
            label = f"{equip_type_label(eq)} #{eq['id']}"
            if len(eq.get("boards", [])) > 1: label += f" [ШАССИ, плат: {len(eq['boards'])}]"
            hdr = small_font.render(label, True, (200, 220, 255))
            screen.blit(hdr, (start_x, row_y))
            
            rows = (len(eq["ports"]) + cols - 1) // cols
            row_y += 24 + rows * (box + gap) + 20
            
            