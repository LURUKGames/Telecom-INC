#!/usr/bin/env python3
"""ui/config_window.py - окна конфигурации: Switch/Router (карта) и Universal (дом)."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TITLE, COLOR_STATUS_LACP, COLOR_LACP_ROW,
    COLOR_STATUS_UP, COLOR_STATUS_DOWN,
    HEADER_H, FOOTER_H,
    COL_NUM, COL_STATUS, COL_INPUT, COL_INPUT_W, COL_SPEED, COL_SPEED_W, ROW_H_CFG,
)
from ui.base import Window
from ui.widgets import (
    _vgrad_rect, draw_fancy_button, draw_button_screen,
    speed_label, TextInput, _screen_size,
)
from ui.net_helpers import (
    port_in_lacp, toggle_port_speed, toggle_lacp_speed,
    equip_type_label, port_status_text_color, _notify_speed_changed,
    find_cable_for_port,
)
from ui.lacp import LACPInputWindow
from ui.chassis import port_name, board_of_port


def board_label(_grp, _equip_id, fallback_index):
    return f"Плата {fallback_index}"


# ============================================================================
# СТАРЫЕ окна (SwitchConfigWindow/RouterConfigWindow) - клик по карте.
# Кнопки Merge/Group — заглушки (переехали в UniversalConfigWindow).
# ============================================================================
class SwitchConfigWindow(Window):
    def __init__(self, equip, screen_w, screen_h, game=None):
        w, h = 540, 560
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equip = equip
        self.game = game
        self.equip.setdefault("lacp_groups", [])
        self.chassis = None
        super().__init__(x, y, w, h, self._title())
        self.row_h = ROW_H_CFG
        self.name_input = None
        self.board_inputs = {}
        self.inputs = []
        self.lacp_inputs = []
        self._speed_buttons = []
        self._save_btn = pygame.Rect(0, 0, 0, 0)
        self._merge_btn = pygame.Rect(0, 0, 0, 0)
        self._group_btn = pygame.Rect(0, 0, 0, 0)
        self._add_lacp_btn = pygame.Rect(0, 0, 0, 0)
        self._cfg_font = pygame.font.SysFont("arial,dejavusans", 14)
        self._header_font = pygame.font.SysFont("arial,dejavusans", 12)
        self.lacp_input_window = None
        self._build_inputs()
        self._compute_content_height()

    def _title(self):
        return f"Config: {equip_type_label(self.equip)} #{self.equip['id']}"

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H + 22,
                           self.width, self.height - HEADER_H - FOOTER_H - 22)

    def _boards(self):
        return [self.equip]

    def _build_inputs(self):
        self.inputs = []
        self.lacp_inputs = []
        for equip in self._boards():
            for i, port in enumerate(equip["ports"]):
                ti = TextInput((0, 0, COL_INPUT_W, 26),
                               initial_text=port.get("label", ""), max_length=15)
                self.inputs.append((equip, i, ti))
            for grp in equip.get("lacp_groups", []):
                ti = TextInput((0, 0, COL_INPUT_W, 26),
                               initial_text=grp.get("label", ""), max_length=15)
                self.lacp_inputs.append((equip, grp, ti))

    def _rows_layout(self):
        rows = []
        for equip in self._boards():
            for i, _ in enumerate(equip["ports"]):
                rows.append(("port", equip, i))
            for grp in equip.get("lacp_groups", []):
                rows.append(("lacp", equip, grp))
        rows.append(("actions", None, None))
        return rows

    def _compute_content_height(self):
        n = len(self._rows_layout())
        self.content_height = 10 + n * self.row_h + 20

    def _row_y(self, i):
        return 10 + i * self.row_h

    def is_text_input_active(self):
        if self.lacp_input_window is not None:
            return True
        return (any(ti.active for _, _, ti in self.inputs)
                or any(ti.active for _, _, ti in self.lacp_inputs))

    def _port_input(self, equip, i):
        for e, pi, ti in self.inputs:
            if e is equip and pi == i:
                return ti
        return None

    def _lacp_input(self, equip, grp):
        for e, g, ti in self.lacp_inputs:
            if e is equip and g is grp:
                return ti
        return None

    def _sync_positions(self):
        cr = self.content_rect()
        self._speed_buttons = []
        rows = self._rows_layout()
        for idx, row in enumerate(rows):
            ry = cr.y + self._row_y(idx) - self.scroll_y
            kind = row[0]
            if kind == "port":
                equip, i = row[1], row[2]
                ti = self._port_input(equip, i)
                if ti is not None:
                    ti.set_rect((cr.x + COL_INPUT, ry + 6, COL_INPUT_W, 26))
                if port_in_lacp(equip, i) is None:
                    btn = pygame.Rect(cr.x + COL_SPEED, ry + 6, COL_SPEED_W, 26)
                    self._speed_buttons.append((btn, "port", equip, i))
            elif kind == "lacp":
                equip, grp = row[1], row[2]
                ti = self._lacp_input(equip, grp)
                if ti is not None:
                    ti.set_rect((cr.x + COL_INPUT, ry + 6, COL_INPUT_W, 26))
                btn = pygame.Rect(cr.x + COL_SPEED, ry + 6, COL_SPEED_W, 26)
                self._speed_buttons.append((btn, "lacp", equip, grp))
            elif kind == "actions":
                self._add_lacp_btn = pygame.Rect(cr.x + COL_NUM, ry + 6, 150, 28)

    def _all_inputs(self):
        for _, _, ti in self.inputs:
            yield ti
        for _, _, ti in self.lacp_inputs:
            yield ti

    def handle_event(self, event):
        if self.lacp_input_window is not None:
            handled = self.lacp_input_window.handle_event(event)
            if self.lacp_input_window.is_closed:
                self.lacp_input_window = None
            return handled or True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._save_btn.collidepoint(event.pos):
                self._save_and_close()
                return True
            if self._merge_btn.collidepoint(event.pos):
                print("Commut перенесён в окно Оборудование (UniversalConfigWindow)")
                return True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._sync_positions()

            if event.type == pygame.KEYDOWN:
                for _, _, ti in self.inputs:
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                for _, _, ti in self.lacp_inputs:
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                return False

            if event.button == 1:
                if self._add_lacp_btn.collidepoint(event.pos):
                    self._open_lacp_input()
                    return True
                cr = self.content_rect()
                in_content = cr.collidepoint(event.pos)
                clicked_input = False
                if in_content:
                    for equip, i, ti in self.inputs:
                        if port_in_lacp(equip, i) is not None:
                            continue
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                    for _, _, ti in self.lacp_inputs:
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                else:
                    for ti in self._all_inputs():
                        ti.active = False
                if clicked_input:
                    return True
                if in_content:
                    for btn, kind, equip, ref in self._speed_buttons:
                        if btn.collidepoint(event.pos):
                            if kind == "port":
                                toggle_port_speed(self.game, equip, ref)
                            else:
                                toggle_lacp_speed(ref, self.game)
                            return True

        return super().handle_event(event)

    def _open_lacp_input(self):
        sw, sh = _screen_size()
        target = self.equip

        def on_submit(selected_ports):
            ports = sorted(p for p in selected_ports
                           if port_in_lacp(target, p) is None)
            if len(ports) < 2:
                print("LACP: нужно выбрать минимум 2 свободных порта")
                return
            new_id = max([g["id"] for g in target["lacp_groups"]], default=0) + 1
            grp = {"id": new_id, "name": f"LACP-{new_id}",
                   "ports": ports, "speed": 1000, "label": "",
                   "mode": "trunk", "vlan_string": "", "admin_state": "up"}
            target["lacp_groups"].append(grp)
            self._persist_labels()
            self._build_inputs()
            self._compute_content_height()
            _notify_speed_changed(self.game)
            print(f"Создана группа {grp['name']} из портов "
                  f"{[p + 1 for p in ports]}")

        self.lacp_input_window = LACPInputWindow(
            on_submit, sw, sh, target, lambda p: port_in_lacp(target, p) is None)

    def _persist_labels(self):
        for equip, i, ti in self.inputs:
            if port_in_lacp(equip, i) is None:
                equip["ports"][i]["label"] = ti.text
        for _, grp, ti in self.lacp_inputs:
            grp["label"] = ti.text

    def _save_and_close(self):
        self._persist_labels()
        print(f"Настройки сохранены: #{self.equip['id']}")
        self.close()

    def _draw_col_headers(self, screen):
        cr = self.content_rect()
        y = cr.y - 18
        headers = [(COL_NUM, "Порт"), (COL_STATUS, "Статус"),
                   (COL_INPUT, "Подпись"), (COL_SPEED, "Скорость")]
        for col_x, text in headers:
            surf = self._header_font.render(text, True, COLOR_TEXT_DIM)
            screen.blit(surf, (cr.x + col_x, y))
        pygame.draw.line(screen, (90, 90, 100),
                         (self.x + 8, cr.y - 2),
                         (self.x + self.width - 8, cr.y - 2), 1)

    def _render_content(self, surface, font, small_font):
        tiny = pygame.font.SysFont("arial,dejavusans", 12)
        rows = self._rows_layout()
        for idx, row in enumerate(rows):
            ry = self._row_y(idx) - self.scroll_y
            if ry + self.row_h < 0 or ry > surface.get_height():
                continue
            kind = row[0]
            if kind == "port":
                equip, i = row[1], row[2]
                in_lacp = port_in_lacp(equip, i)
                num_col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
                pname = port_name(self.game, equip, i) if self.game else str(i + 1)
                num = font.render(pname, True, num_col)
                surface.blit(num, (COL_NUM, ry + 8))
                status, col = port_status_text_color(self.game, equip, i)
                st = tiny.render(status, True, col)
                surface.blit(st, (COL_STATUS, ry + 10))
            elif kind == "lacp":
                equip, grp = row[1], row[2]
                name = font.render(grp["name"], True, COLOR_LACP_ROW)
                surface.blit(name, (COL_NUM, ry + 8))
                members = ",".join(str(p + 1) for p in grp["ports"])
                st = tiny.render(f"порты: {members}", True, COLOR_LACP_ROW)
                surface.blit(st, (COL_STATUS, ry + 10))

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_col_headers(screen)
        self._draw_content(screen, font, small_font)
        self._sync_positions()
        cr = self.content_rect()
        old_clip = screen.get_clip()
        screen.set_clip(cr)
        for equip, i, ti in self.inputs:
            if port_in_lacp(equip, i) is not None:
                continue
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)
        for _, _, ti in self.lacp_inputs:
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)
        for btn, kind, equip, ref in self._speed_buttons:
            if cr.y - 30 <= btn.y <= cr.bottom:
                spd = (equip["ports"][ref]["speed"] if kind == "port"
                       else ref.get("speed", 1000))
                draw_button_screen(screen, small_font, btn, speed_label(spd))
        if cr.y - 30 <= self._add_lacp_btn.y <= cr.bottom:
            draw_button_screen(screen, small_font, self._add_lacp_btn, "+ADD_LACP")
        screen.set_clip(old_clip)

        self._save_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                     self.y + self.height - FOOTER_H + 6, 140, 30)
        draw_button_screen(screen, small_font, self._save_btn, "💾 Сохранить")

        if self.lacp_input_window is not None:
            self.lacp_input_window.draw(screen, font, small_font)


class RouterConfigWindow(SwitchConfigWindow):
    def __init__(self, equip, screen_w, screen_h, game=None):
        super().__init__(equip, screen_w, screen_h, game=game)
        self.width, self.height = 540, 400
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self._compute_content_height()
        
    # ============================================================================
# VlanPopupWindow — всплывающее окно настройки VLAN
# ============================================================================
VLAN_BOX_SIZE = 200


class VlanPopupWindow(Window):
    """
    Всплывающее окно настройки VLAN для порта или LACP-группы.
    callback(vlan_string) вызывается при "Применить".
    """

    def __init__(self, screen_w, screen_h, current_text, mode, callback):
        w, h = 360, 340
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Настройка VLAN")
        self.mode = mode
        self.callback = callback
        self.resizable = False
        # Многострочный текст — храним как список строк
        self.lines = (current_text or "").split("\n")
        if not self.lines:
            self.lines = [""]
        self.cursor_line = len(self.lines) - 1
        self.cursor_col = len(self.lines[-1])
        self._cursor_timer = 0
        self._apply_btn = pygame.Rect(0, 0, 0, 0)
        self._cancel_btn = pygame.Rect(0, 0, 0, 0)
        self._text_rect = pygame.Rect(0, 0, 0, 0)
        self._font = pygame.font.SysFont("arial,dejavusans", 14)
        self._hint_font = pygame.font.SysFont("arial,dejavusans", 12)
        self._focused = True

    def is_text_input_active(self):
        return self._focused

    def _layout(self):
        self._text_rect = pygame.Rect(self.x + (self.width - VLAN_BOX_SIZE) // 2,
                                      self.y + HEADER_H + 44,
                                      VLAN_BOX_SIZE, VLAN_BOX_SIZE)
        by = self.y + self.height - 44
        self._apply_btn = pygame.Rect(self.x + 20, by, 140, 32)
        self._cancel_btn = pygame.Rect(self.x + self.width - 160, by, 140, 32)

    def _insert_char(self, ch):
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = (line[:self.cursor_col]
                                        + ch + line[self.cursor_col:])
        self.cursor_col += 1

    def _backspace(self):
        if self.cursor_col > 0:
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = (line[:self.cursor_col - 1]
                                            + line[self.cursor_col:])
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            prev_len = len(self.lines[self.cursor_line - 1])
            self.lines[self.cursor_line - 1] += self.lines[self.cursor_line]
            del self.lines[self.cursor_line]
            self.cursor_line -= 1
            self.cursor_col = prev_len

    def _newline(self):
        line = self.lines[self.cursor_line]
        left = line[:self.cursor_col]
        right = line[self.cursor_col:]
        self.lines[self.cursor_line] = left
        self.lines.insert(self.cursor_line + 1, right)
        self.cursor_line += 1
        self.cursor_col = 0

    def _get_text(self):
        return "\n".join(self.lines)

    def _apply(self):
        text = self._get_text().strip()
        cb = self.callback
        self.close()
        cb(text)

    def handle_event(self, event):
        self._layout()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self._newline()
                else:
                    self._apply()
                return True
            if event.key == pygame.K_BACKSPACE:
                self._backspace()
                self._cursor_timer = 0
                return True
            if event.key == pygame.K_LEFT:
                if self.cursor_col > 0:
                    self.cursor_col -= 1
                elif self.cursor_line > 0:
                    self.cursor_line -= 1
                    self.cursor_col = len(self.lines[self.cursor_line])
                self._cursor_timer = 0
                return True
            if event.key == pygame.K_RIGHT:
                if self.cursor_col < len(self.lines[self.cursor_line]):
                    self.cursor_col += 1
                elif self.cursor_line < len(self.lines) - 1:
                    self.cursor_line += 1
                    self.cursor_col = 0
                self._cursor_timer = 0
                return True
            if event.key == pygame.K_UP and self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
                self._cursor_timer = 0
                return True
            if event.key == pygame.K_DOWN and self.cursor_line < len(self.lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
                self._cursor_timer = 0
                return True
            ch = event.unicode
            if ch and ch.isprintable():
                self._insert_char(ch)
                self._cursor_timer = 0
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._apply_btn.collidepoint(event.pos):
                self._apply()
                return True
            if self._cancel_btn.collidepoint(event.pos):
                self.close()
                return True
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self.back_rect().collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            if self._text_rect.collidepoint(event.pos):
                return True
            if self.contains(event.pos):
                return True
            self.close()
            return True

        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()

        if self.mode == "access":
            hint = "Access: один VLAN (1-4092)"
        else:
            hint = "Пример: 1-4092 или 1,2,3,4,20,30,2500"
        hs = self._hint_font.render(hint, True, COLOR_TEXT_DIM)
        screen.blit(hs, (self.x + 30, self.y + HEADER_H + 10))
        ms = self._hint_font.render(f"Режим: {self.mode}", True, COLOR_TEXT_DIM)
        screen.blit(ms, (self.x + 30, self.y + HEADER_H + 26))

        pygame.draw.rect(screen, (30, 30, 34), self._text_rect, border_radius=6)
        pygame.draw.rect(screen, (120, 160, 200), self._text_rect, 2, border_radius=6)

        old_clip = screen.get_clip()
        screen.set_clip(self._text_rect)
        line_h = self._font.get_height() + 2
        for idx, line in enumerate(self.lines):
            ls = self._font.render(line, True, COLOR_TEXT)
            screen.blit(ls, (self._text_rect.x + 6,
                             self._text_rect.y + 6 + idx * line_h))
        self._cursor_timer = (self._cursor_timer + 1) % 60
        if self._cursor_timer < 30:
            cur_line_text = self.lines[self.cursor_line][:self.cursor_col]
            cx = self._text_rect.x + 6 + self._font.size(cur_line_text)[0]
            cy = self._text_rect.y + 6 + self.cursor_line * line_h
            pygame.draw.line(screen, COLOR_TEXT,
                             (cx, cy), (cx, cy + line_h - 2), 1)
        screen.set_clip(old_clip)

        draw_button_screen(screen, small_font, self._apply_btn, "✔ Применить")
        draw_button_screen(screen, small_font, self._cancel_btn, "Отмена")


# ============================================================================
# UniversalConfigWindow — главное окно конфигурации дома.
# Режимы выделения: NORMAL | COMMUT | LACP
# ============================================================================
UCW_ROW_H = 46
UCW_X_PORT = 10
UCW_X_LINK = 60
UCW_LINK_W = 60
UCW_LINK_H = 26
UCW_X_DESC = 130
UCW_DESC_W = 130
UCW_X_SPEED = 270
UCW_SPEED_W = 60
UCW_X_MODE = 340
UCW_MODE_W = 80
UCW_X_VLAN = 430
UCW_VLAN_W = 110
UCW_SECTION_HDR_H = 34
UCW_SECTION_GAP = 10
UCW_FOOTER_H = 50

COLOR_LINK_UP = (60, 190, 90)
COLOR_LINK_DOWN = (210, 70, 70)
COLOR_LINK_EDGE = (230, 230, 230)
COLOR_BTN_DIS_BG = (60, 60, 66)
COLOR_BTN_DIS_EDGE = (95, 95, 105)
COLOR_SEL_PORT = (90, 160, 240)
COLOR_SEL_SECTION = (70, 130, 200)
COLOR_MODE_BANNER = (50, 90, 150)


def _ensure_port_fields(port):
    port.setdefault("admin_state", "up")
    port.setdefault("vlan_string", "")
    port.setdefault("mode", "access")


def _ensure_lacp_fields(grp):
    grp.setdefault("admin_state", "up")
    grp.setdefault("vlan_string", "")
    grp.setdefault("mode", "trunk")
    grp.setdefault("label", "")


def _port_link_state(port):
    if port.get("admin_state", "up") == "shut":
        return "shut"
    return "down" if port.get("free", True) else "up"


def _lacp_link_state(equip, grp):
    """LACP up, если admin_state=up И хотя бы один физпорт группы занят."""
    if grp.get("admin_state", "up") == "shut":
        return "shut"
    for pi in grp["ports"]:
        if 0 <= pi < len(equip["ports"]):
            if not equip["ports"][pi].get("free", True):
                return "up"
    return "down"


def _vlan_preview(text):
    """Внутрь кнопки VLAN: первые 4 значения; пусто → 'VLAN'."""
    if not text:
        return "VLAN"
    import re
    parts = [p.strip() for p in re.split(r"[,\n]", text) if p.strip()]
    if not parts:
        return "VLAN"
    shown = parts[:4]
    suffix = "..." if len(parts) > 4 else ""
    return ",".join(shown) + suffix


def _find_cable_100(game, equip_id, port_index):
    if game is None:
        return False
    for cable in game.cables:
        a_match = cable["a"] == equip_id and cable["port_a"] == port_index
        b_match = cable.get("b") == equip_id and cable.get("port_b") == port_index
        if a_match or b_match:
            return cable["type"] == "cable_100"
    return False

class UniversalConfigWindow(Window):
    """Одно окно на все устройства дома. Режимы: NORMAL / COMMUT / LACP."""

    MODE_NORMAL = "normal"
    MODE_COMMUT = "commut"
    MODE_LACP = "lacp"

    def __init__(self, devices, screen_w, screen_h, game=None):
        w, h = 720, 620
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Конфигурация оборудования")
        self.game = game
        self.row_h = UCW_ROW_H
        self._cfg_font = pygame.font.SysFont("arial,dejavusans", 14)
        self._header_font = pygame.font.SysFont("arial,dejavusans", 13)
        self._tiny = pygame.font.SysFont("arial,dejavusans", 11)

        self.devices = self._visible_devices(devices)
        self._init_fields()

        self.inputs = {}
        self._build_inputs()

        self.mode = self.MODE_NORMAL
        self.selected_devices = set()
        self.selected_ports = []

        self.active_section_eid = (self.devices[0]["id"] if self.devices else None)
        self.popup = None
        self._pending_unmerge = None

        self._section_hits = []
        self._link_hits = []
        self._desc_rects = {}
        self._speed_hits = []
        self._mode_hits = []
        self._vlan_hits = []

        # Футер: LACP, Commut, Save (без Setting Group и Unmerge)
        self._btn_lacp = pygame.Rect(0, 0, 0, 0)
        self._btn_commut = pygame.Rect(0, 0, 0, 0)
        self._btn_save = pygame.Rect(0, 0, 0, 0)

        self._compute_content_height()

    # ---- подготовка ----
    def _visible_devices(self, devices):
        return [d for d in devices if not d.get("is_merged_into")]

    def _init_fields(self):
        for equip in self.devices:
            equip.setdefault("lacp_groups", [])
            equip.setdefault("boards", [{"board_id": 1, "port_range": (0, len(equip["ports"]))}])
            for port in equip["ports"]:
                _ensure_port_fields(port)
            for grp in equip["lacp_groups"]:
                _ensure_lacp_fields(grp)

    def _build_inputs(self):
        self.inputs = {}
        for equip in self.devices:
            for i, port in enumerate(equip["ports"]):
                self.inputs[("port", equip["id"], i)] = TextInput(
                    (0, 0, UCW_DESC_W, 26), initial_text=port.get("label", ""), max_length=15)
            for grp in equip["lacp_groups"]:
                self.inputs[("lacp", equip["id"], grp["id"])] = TextInput(
                    (0, 0, UCW_DESC_W, 26), initial_text=grp.get("label", ""), max_length=15)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H, self.width, self.height - HEADER_H - UCW_FOOTER_H)

    def on_resized(self):
        self._compute_content_height()
        self._clamp_scroll()

    def _section_rows(self, equip):
        return 1 + len(equip["ports"]) + len(equip["lacp_groups"])

    def _compute_content_height(self):
        total = 10
        for equip in self.devices:
            total += self.row_h
            total += (self._section_rows(equip) - 1) * self.row_h
            total += UCW_SECTION_GAP
        self.content_height = total + 20

    def _find_equip(self, eid):
        for d in self.devices:
            if d["id"] == eid:
                return d
        return None

    # ---- layout + hit-boxes ----
    def _sync_positions(self):
        cr = self.content_rect()
        self._section_hits = []
        self._link_hits = []
        self._desc_rects = {}
        self._speed_hits = []
        self._mode_hits = []
        self._vlan_hits = []

        y = 10
        for equip in self.devices:
            ry = cr.y + y - self.scroll_y
            hdr_rect = pygame.Rect(cr.x, ry, cr.width, UCW_SECTION_HDR_H)
            self._section_hits.append((hdr_rect, equip))
            y += self.row_h

            for i, port in enumerate(equip["ports"]):
                ry = cr.y + y - self.scroll_y
                self._link_hits.append((pygame.Rect(cr.x + UCW_X_LINK, ry + 10, UCW_LINK_W, UCW_LINK_H), equip, i, "port", None))
                self._desc_rects[("port", equip["id"], i)] = pygame.Rect(cr.x + UCW_X_DESC, ry + 10, UCW_DESC_W, 26)
                self._speed_hits.append((pygame.Rect(cr.x + UCW_X_SPEED, ry + 10, UCW_SPEED_W, 26), "port", equip, i))
                self._mode_hits.append((pygame.Rect(cr.x + UCW_X_MODE, ry + 10, UCW_MODE_W, 26), "port", equip, i))
                self._vlan_hits.append((pygame.Rect(cr.x + UCW_X_VLAN, ry + 10, UCW_VLAN_W, 26), "port", equip, i))
                y += self.row_h

            for grp in equip["lacp_groups"]:
                ry = cr.y + y - self.scroll_y
                self._link_hits.append((pygame.Rect(cr.x + UCW_X_LINK, ry + 10, UCW_LINK_W, UCW_LINK_H), equip, None, "lacp", grp))
                self._desc_rects[("lacp", equip["id"], grp["id"])] = pygame.Rect(cr.x + UCW_X_DESC, ry + 10, UCW_DESC_W, 26)
                self._speed_hits.append((pygame.Rect(cr.x + UCW_X_SPEED, ry + 10, UCW_SPEED_W, 26), "lacp", equip, grp))
                self._mode_hits.append((pygame.Rect(cr.x + UCW_X_MODE, ry + 10, UCW_MODE_W, 26), "lacp", equip, grp))
                self._vlan_hits.append((pygame.Rect(cr.x + UCW_X_VLAN, ry + 10, UCW_VLAN_W, 26), "lacp", equip, grp))
                y += self.row_h
            y += UCW_SECTION_GAP

        for key, rect in self._desc_rects.items():
            ti = self.inputs.get(key)
            if ti is not None:
                ti.set_rect(rect)

        # Футер: LACP (слева), Commut (рядом), Save (справа)
        fx = self.x + 10
        fy = self.y + self.height - UCW_FOOTER_H + 10
        bw, bh, gap = 110, 30, 6
        self._btn_lacp = pygame.Rect(fx, fy, bw, bh)
        self._btn_commut = pygame.Rect(fx + (bw + gap), fy, bw, bh)
        self._btn_save = pygame.Rect(self.x + self.width - bw - 10, fy, bw, bh)

    def is_text_input_active(self):
        if self.popup is not None:
            return True
        return any(ti.active for ti in self.inputs.values())

    # ---- режимы ----
    def _enter_mode(self, mode):
        if self.mode == mode:
            self._exit_mode()
            return
        self._exit_mode()
        self.mode = mode
        if mode == self.MODE_COMMUT:
            print("Режим COMMUT: кликай по заголовкам, чтобы выбрать 2+ устройства для слияния.")
            print("Если устройство уже шасси (плат > 1) — клик по нему разъединит его.")
        elif mode == self.MODE_LACP:
            print("Режим LACP: кликай по овалам Link у физпортов; повторный LKM — снять")

    def _exit_mode(self):
        self.mode = self.MODE_NORMAL
        self.selected_devices.clear()
        self.selected_ports.clear()

    def _confirm_commut(self):
        if len(self.selected_devices) < 2:
            print("Commut: выбери минимум 2 устройства")
            return
        ids = list(self.selected_devices)
        host_id = ids[0]
        others = [i for i in ids[1:]]
        host = self._find_equip(host_id)
        if host is None:
            self._exit_mode()
            return
        for oid in others:
            other = self._find_equip(oid)
            if other is not None:
                self.game.merge_equipment(host, other)
        
        # Обновляем список устройств после слияния
        self.devices = self._visible_devices(self.devices)
        self._init_fields()
        self._build_inputs()
        self._compute_content_height()
        self.active_section_eid = host["id"]
        self._exit_mode()

    def _do_unmerge(self, eq):
        if len(eq.get("boards", [])) < 2:
            return
        last = max(eq["boards"], key=lambda b: b["board_id"])
        ok, mixed = self.game.can_unmerge(eq, last["board_id"])
        if mixed:
            if getattr(self, "_pending_unmerge", None) == last["board_id"]:
                self.game.unmerge_equipment(eq, last["board_id"], force=True)
                self._pending_unmerge = None
            else:
                self._pending_unmerge = last["board_id"]
                print(f"Unmerge: LACP будет сломан ({', '.join(mixed)}). Повторный клик по заголовку — подтвердить.")
                return
        else:
            self.game.unmerge_equipment(eq, last["board_id"])
        
        # Возвращаем "вынырнувшее" устройство обратно в список
        for d in self.game.equipment:
            if (d["x"], d["y"]) == (eq["x"], eq["y"]) and not d.get("is_merged_into"):
                if d not in self.devices:
                    self.devices.append(d)
        self._init_fields()
        self._build_inputs()
        self._compute_content_height()

    def _confirm_lacp(self):
        if len(self.selected_ports) < 2:
            print("LACP: выбери минимум 2 порта")
            return
        eids = {eid for eid, _ in self.selected_ports}
        if len(eids) > 1:
            print("LACP: все порты должны принадлежать одному устройству")
            return
        eid = eids.pop()
        equip = self._find_equip(eid)
        if equip is None:
            return
        ports = sorted(pi for e, pi in self.selected_ports if port_in_lacp(equip, pi) is None)
        if len(ports) < 2:
            print("LACP: нужно минимум 2 свободных от LACP порта")
            return
        new_id = max([g["id"] for g in equip["lacp_groups"]], default=0) + 1
        grp = {"id": new_id, "name": f"LACP-{new_id}", "ports": ports, "speed": 1000, "label": "", "mode": "trunk", "vlan_string": "", "admin_state": "up"}
        equip["lacp_groups"].append(grp)
        _notify_speed_changed(self.game)
        print(f"LACP {grp['name']}: порты {[p + 1 for p in ports]} у #{eid}")
        self._build_inputs()
        self._compute_content_height()
        self._exit_mode()

    def _toggle_admin_state(self, obj):
        st = obj.get("admin_state", "up")
        obj["admin_state"] = "up" if st == "shut" else "shut"

    def _toggle_mode(self, obj):
        obj["mode"] = "trunk" if obj.get("mode", "access") == "access" else "access"

    def _open_vlan_popup(self, kind, equip, ref):
        sw, sh = _screen_size()
        if kind == "port":
            port = equip["ports"][ref]
            text = port.get("vlan_string", "")
            mode = port.get("mode", "access")
            def cb(new_text):
                port["vlan_string"] = new_text
                self.popup = None
        else:
            grp = ref
            text = grp.get("vlan_string", "")
            mode = grp.get("mode", "trunk")
            def cb(new_text):
                grp["vlan_string"] = new_text
                self.popup = None
        self.popup = VlanPopupWindow(sw, sh, text, mode, cb)
        if self.manager is not None:
            self.popup.manager = self.manager

    # ---- события ----
    def handle_event(self, event):
        if self.popup is not None:
            handled = self.popup.handle_event(event)
            if self.popup is not None and self.popup.is_closed:
                self.popup = None
            return handled or True

        if event.type == pygame.KEYDOWN:
            for ti in self.inputs.values():
                if ti.active:
                    return ti.handle_event(event, self._cfg_font)
            return super().handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._sync_positions()

            # 1. Футер
            if self._btn_save.collidepoint(event.pos):
                self._save(); return True
            if self._btn_lacp.collidepoint(event.pos):
                if self.mode == self.MODE_LACP: self._confirm_lacp()
                else: self._enter_mode(self.MODE_LACP)
                return True
            if self._btn_commut.collidepoint(event.pos):
                if self.mode == self.MODE_COMMUT:
                    if len(self.selected_devices) >= 2:
                        self._confirm_commut()
                    else:
                        self._exit_mode()
                else: 
                    self._enter_mode(self.MODE_COMMUT)
                return True

            # 2. Контент
            if self.content_rect().collidepoint(event.pos):
                
                # 2.1 Заголовки секций (Commut или выбор активной)
                for rect, equip in self._section_hits:
                    if rect.collidepoint(event.pos):
                        if self.mode == self.MODE_COMMUT:
                            if len(equip.get("boards", [])) > 1:
                                # Если уже шасси -> разъединяем
                                self.active_section_eid = equip["id"]
                                self._do_unmerge(equip)
                            else:
                                # Иначе -> добавляем/убираем из выбора
                                if equip["id"] in self.selected_devices:
                                    self.selected_devices.discard(equip["id"])
                                else:
                                    self.selected_devices.add(equip["id"])
                        else: 
                            self.active_section_eid = equip["id"]
                        return True

                # 2.2 Остальные элементы (Link, Speed, Mode, VLAN, Desc)
                for rect, equip, pi, kind, ref in self._link_hits:
                    if rect.collidepoint(event.pos):
                        if self.mode == self.MODE_LACP and kind == "port":
                            key = (equip["id"], pi)
                            if key in self.selected_ports: self.selected_ports.remove(key)
                            else: self.selected_ports.append(key)
                            return True
                        if kind == "port": self._toggle_admin_state(equip["ports"][pi])
                        else: self._toggle_admin_state(ref)
                        return True

                for rect, kind, equip, ref in self._speed_hits:
                    if rect.collidepoint(event.pos):
                        if kind == "port":
                            if port_in_lacp(equip, ref) is not None: return True
                            if _find_cable_100(self.game, equip["id"], ref): return True
                            toggle_port_speed(self.game, equip, ref)
                        else: toggle_lacp_speed(ref, self.game)
                        return True

                for rect, kind, equip, ref in self._mode_hits:
                    if rect.collidepoint(event.pos):
                        if kind == "port":
                            if port_in_lacp(equip, ref) is not None: return True
                            self._toggle_mode(equip["ports"][ref])
                        else: self._toggle_mode(ref)
                        return True

                for rect, kind, equip, ref in self._vlan_hits:
                    if rect.collidepoint(event.pos):
                        if kind == "port":
                            if port_in_lacp(equip, ref) is not None: return True
                            self._open_vlan_popup("port", equip, ref)
                        else: self._open_vlan_popup("lacp", equip, ref)
                        return True

                for key, rect in self._desc_rects.items():
                    kind, eid = key[0], key[1]
                    equip = self._find_equip(eid)
                    if equip is None: continue
                    if kind == "port" and port_in_lacp(equip, key[2]) is not None: continue
                    ti = self.inputs.get(key)
                    if ti is not None and ti.handle_event(event, self._cfg_font): return True

                for ti in self.inputs.values(): ti.active = False
                return True

        return super().handle_event(event)

    def _save(self):
        for key, ti in self.inputs.items():
            kind, eid = key[0], key[1]
            equip = self._find_equip(eid)
            if equip is None: continue
            if kind == "port":
                pi = key[2]
                if port_in_lacp(equip, pi) is None:
                    equip["ports"][pi]["label"] = ti.text
            else:
                gid = key[2]
                for grp in equip.get("lacp_groups", []):
                    if grp["id"] == gid:
                        grp["label"] = ti.text
                        break
        print("Настройки применены")

    # ---- отрисовка ----
    def _draw_link_pill(self, screen, rect, state):
        color = COLOR_LINK_UP if state == "up" else COLOR_LINK_DOWN
        text = state
        pygame.draw.rect(screen, color, rect, border_radius=18)
        pygame.draw.rect(screen, COLOR_LINK_EDGE, rect, 1, border_radius=18)
        surf = self._tiny.render(text, True, (255, 255, 255))
        screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))

    def _draw_mini_button(self, screen, rect, text, disabled=False, selected=False):
        if disabled:
            pygame.draw.rect(screen, COLOR_BTN_DIS_BG, rect, border_radius=5)
            pygame.draw.rect(screen, COLOR_BTN_DIS_EDGE, rect, 1, border_radius=5)
            surf = self._tiny.render(text, True, (140, 140, 150))
            screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))
            return
        mouse = pygame.mouse.get_pos()
        state = "active" if selected else ("hover" if rect.collidepoint(mouse) else "normal")
        draw_fancy_button(screen, self._tiny, rect, text, state=state, radius=5)

    def _render_content(self, surface, font, small_font):
        y = 10
        for equip in self.devices:
            ry = y - self.scroll_y
            hdr_rect = pygame.Rect(0, ry, surface.get_width(), UCW_SECTION_HDR_H)
            
            # Подсветка заголовка
            if self.mode == self.MODE_COMMUT and equip["id"] in self.selected_devices:
                pygame.draw.rect(surface, COLOR_SEL_SECTION, hdr_rect)
                pygame.draw.rect(surface, (100, 200, 255), hdr_rect, 2) # голубой контур
            elif equip["id"] == self.active_section_eid:
                pygame.draw.rect(surface, (50, 70, 100), hdr_rect)

            title = equip_type_label(equip)
            boards_n = len(equip.get("boards", []))
            
            if boards_n > 1:
                label_text = f"{title} #{equip['id']}  [ШАССИ, плат: {boards_n}]"
                if self.mode == self.MODE_COMMUT:
                    label_text += "  (LKM -> разделить)"
            else:
                label_text = f"{title} #{equip['id']}"
                
            hdr = self._header_font.render(label_text, True, COLOR_TITLE)
            surface.blit(hdr, (UCW_X_PORT, ry + 10))
            y += self.row_h

            for i, port in enumerate(equip["ports"]):
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h
                    continue
                pname = port_name(self.game, equip, i) if self.game else f"{i + 1}"
                in_lacp = port_in_lacp(equip, i) is not None
                col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
                if self.mode == self.MODE_LACP and (equip["id"], i) in self.selected_ports:
                    pygame.draw.rect(surface, (40, 70, 120), pygame.Rect(0, ry, surface.get_width(), self.row_h))
                num = self._cfg_font.render(pname, True, col)
                surface.blit(num, (UCW_X_PORT, ry + 15))
                y += self.row_h

            for grp in equip["lacp_groups"]:
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h
                    continue
                name = self._cfg_font.render(grp["name"], True, COLOR_LACP_ROW)
                surface.blit(name, (UCW_X_PORT, ry + 10))
                members = ",".join(str(p + 1) for p in grp["ports"])
                meta = self._tiny.render(f"порты: {members}", True, COLOR_LACP_ROW)
                surface.blit(meta, (UCW_X_PORT, ry + 28))
                y += self.row_h
            y += UCW_SECTION_GAP

    def _draw_mode_banner(self, screen):
        if self.mode == self.MODE_NORMAL: return
        pygame.draw.rect(screen, COLOR_MODE_BANNER, pygame.Rect(self.x, self.y + HEADER_H - 2, self.width, 4))
        if self.mode == self.MODE_COMMUT:
            txt = "Режим COMMUT: LKM по заголовку — выбрать/разъединить. Выбери 2+ и нажми Commut для слияния."
        else:
            txt = "Режим LACP: выбирай овалы Link у физпортов"
        surf = self._tiny.render(txt, True, (200, 220, 255))
        screen.blit(surf, (self.x + 10, self.y + HEADER_H + 2))

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_mode_banner(screen)
        self._draw_content(screen, font, small_font)
        self._sync_positions()
        cr = self.content_rect()
        old_clip = screen.get_clip()
        screen.set_clip(cr)

        for rect, equip, pi, kind, ref in self._link_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                state = _port_link_state(equip["ports"][pi]) if kind == "port" else _lacp_link_state(equip, ref)
                self._draw_link_pill(screen, rect, state)

        for key, rect in self._desc_rects.items():
            kind, eid = key[0], key[1]
            equip = self._find_equip(eid)
            if equip is None: continue
            if kind == "port" and port_in_lacp(equip, key[2]) is not None:
                self._draw_mini_button(screen, rect, "—", disabled=True)
                continue
            if cr.y - 30 <= rect.y <= cr.bottom:
                ti = self.inputs.get(key)
                if ti: ti.draw(screen, self._cfg_font)

        for rect, kind, equip, ref in self._speed_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "LACP", disabled=True)
                        continue
                    self._draw_mini_button(screen, rect, speed_label(equip["ports"][ref].get("speed", 1000)))
                else:
                    self._draw_mini_button(screen, rect, speed_label(ref.get("speed", 1000)))

        for rect, kind, equip, ref in self._mode_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "LACP", disabled=True)
                        continue
                    self._draw_mini_button(screen, rect, equip["ports"][ref].get("mode", "access"))
                else:
                    self._draw_mini_button(screen, rect, ref.get("mode", "trunk"))

        for rect, kind, equip, ref in self._vlan_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "—", disabled=True)
                        continue
                    text = _vlan_preview(equip["ports"][ref].get("vlan_string", ""))
                else:
                    text = _vlan_preview(ref.get("vlan_string", ""))
                self._draw_mini_button(screen, rect, text)

        screen.set_clip(old_clip)

        footer_bg = pygame.Rect(self.x, self.y + self.height - UCW_FOOTER_H, self.width, UCW_FOOTER_H)
        pygame.draw.rect(screen, (40, 42, 50), footer_bg)
        pygame.draw.line(screen, (90, 90, 100), (footer_bg.x, footer_bg.y), (footer_bg.right, footer_bg.y), 1)

        self._draw_mini_button(screen, self._btn_lacp, "LACP", selected=(self.mode == self.MODE_LACP))
        self._draw_mini_button(screen, self._btn_commut, "Commut", selected=(self.mode == self.MODE_COMMUT))
        self._draw_mini_button(screen, self._btn_save, "Save")

        if self.popup is not None:
            self.popup.draw(screen, font, small_font)
# ---- события ----
    def _toggle_admin_state(self, obj):
        st = obj.get("admin_state", "up")
        obj["admin_state"] = "up" if st == "shut" else "shut"

    def _toggle_mode(self, obj):
        obj["mode"] = "trunk" if obj.get("mode", "access") == "access" else "access"

    def _open_vlan_popup(self, kind, equip, ref):
        """kind: 'port' -> ref=port_index; 'lacp' -> ref=grp"""
        sw, sh = _screen_size()
        if kind == "port":
            port = equip["ports"][ref]
            text = port.get("vlan_string", "")
            mode = port.get("mode", "access")

            def cb(new_text):
                port["vlan_string"] = new_text
                self.popup = None
        else:
            grp = ref
            text = grp.get("vlan_string", "")
            mode = grp.get("mode", "trunk")

            def cb(new_text):
                grp["vlan_string"] = new_text
                self.popup = None

        self.popup = VlanPopupWindow(sw, sh, text, mode, cb)
        self.popup.manager = self.manager

        def handle_event(self, event):
            # Popup (VLAN / GroupSettings) перехватывает всё
            if self.popup is not None:
                handled = self.popup.handle_event(event)
                if self.popup is not None and self.popup.is_closed:
                    self.popup = None
                return handled or True

            # KEYDOWN -> активный TextInput
            if event.type == pygame.KEYDOWN:
                for ti in self.inputs.values():
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                return super().handle_event(event)

            # Клики: СНАЧАЛА футер и контент, ПОТОМ базовое окно
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 1. Футер
                if self._btn_save.collidepoint(event.pos):
                    self._save(); return True
                if self._btn_lacp.collidepoint(event.pos):
                    if self.mode == self.MODE_LACP:
                        self._confirm_lacp()
                    else:
                        self._enter_mode(self.MODE_LACP)
                    return True
                if self._btn_commut.collidepoint(event.pos):
                    if self.mode == self.MODE_COMMUT:
                        self._confirm_commut()
                    else:
                        self._enter_mode(self.MODE_COMMUT)
                    return True
                 
                

                # 2. Контент (ЗАГОЛОВКИ, LINK, SPEED, MODE, VLAN, DESC)
                self._sync_positions()
                if self.content_rect().collidepoint(event.pos):
                    # Заголовки секций
                    for rect, equip in self._section_hits:
                        if rect.collidepoint(event.pos):
                            if self.mode == self.MODE_COMMUT:
                                if equip["id"] in self.selected_devices:
                                    self.selected_devices.discard(equip["id"])
                                else:
                                    self.selected_devices.add(equip["id"])
                            else:
                                self.active_section_eid = equip["id"]
                            return True
                    # Link-овалы (up/down/shut / выбор в LACP)
                    for rect, equip, pi, kind, ref in self._link_hits:
                        if rect.collidepoint(event.pos):
                            if self.mode == self.MODE_LACP and kind == "port":
                                key = (equip["id"], pi)
                                if key in self.selected_ports:
                                    self.selected_ports.remove(key)
                                else:
                                    self.selected_ports.append(key)
                                return True
                            if kind == "port":
                                self._toggle_admin_state(equip["ports"][pi])
                            else:
                                self._toggle_admin_state(ref)
                            return True
                    # Скорость
                    for rect, kind, equip, ref in self._speed_hits:
                        if rect.collidepoint(event.pos):
                            if kind == "port":
                                if port_in_lacp(equip, ref) is not None:
                                    return True
                                if _find_cable_100(self.game, equip["id"], ref):
                                    print("Кабель 100Мб ограничивает скорость")
                                    return True
                                toggle_port_speed(self.game, equip, ref)
                            else:
                                toggle_lacp_speed(ref, self.game)
                            return True
                    # Режим access/trunk
                    for rect, kind, equip, ref in self._mode_hits:
                        if rect.collidepoint(event.pos):
                            if kind == "port":
                                if port_in_lacp(equip, ref) is not None:
                                    return True
                                self._toggle_mode(equip["ports"][ref])
                            else:
                                self._toggle_mode(ref)
                            return True
                    # VLAN
                    for rect, kind, equip, ref in self._vlan_hits:
                        if rect.collidepoint(event.pos):
                            if kind == "port":
                                if port_in_lacp(equip, ref) is not None:
                                    return True
                                self._open_vlan_popup("port", equip, ref)
                            else:
                                self._open_vlan_popup("lacp", equip, ref)
                            return True
                    # Поля подписи
                    for key, rect in self._desc_rects.items():
                        kind, eid = key[0], key[1]
                        equip = self._find_equip(eid)
                        if equip is None:
                            continue
                        if kind == "port" and port_in_lacp(equip, key[2]) is not None:
                            continue
                        ti = self.inputs.get(key)
                        if ti is not None and ti.handle_event(event, self._cfg_font):
                            return True
                    # Клик по пустому месту — снять фокус
                    for ti in self.inputs.values():
                        ti.active = False
                    return True

            # 3. Всё остальное (drag, scroll, resize, back, close) — базовому классу
            return super().handle_event(event)

    def _save(self):
        for key, ti in self.inputs.items():
            kind, eid = key[0], key[1]
            equip = self._find_equip(eid)
            if equip is None:
                continue
            if kind == "port":
                pi = key[2]
                if port_in_lacp(equip, pi) is None:
                    equip["ports"][pi]["label"] = ti.text
            else:
                gid = key[2]
                for grp in equip.get("lacp_groups", []):
                    if grp["id"] == gid:
                        grp["label"] = ti.text
                        break
        print("Настройки применены")

    # ---- отрисовка ----
    def _draw_link_pill(self, screen, rect, state):
        if state == "up":
            color = COLOR_LINK_UP
            text = "up"
        elif state == "shut":
            color = COLOR_LINK_DOWN
            text = "shut"
        else:
            color = COLOR_LINK_DOWN
            text = "down"
        pygame.draw.rect(screen, color, rect, border_radius=18)
        pygame.draw.rect(screen, COLOR_LINK_EDGE, rect, 1, border_radius=18)
        surf = self._tiny.render(text, True, (255, 255, 255))
        screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                           rect.centery - surf.get_height() // 2))

    def _draw_mini_button(self, screen, rect, text, disabled=False, selected=False):
        if disabled:
            pygame.draw.rect(screen, COLOR_BTN_DIS_BG, rect, border_radius=5)
            pygame.draw.rect(screen, COLOR_BTN_DIS_EDGE, rect, 1, border_radius=5)
            surf = self._tiny.render(text, True, (140, 140, 150))
            screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                               rect.centery - surf.get_height() // 2))
            return
        mouse = pygame.mouse.get_pos()
        state = "active" if selected else (
            "hover" if rect.collidepoint(mouse) else "normal")
        draw_fancy_button(screen, self._tiny, rect, text, state=state, radius=5)

    def _render_content(self, surface, font, small_font):
        """Статика: заголовки, номера портов, подписи LACP, подсветка выбранных."""
        y = 10
        for equip in self.devices:
            # Фон заголовка секции
            ry = y - self.scroll_y
            hdr_rect = pygame.Rect(0, ry, surface.get_width(), UCW_SECTION_HDR_H)
            if (self.mode == self.MODE_COMMUT and
                    equip["id"] in self.selected_devices):
                pygame.draw.rect(surface, COLOR_SEL_SECTION, hdr_rect)
            elif equip["id"] == self.active_section_eid:
                pygame.draw.rect(surface, (50, 70, 100), hdr_rect)
            # Заголовок
            title = equip_type_label(equip)
            boards_n = len(equip.get("boards", []))
            label = (f"{title} #{equip['id']}"
                     + (f"  [шасси, плат: {boards_n}]" if boards_n > 1 else ""))
            hdr = self._header_font.render(label, True, COLOR_TITLE)
            surface.blit(hdr, (UCW_X_PORT, ry + 10))
            y += self.row_h
            # Порты
            for i, port in enumerate(equip["ports"]):
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h
                    continue
                pname = (port_name(self.game, equip, i)
                         if self.game else f"{i + 1}")
                in_lacp = port_in_lacp(equip, i) is not None
                col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
                # Подсветка выбранного порта в режиме LACP
                if self.mode == self.MODE_LACP:
                    key = (equip["id"], i)
                    if key in self.selected_ports:
                        row_bg = pygame.Rect(0, ry, surface.get_width(), self.row_h)
                        pygame.draw.rect(surface, (40, 70, 120), row_bg)
                num = self._cfg_font.render(pname, True, col)
                surface.blit(num, (UCW_X_PORT, ry + 15))
                y += self.row_h
            # LACP-строки
            for grp in equip["lacp_groups"]:
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h
                    continue
                name = self._cfg_font.render(grp["name"], True, COLOR_LACP_ROW)
                surface.blit(name, (UCW_X_PORT, ry + 10))
                members = ",".join(str(p + 1) for p in grp["ports"])
                meta = self._tiny.render(f"порты: {members}", True, COLOR_LACP_ROW)
                surface.blit(meta, (UCW_X_PORT, ry + 28))
                y += self.row_h
            y += UCW_SECTION_GAP

    def _draw_mode_banner(self, screen):
        if self.mode == self.MODE_NORMAL:
            return
        bar = pygame.Rect(self.x, self.y + HEADER_H - 2, self.width, 4)
        pygame.draw.rect(screen, COLOR_MODE_BANNER, bar)
        txt = ("Режим COMMUT: выбирай заголовки устройств"
               if self.mode == self.MODE_COMMUT else
               "Режим LACP: выбирай овалы Link у физпортов")
        surf = self._tiny.render(txt, True, (200, 220, 255))
        screen.blit(surf, (self.x + 10, self.y + HEADER_H + 2))

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_mode_banner(screen)
        self._draw_content(screen, font, small_font)
        self._sync_positions()

        cr = self.content_rect()
        old_clip = screen.get_clip()
        screen.set_clip(cr)

        # Link pills (порты и LACP)
        for rect, equip, pi, kind, ref in self._link_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            if kind == "port":
                state = _port_link_state(equip["ports"][pi])
            else:
                state = _lacp_link_state(equip, ref)
            self._draw_link_pill(screen, rect, state)

        # Desc TextInput'ы
        for key, rect in self._desc_rects.items():
            kind = key[0]
            eid = key[1]
            equip = self._find_equip(eid)
            if equip is None:
                continue
            ti = self.inputs.get(key)
            if ti is None:
                continue
            if kind == "port":
                pi = key[2]
                if port_in_lacp(equip, pi) is not None:
                    self._draw_mini_button(screen, rect, "—", disabled=True)
                    continue
            if cr.y - 30 <= rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)

        # Speed
        for rect, kind, equip, ref in self._speed_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            if kind == "port":
                if port_in_lacp(equip, ref) is not None:
                    self._draw_mini_button(screen, rect, "LACP", disabled=True)
                    continue
                spd = equip["ports"][ref].get("speed", 1000)
            else:
                spd = ref.get("speed", 1000)
            self._draw_mini_button(screen, rect, speed_label(spd))

        # Mode
        for rect, kind, equip, ref in self._mode_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            if kind == "port":
                if port_in_lacp(equip, ref) is not None:
                    self._draw_mini_button(screen, rect, "LACP", disabled=True)
                    continue
                md = equip["ports"][ref].get("mode", "access")
            else:
                md = ref.get("mode", "trunk")
            self._draw_mini_button(screen, rect, md)

        # VLAN
        for rect, kind, equip, ref in self._vlan_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            if kind == "port":
                if port_in_lacp(equip, ref) is not None:
                    self._draw_mini_button(screen, rect, "—", disabled=True)
                    continue
                text = _vlan_preview(equip["ports"][ref].get("vlan_string", ""))
            else:
                text = _vlan_preview(ref.get("vlan_string", ""))
            self._draw_mini_button(screen, rect, text)

        screen.set_clip(old_clip)

        # Футер
        footer_bg = pygame.Rect(self.x, self.y + self.height - UCW_FOOTER_H,
                                self.width, UCW_FOOTER_H)
        pygame.draw.rect(screen, (40, 42, 50), footer_bg)
        pygame.draw.line(screen, (90, 90, 100),
                         (footer_bg.x, footer_bg.y),
                         (footer_bg.right, footer_bg.y), 1)

        self._draw_mini_button(screen, self._btn_lacp, "LACP",
                               selected=(self.mode == self.MODE_LACP))
        self._draw_mini_button(screen, self._btn_commut, "Commut",
                               selected=(self.mode == self.MODE_COMMUT))
        
        self._draw_mini_button(screen, self._btn_save, "Save")

        if self.popup is not None:
            self.popup.draw(screen, font, small_font)


