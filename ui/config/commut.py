#!/usr/bin/env python3
"""ui/config/commut.py - Окно для объединения устройств в единое шасси."""

import pygame
from config import COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TITLE
from ui.app_window import AppWindow
from ui.widgets import TextInput
from ui.net_helpers import equip_type_label

class CommutWindow(AppWindow):
    def __init__(self, devices, game, callback, screen_w, screen_h):
        w, h = 500, 540
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        
        self.devices = devices
        self.game = game
        self.callback = callback
        
        self.mode = "list" 
        self.edit_eq = None
        
        self.selected = set()
        self.name_input = TextInput((0, 0, 250, 26), initial_text="", max_length=20)
        self.edit_name_input = TextInput((0, 0, 250, 26), initial_text="", max_length=20)
        self.edit_remove_boards = set()
        self.edit_add_ids = set()
        
        self._btns = []
        self._font = pygame.font.SysFont("arial,dejavusans", 14)
        self._small = pygame.font.SysFont("arial,dejavusans", 12)

        super().__init__(x, y, w, h, "Коммутация устройств (шасси)")
        self._update_buttons()

    def _update_buttons(self):
        if self.mode == "list":
            self.buttons = [{"text": "+ Commut", "callback": self._enter_create}]
        elif self.mode == "create":
            self.buttons = [
                {"text": "✔ Создать", "callback": self._submit_create},
                {"text": "Отмена", "callback": self._enter_list}
            ]
        elif self.mode == "edit":
            self.buttons = [
                {"text": "✔ Сохранить", "callback": self._submit_edit},
                {"text": "Отмена", "callback": self._enter_list}
            ]
        self._update_footer_layout()
        self._update_content_height()

    def _update_content_height(self):
        h = 80
        if self.mode == "list":
            h += len(self.devices) * 48
        elif self.mode == "create":
            h += len([d for d in self.devices if not d.get("is_merged_into") and len(d.get("boards", [])) <= 1]) * 48
        elif self.mode == "edit":
            if self.edit_eq:
                h += len(self.edit_eq.get("boards", [])) * 44
                h += len([d for d in self.devices if not d.get("is_merged_into") and len(d.get("boards", [])) <= 1 and d["id"] != self.edit_eq["id"]]) * 44
        self.content_height = h + 20

    def _enter_create(self):
        self.mode = "create"
        self.selected = set()
        self.name_input.text = "Новое шасси"
        self._update_buttons()

    def _enter_list(self):
        self.mode = "list"
        self._update_buttons()

    def _enter_edit(self, eq):
        self.mode = "edit"
        self.edit_eq = eq
        self.edit_name_input.text = eq.get("name", "Шасси")
        self.edit_remove_boards = set()
        self.edit_add_ids = set()
        self._update_buttons()

    def is_text_input_active(self):
        return self.name_input.active or self.edit_name_input.active

    def _find_equip(self, eid):
        for d in self.devices:
            if d["id"] == eid: return d
        return None

    def _types_match(self, t1, t2):
        switches = ("switch_12", "switch_24")
        if t1 in switches and t2 in switches: return True
        if t1 == "router" and t2 == "router": return True
        return False

    def _layout(self):
        self._btns = []
        if self.mode == "list":
            y = 60 - self.scroll_y
            for d in self.devices:
                rect = pygame.Rect(20, y, self.width - 40, 40)
                self._btns.append(("device", rect, d))
                y += 48
            
        elif self.mode == "create":
            y = 80 - self.scroll_y
            for d in self.devices:
                if len(d.get("boards", [])) > 1 or d.get("is_merged_into"): continue
                rect = pygame.Rect(20, y, self.width - 40, 40)
                self._btns.append(("create_device", rect, d))
                y += 48
            self.name_input.set_rect((self.x + 130, self.content_rect().y + 40, 250, 26))
            
        elif self.mode == "edit":
            y = 80 - self.scroll_y
            eq = self.edit_eq
            if eq:
                for b in eq.get("boards", []):
                    if b["board_id"] in self.edit_remove_boards: continue
                    rect = pygame.Rect(20, y, self.width - 100, 36)
                    self._btns.append(("edit_board_remove", rect, b))
                    x_btn = pygame.Rect(self.width - 70, y + 2, 32, 32)
                    self._btns.append(("edit_x", x_btn, b))
                    y += 44
                for d in self.devices:
                    if len(d.get("boards", [])) > 1 or d.get("is_merged_into") or d["id"] == eq["id"]: continue
                    rect = pygame.Rect(20, y, self.width - 40, 36)
                    self._btns.append(("edit_add", rect, d))
                    y += 44
            self.edit_name_input.set_rect((self.x + 130, self.content_rect().y + 40, 250, 26))

    def _submit_create(self):
        if len(self.selected) < 2:
            self.game.ui_manager.open_message_box("Ошибка", "Выберите 2+ устройства для объединения.")
            return
        
        ids = list(self.selected)
        base_type = self._find_equip(ids[0])["type"]
        for i in ids[1:]:
            if not self._types_match(base_type, self._find_equip(i)["type"]):
                self.game.ui_manager.open_message_box("Ошибка", "Нельзя объединять свитчи и роутеры вместе.")
                return

        name = self.name_input.text.strip() or "Новое шасси"
        self.close()
        self.callback(ids[0], ids[1:], name, True, [])

    def _submit_edit(self):
        eq = self.edit_eq
        if not eq: return
        
        for oid in self.edit_add_ids:
            other = self._find_equip(oid)
            if other and not self._types_match(eq["type"], other["type"]):
                self.game.ui_manager.open_message_box("Ошибка", "Нельзя добавлять роутеры к свитчам (и наоборот).")
                return

        name = self.edit_name_input.text.strip() or eq.get("name", "Шасси")
        remove_ids = list(self.edit_remove_boards)
        add_ids = list(self.edit_add_ids)
        self.close()
        if self.callback:
            self.callback(eq["id"], add_ids, name, False, remove_ids)

    def handle_event(self, event):
        self._layout()
        
        if super().handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            if self.name_input.active: return self.name_input.handle_event(event, self._font)
            if self.edit_name_input.active: return self.edit_name_input.handle_event(event, self._font)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.name_input.handle_event(event, self._font): return True
            if self.edit_name_input.handle_event(event, self._font): return True
                
            cr = self.content_rect()
            local_pos = (event.pos[0] - cr.x, event.pos[1] - cr.y + self.scroll_y)
            
            for kind, rect, obj in self._btns:
                if not rect.collidepoint(local_pos): continue
                
                if kind == "device":
                    if len(obj.get("boards", [])) > 1:
                        self._enter_edit(obj)
                    return True
                elif kind == "create_device":
                    if obj["id"] in self.selected: self.selected.discard(obj["id"])
                    else: self.selected.add(obj["id"])
                    return True
                elif kind == "edit_x":
                    self.edit_remove_boards.add(obj["board_id"])
                    return True
                elif kind == "edit_add":
                    if obj["id"] in self.edit_add_ids: self.edit_add_ids.discard(obj["id"])
                    else: self.edit_add_ids.add(obj["id"])
                    return True
        return False

    def _render_content(self, surface, font, small_font):
        if self.mode == "list":
            hint = small_font.render("Устройства в доме (нажмите на шасси для редактирования):", True, COLOR_TEXT_DIM)
            surface.blit(hint, (20, 10))
            for kind, rect, obj in self._btns:
                is_chassis = len(obj.get("boards", [])) > 1
                bg = (70, 90, 130) if is_chassis else (60, 60, 68)
                edge = (100, 200, 255) if is_chassis else (150, 150, 150)
                pygame.draw.rect(surface, bg, rect, border_radius=6)
                pygame.draw.rect(surface, edge, rect, 2 if is_chassis else 1, border_radius=6)
                
                label = f"{equip_type_label(obj)} #{obj['id']}"
                if is_chassis: label += f"  [ШАССИ: {obj.get('name', '')}, плат: {len(obj['boards'])}]"
                txt = self._font.render(label, True, COLOR_TEXT)
                surface.blit(txt, (rect.x + 15, rect.centery - txt.get_height()//2))
                
                if is_chassis:
                    pencil = self._small.render("✎", True, (200, 220, 255))
                    surface.blit(pencil, (rect.right - 30, rect.centery - pencil.get_height()//2))
        
        elif self.mode == "create":
            surface.blit(small_font.render("Имя шасси:", True, COLOR_TEXT), (20, 48))
            self.name_input.draw(surface, self._font)
            for kind, rect, obj in self._btns:
                is_selected = obj["id"] in self.selected
                bg = (50, 200, 50) if is_selected else (60, 60, 68)
                pygame.draw.rect(surface, bg, rect, border_radius=6)
                pygame.draw.rect(surface, (255,255,255) if is_selected else (150,150,150), rect, 2 if is_selected else 1, border_radius=6)
                txt = self._font.render(f"{equip_type_label(obj)} #{obj['id']}", True, COLOR_TEXT)
                surface.blit(txt, (rect.x + 15, rect.centery - txt.get_height()//2))
            
        elif self.mode == "edit":
            surface.blit(small_font.render("Имя шасси:", True, COLOR_TEXT), (20, 48))
            self.edit_name_input.draw(surface, self._font)
            surface.blit(small_font.render("Платы (× — убрать) и свободные (клик — добавить):", True, COLOR_TEXT_DIM), (20, 68))
            
            for kind, rect, obj in self._btns:
                if kind == "edit_x":
                    pygame.draw.rect(surface, (200, 60, 60), rect, border_radius=4)
                    x_txt = self._small.render("×", True, (255,255,255))
                    surface.blit(x_txt, (rect.centerx - x_txt.get_width()//2, rect.centery - x_txt.get_height()//2))
                elif kind == "edit_board_remove":
                    pygame.draw.rect(surface, (100, 100, 110), rect, border_radius=6)
                    txt = self._small.render(obj.get("name", f"Плата {obj['board_id']}"), True, COLOR_TEXT)
                    surface.blit(txt, (rect.x + 10, rect.centery - txt.get_height()//2))
                elif kind == "edit_add":
                    is_sel = obj["id"] in self.edit_add_ids
                    bg = (50, 200, 50) if is_sel else (60, 60, 68)
                    pygame.draw.rect(surface, bg, rect, border_radius=6)
                    pygame.draw.rect(surface, (200,200,200), rect, 1, border_radius=6)
                    txt = self._small.render(f"{equip_type_label(obj)} #{obj['id']}", True, COLOR_TEXT)
                    surface.blit(txt, (rect.x + 10, rect.centery - txt.get_height()//2))
                    
                    