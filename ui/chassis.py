#!/usr/bin/env python3
"""ui/chassis.py - логическое оборудование (шасси): хелперы, Merge и групповые настройки."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TITLE, COLOR_TEXT_DIM,
    HEADER_H, FOOTER_H,
)
from ui.base import Window
from ui.widgets import draw_fancy_button, draw_button_screen


# --------------------------------------------------------------------------
# Хелперы шасси
# --------------------------------------------------------------------------
def chassis_kind(equip):
    return "router" if equip["type"] == "router" else "switch"


def board_index(game, equip):
    grp = game.chassis_of(equip["id"])
    if grp is None:
        return 1
    return grp["boards"].index(equip["id"]) + 1


def port_name(game, equip, port_index):
    return f"{board_index(game, equip)}/{port_index + 1}"


def board_label(grp, equip_id, fallback_index):
    labels = grp.get("board_labels", {})
    return labels.get(equip_id, f"Плата {fallback_index}")


def create_chassis(game, kind, equip_list):
    grp = {
        "id": game._next_chassis_id,
        "kind": kind,
        "name": f"{'Router-Core' if kind == 'router' else 'Switch-Main'}-{game._next_chassis_id}",
        "boards": [e["id"] for e in equip_list],
        "board_labels": {},
    }
    game._next_chassis_id += 1
    game.chassis_groups.append(grp)
    return grp


def merge_into_chassis(game, base_equip, other_equip):
    kind = chassis_kind(base_equip)
    if chassis_kind(other_equip) != kind:
        print("Коммутация: нельзя объединять свитч с роутером")
        return None
    if game.chassis_of(other_equip["id"]) is not None:
        print("Коммутация: выбранное устройство уже в другом шасси")
        return None

    grp = game.chassis_of(base_equip["id"])
    if grp is None:
        grp = create_chassis(game, kind, [base_equip, other_equip])
    else:
        grp["boards"].append(other_equip["id"])
    print(f"Шасси '{grp['name']}': плат {len(grp['boards'])} "
          f"(добавлено #{other_equip['id']})")
    return grp


def mergeable_devices(game, equip):
    kind = chassis_kind(equip)
    loc = (equip["x"], equip["y"])
    devices = game.equipment_at.get(loc, [])
    out = []
    for d in devices:
        if d is equip:
            continue
        if chassis_kind(d) != kind:
            continue
        if game.chassis_of(d["id"]) is not None:
            continue
        out.append(d)
    return out


# --------------------------------------------------------------------------
# Окно Merge
# --------------------------------------------------------------------------
class ChassisMergeWindow(Window):
    def __init__(self, base_equip, screen_w, screen_h, game=None, manager=None):
        w, h = 360, 420
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Коммутация (шасси)")
        self.base = base_equip
        self.game = game
        self.manager = manager
        self.candidates = mergeable_devices(game, base_equip) if game else []
        self.selected_id = None
        self.row_h = 40
        self._rows = []
        self._merge_btn = pygame.Rect(0, 0, 0, 0)
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _compute_content_height(self):
        self.content_height = 40 + len(self.candidates) * self.row_h + 10

    def _layout(self):
        self._rows = []
        start_x = 14
        y = 36
        for d in self.candidates:
            rect = pygame.Rect(start_x, y, self.width - 40, self.row_h - 8)
            self._rows.append((rect, d))
            y += self.row_h

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        cx = local_x - cr.x
        cy = local_y - cr.y
        self._layout()
        for rect, d in self._rows:
            if rect.collidepoint(cx, cy):
                self.selected_id = d["id"]
                return

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._merge_btn.collidepoint(event.pos) and self.selected_id is not None:
                self._do_merge()
                return True
        return super().handle_event(event)

    def _do_merge(self):
        other = self.game.equipment_by_id(self.selected_id)
        if other is None:
            return
        merge_into_chassis(self.game, self.base, other)
        self.close()

    def _render_content(self, surface, font, small_font):
        from ui.net_helpers import equip_type_label
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 12)
        if not self.candidates:
            msg = small_font.render("Нет подходящих устройств", True, COLOR_TEXT_DIM)
            surface.blit(msg, (14, 40 - self.scroll_y))
            return
        hdr = small_font.render("Выбери устройство для объединения:",
                                True, COLOR_TEXT_DIM)
        surface.blit(hdr, (14, 8 - self.scroll_y))
        for rect, d in self._rows:
            ry = rect.y - self.scroll_y
            if ry + rect.height < 0 or ry > surface.get_height():
                continue
            selected = (d["id"] == self.selected_id)
            r2 = pygame.Rect(rect.x, ry, rect.width, rect.height)
            if selected:
                pygame.draw.rect(surface, (50, 110, 70), r2, border_radius=6)
                pygame.draw.rect(surface, (120, 220, 150), r2, 2, border_radius=6)
            else:
                pygame.draw.rect(surface, (55, 55, 62), r2, border_radius=6)
                pygame.draw.rect(surface, (110, 110, 120), r2, 1, border_radius=6)
            txt = tiny.render(f"{equip_type_label(d)} #{d['id']}", True, COLOR_TEXT)
            surface.blit(txt, (rect.x + 10, ry + rect.height // 2 - txt.get_height() // 2))

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._merge_btn = pygame.Rect(self.x + self.width // 2 - 80,
                                      self.y + self.height - FOOTER_H + 6, 160, 30)
        if self.selected_id is not None:
            draw_button_screen(screen, small_font, self._merge_btn, "⛓ Объединить")
        else:
            draw_fancy_button(screen, small_font, self._merge_btn,
                              "⛓ Объединить", state="disabled")


# --------------------------------------------------------------------------
# Групповое применение скорости + окно настроек группы
# --------------------------------------------------------------------------
def apply_speed_to_boards(game, boards, speed):
    from ui.net_helpers import port_in_lacp, find_cable_for_port, _notify_speed_changed
    for equip in boards:
        for i, port in enumerate(equip["ports"]):
            if port_in_lacp(equip, i) is not None:
                continue
            cable = find_cable_for_port(game, equip["id"], i)
            if cable is not None and cable["type"] == "cable_100":
                continue
            port["speed"] = speed
    _notify_speed_changed(game)


class ChassisGroupSettingsWindow(Window):
    SPEEDS = [("100M", 100), ("1G", 1000), ("10G", 10000)]

    def __init__(self, grp, screen_w, screen_h, game=None):
        w, h = 380, 460
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"Настройки: {grp.get('name', 'Шасси')}")
        self.grp = grp
        self.game = game
        self._buttons = []  # (rect, scope, equip_or_None, speed, label)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H)

    def _boards(self):
        return self.game.equipment_in_chassis(self.grp["id"]) if self.game else []

    def _layout(self):
        self._buttons = []
        bx = self.x + 20
        bw = self.width - 40
        y = self.y + HEADER_H + 36
        for label, sp in self.SPEEDS:
            rect = pygame.Rect(bx, y, bw, 32)
            self._buttons.append((rect, "chassis", None, sp, f"Всё шасси → {label}"))
            y += 38
        y += 10
        for idx, equip in enumerate(self._boards(), 1):
            name = board_label(self.grp, equip["id"], idx)
            for label, sp in self.SPEEDS:
                rect = pygame.Rect(bx, y, bw, 28)
                self._buttons.append((rect, "board", equip, sp, f"{name} → {label}"))
                y += 32
            y += 8

    def handle_event(self, event):
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
            for rect, scope, equip, sp, _ in self._buttons:
                if rect.collidepoint(event.pos):
                    if scope == "chassis":
                        apply_speed_to_boards(self.game, self._boards(), sp)
                        print(f"Шасси '{self.grp['name']}': все порты → {sp}М")
                    else:
                        apply_speed_to_boards(self.game, [equip], sp)
                        print(f"Плата #{equip['id']}: порты → {sp}М")
                    self.close()
                    return True
            if self.contains(event.pos):
                return True
            self.close()
            return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        hint = small_font.render("Применить скорость:", True, COLOR_TEXT_DIM)
        screen.blit(hint, (self.x + 20, self.y + HEADER_H + 8))
        for rect, scope, equip, sp, label in self._buttons:
            draw_button_screen(screen, small_font, rect, label)
            
            