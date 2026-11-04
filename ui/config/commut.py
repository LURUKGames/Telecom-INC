#!/usr/bin/env python3
"""
ui/commut.py - Окно для объединения устройств (свитчей/роутеров) в единое шасси.
Позволяет создавать новые шасси, редактировать существующие (добавлять/убирать платы)
и менять имя шасси.
"""

import pygame
from config import COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TITLE, HEADER_H, FOOTER_H
from ui.base import Window
from ui.widgets import draw_button_screen, TextInput
from ui.net_helpers import equip_type_label


class CommutWindow(Window):
    def __init__(self, devices, game, callback, screen_w, screen_h):
        """
        devices: список всех доступных устройств в доме.
        game: ссылка на игру (нужна для вызова merge/unmerge).
        callback: функция, которая вызывается после создания/редактирования.
        """
        w, h = 500, 540
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Коммутация устройств (шасси)")
        self.devices = devices
        self.game = game
        self.callback = callback
        
        # Режимы окна: список, создание нового, редактирование
        self.mode = "list" 
        self.edit_eq = None
        
        # Временные данные для режима создания/редактирования
        self.selected = set()
        self.error_msg = ""
        self._error_timer = 0
        
        self.name_input = TextInput((0, 0, 250, 26), initial_text="", max_length=20)
        self.edit_name_input = TextInput((0, 0, 250, 26), initial_text="", max_length=20)
        self.edit_remove_boards = set()
        self.edit_add_ids = set()
        
        self._btns = []
        self._font = pygame.font.SysFont("arial,dejavusans", 14)
        self._small = pygame.font.SysFont("arial,dejavusans", 12)

    def is_text_input_active(self):
        return self.name_input.active or self.edit_name_input.active

    def _find_equip(self, eid):
        for d in self.devices:
            if d["id"] == eid: return d
        return None

    def _layout(self):
        """Пересчитывает координаты кнопок в зависимости от текущего режима."""
        self._btns = []
        if self.mode == "list":
            y = self.y + HEADER_H + 60
            for d in self.devices:
                rect = pygame.Rect(self.x + 20, y, self.width - 40, 40)
                self._btns.append(("device", rect, d))
                y += 48
            y += 10
            self._btn_plus = pygame.Rect(self.x + 20, y, 140, 32)
            
        elif self.mode == "create":
            y = self.y + HEADER_H + 80
            for d in self.devices:
                # В режиме создания показываем только одиночные устройства
                if len(d.get("boards", [])) > 1 or d.get("is_merged_into"):
                    continue
                rect = pygame.Rect(self.x + 20, y, self.width - 40, 40)
                self._btns.append(("create_device", rect, d))
                y += 48
            self.name_input.set_rect((self.x + 130, self.y + HEADER_H + 40, 250, 26))
            self._btn_ok = pygame.Rect(self.x + 20, self.y + self.height - 50, 200, 36)
            self._btn_cancel = pygame.Rect(self.x + self.width - 180, self.y + self.height - 50, 160, 36)
            
        elif self.mode == "edit":
            y = self.y + HEADER_H + 80
            eq = self.edit_eq
            if eq:
                # Показываем текущие платы (с кнопкой крестик для удаления)
                for b in eq.get("boards", []):
                    if b["board_id"] in self.edit_remove_boards:
                        continue
                    rect = pygame.Rect(self.x + 20, y, self.width - 100, 36)
                    self._btns.append(("edit_board_remove", rect, b))
                    x_btn = pygame.Rect(self.x + self.width - 70, y + 2, 32, 32)
                    self._btns.append(("edit_x", x_btn, b))
                    y += 44
                # Показываем свободные устройства, которые можно добавить
                for d in self.devices:
                    if len(d.get("boards", [])) > 1 or d.get("is_merged_into") or d["id"] == eq["id"]:
                        continue
                    rect = pygame.Rect(self.x + 20, y, self.width - 40, 36)
                    self._btns.append(("edit_add", rect, d))
                    y += 44
            self.edit_name_input.set_rect((self.x + 130, self.y + HEADER_H + 40, 250, 26))
            self._btn_ok = pygame.Rect(self.x + 20, self.y + self.height - 50, 200, 36)
            self._btn_cancel = pygame.Rect(self.x + self.width - 180, self.y + self.height - 50, 160, 36)

    def _submit_create(self):
        """Создание нового шасси."""
        if len(self.selected) < 2:
            self.error_msg = "Выберите 2+ устройства"
            self._error_timer = 180
            return
        name = self.name_input.text.strip() or "Новое шасси"
        ids = list(self.selected)
        self.close()
        self.callback(ids[0], ids[1:], name, True)

    def _submit_edit(self):
        """Применение изменений в существующем шасси."""
        eq = self.edit_eq
        if not eq: return
        
        # 1. Удаляем платы, которые отметили крестиком
        for bid in list(self.edit_remove_boards):
            if bid == 1: continue # Базовую плату удалять нельзя
            self.game.unmerge_equipment(eq, bid)
            
        # 2. Добавляем новые устройства (merge_equipment)
        for oid in list(self.edit_add_ids):
            other = self._find_equip(oid)
            if other:
                self.game.merge_equipment(eq, other)
                
        # 3. Обновляем имя
        eq["name"] = self.edit_name_input.text.strip() or eq.get("name", "Шасси")
        self.close()

    def handle_event(self, event):
        self._layout()
        if event.type == pygame.KEYDOWN:
            if self.name_input.active:
                return self.name_input.handle_event(event, self._font)
            if self.edit_name_input.active:
                return self.edit_name_input.handle_event(event, self._font)
            if event.key == pygame.K_ESCAPE:
                self.mode = "list" if self.mode != "list" else self.close()
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos) or self.back_rect().collidepoint(event.pos):
                self.close(); return True
            if self.name_input.handle_event(event, self._font): return True
            if self.edit_name_input.handle_event(event, self._font): return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
                
            # Логика кликов по режимам
            if self.mode == "list":
                if self._btn_plus.collidepoint(event.pos):
                    self.mode = "create"
                    self.selected = set()
                    self.name_input.text = "Новое шасси"
                    return True
                for kind, rect, obj in self._btns:
                    if kind == "device" and rect.collidepoint(event.pos):
                        if len(obj.get("boards", [])) > 1:
                            self.mode = "edit"
                            self.edit_eq = obj
                            self.edit_name_input.text = obj.get("name", "Шасси")
                            self.edit_remove_boards = set()
                            self.edit_add_ids = set()
                        return True
                        
            elif self.mode == "create":
                if self._btn_ok.collidepoint(event.pos):
                    self._submit_create(); return True
                if self._btn_cancel.collidepoint(event.pos):
                    self.mode = "list"; return True
                for kind, rect, obj in self._btns:
                    if kind == "create_device" and rect.collidepoint(event.pos):
                        if obj["id"] in self.selected: self.selected.discard(obj["id"])
                        else: self.selected.add(obj["id"])
                        return True
                        
            elif self.mode == "edit":
                if self._btn_ok.collidepoint(event.pos):
                    self._submit_edit(); return True
                if self._btn_cancel.collidepoint(event.pos):
                    self.mode = "list"; return True
                for kind, rect, obj in self._btns:
                    if not rect.collidepoint(event.pos): continue
                    if kind == "edit_x":
                        self.edit_remove_boards.add(obj["board_id"])
                        return True
                    if kind == "edit_add":
                        if obj["id"] in self.edit_add_ids: self.edit_add_ids.discard(obj["id"])
                        else: self.edit_add_ids.add(obj["id"])
                        return True
            return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        
        if self._error_timer > 0:
            self._error_timer -= 1
            err = small_font.render(self.error_msg, True, (255, 80, 80))
            screen.blit(err, (self.x + 20, self.y + HEADER_H + 6))
        
        if self.mode == "list":
            hint = small_font.render("Устройства в доме (нажмите на шасси для редактирования):", True, COLOR_TEXT_DIM)
            screen.blit(hint, (self.x + 20, self.y + HEADER_H + 10))
            for kind, rect, obj in self._btns:
                is_chassis = len(obj.get("boards", [])) > 1
                bg = (70, 90, 130) if is_chassis else (60, 60, 68)
                edge = (100, 200, 255) if is_chassis else (150, 150, 150)
                pygame.draw.rect(screen, bg, rect, border_radius=6)
                pygame.draw.rect(screen, edge, rect, 2 if is_chassis else 1, border_radius=6)
                
                label = f"{equip_type_label(obj)} #{obj['id']}"
                if is_chassis: label += f"  [ШАССИ: {obj.get('name', '')}, плат: {len(obj['boards'])}]"
                txt = self._font.render(label, True, COLOR_TEXT)
                screen.blit(txt, (rect.x + 15, rect.centery - txt.get_height()//2))
                
                if is_chassis:
                    pencil = self._small.render("✎", True, (200, 220, 255))
                    screen.blit(pencil, (rect.right - 30, rect.centery - pencil.get_height()//2))
            draw_button_screen(screen, small_font, self._btn_plus, "+ Commut")
        
        elif self.mode == "create":
            screen.blit(small_font.render("Имя шасси:", True, COLOR_TEXT), (self.x + 20, self.y + HEADER_H + 48))
            self.name_input.draw(screen, self._font)
            for kind, rect, obj in self._btns:
                is_selected = obj["id"] in self.selected
                bg = (50, 200, 50) if is_selected else (60, 60, 68)
                pygame.draw.rect(screen, bg, rect, border_radius=6)
                pygame.draw.rect(screen, (255,255,255) if is_selected else (150,150,150), rect, 2 if is_selected else 1, border_radius=6)
                txt = self._font.render(f"{equip_type_label(obj)} #{obj['id']}", True, COLOR_TEXT)
                screen.blit(txt, (rect.x + 15, rect.centery - txt.get_height()//2))
            draw_button_screen(screen, small_font, self._btn_ok, f"✔ Создать ({len(self.selected)})")
            draw_button_screen(screen, small_font, self._btn_cancel, "Отмена")
            
        elif self.mode == "edit":
            screen.blit(small_font.render("Имя шасси:", True, COLOR_TEXT), (self.x + 20, self.y + HEADER_H + 48))
            self.edit_name_input.draw(screen, self._font)
            screen.blit(small_font.render("Платы (× — убрать) и свободные устройства (клик — добавить):", True, COLOR_TEXT_DIM), (self.x + 20, self.y + HEADER_H + 68))
            
            for kind, rect, obj in self._btns:
                if kind == "edit_x":
                    pygame.draw.rect(screen, (200, 60, 60), rect, border_radius=4)
                    x_txt = self._small.render("×", True, (255,255,255))
                    screen.blit(x_txt, (rect.centerx - x_txt.get_width()//2, rect.centery - x_txt.get_height()//2))
                elif kind == "edit_board_remove":
                    pygame.draw.rect(screen, (100, 100, 110), rect, border_radius=6)
                    txt = self._small.render(obj.get("name", f"Плата {obj['board_id']}"), True, COLOR_TEXT)
                    screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height()//2))
                elif kind == "edit_add":
                    is_sel = obj["id"] in self.edit_add_ids
                    bg = (50, 200, 50) if is_sel else (60, 60, 68)
                    pygame.draw.rect(screen, bg, rect, border_radius=6)
                    pygame.draw.rect(screen, (200,200,200), rect, 1, border_radius=6)
                    txt = self._small.render(f"{equip_type_label(obj)} #{obj['id']}", True, COLOR_TEXT)
                    screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height()//2))
                    
            draw_button_screen(screen, small_font, self._btn_ok, "✔ Сохранить")
            draw_button_screen(screen, small_font, self._btn_cancel, "Отмена")