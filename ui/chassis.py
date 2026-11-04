#!/usr/bin/env python3
"""ui/chassis.py - логическое оборудование (шасси): хелперы имён и окно Merge."""

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
    """Категория оборудования для объединения: 'switch' или 'router'."""
    return "router" if equip["type"] == "router" else "switch"


def board_index(game, equip):
    """Номер платы (1-based) внутри шасси, либо 1, если не в шасси."""
    grp = game.chassis_of(equip["id"])
    if grp is None:
        return 1
    return grp["boards"].index(equip["id"]) + 1


def port_name(game, equip, port_index):
    """Имя порта вида 'плата/порт'. Если не в шасси — плата всегда 1."""
    return f"{board_index(game, equip)}/{port_index + 1}"


def board_label(grp, equip_id, fallback_index):
    """Подпись платы из group['board_labels'] либо 'Плата N'."""
    labels = grp.get("board_labels", {})
    return labels.get(equip_id, f"Плата {fallback_index}")


def create_chassis(game, kind, equip_list):
    """Создаёт группу-шасси из списка equipment одного типа."""
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
    """
    Объединяет base и other в одно шасси.
    Если base уже в шасси — добавляет other как новую плату.
    Иначе создаёт новое шасси из [base, other].
    """
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
    """Устройства того же типа-категории в том же доме, которые можно добавить."""
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
# Окно Merge — выбор устройства для объединения в шасси
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
        self._rows = []          # (rect, equip)
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
        grp = merge_into_chassis(self.game, self.base, other)
        self.close()
        if grp is not None and self.manager is not None:
            if grp["kind"] == "router":
                self.manager.open_router_config(self.base)
            else:
                self.manager.open_switch_config(self.base)

    def _render_content(self, surface, font, small_font):
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
            from ui.net_helpers import equip_type_label
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
            
            