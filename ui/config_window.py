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
)
from ui.lacp import LACPInputWindow
from ui.chassis import port_name, board_label


# ============================================================================
# СТАРЫЕ окна (SwitchConfigWindow/RouterConfigWindow) - для клика по карте.
# ============================================================================
class SwitchConfigWindow(Window):
    def __init__(self, equip, screen_w, screen_h, game=None):
        w, h = 540, 560
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equip = equip
        self.game = game
        self.equip.setdefault("lacp_groups", [])
        self.chassis = game.chassis_of(equip["id"]) if game else None
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
        if self.chassis is not None:
            return f"Config шасси: {self.chassis.get('name', 'Chassis')}"
        return f"Config: {equip_type_label(self.equip)} #{self.equip['id']}"

    def content_rect(self):
        top = HEADER_H + 22 + (34 if self.chassis is not None else 0)
        return pygame.Rect(self.x, self.y + top,
                           self.width, self.height - top - FOOTER_H)

    def _boards(self):
        if self.chassis is not None:
            return self.game.equipment_in_chassis(self.chassis["id"])
        return [self.equip]

    def _build_inputs(self):
        self.inputs = []
        self.lacp_inputs = []
        self.board_inputs = {}
        if self.chassis is not None:
            self.name_input = TextInput((0, 0, 220, 26),
                                        initial_text=self.chassis.get("name", ""),
                                        max_length=20)
        else:
            self.name_input = None
        for bidx, equip in enumerate(self._boards(), 1):
            if self.chassis is not None:
                lbl = board_label(self.chassis, equip["id"], bidx)
                self.board_inputs[equip["id"]] = TextInput(
                    (0, 0, 200, 26), initial_text=lbl, max_length=18)
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
            if self.chassis is not None:
                rows.append(("board", equip, None))
            for i, _ in enumerate(equip["ports"]):
                rows.append(("port", equip, i))
            for grp in equip.get("lacp_groups", []):
                rows.append(("lacp", equip, grp))
        rows.append(("actions", None, None))
        return rows

    def _compute_content_height(self):
        n = len(self._rows_layout())
        self.content_height = 10 + n * self.row_h + 20

    def _row_y(self, row_index):
        return 10 + row_index * self.row_h

    def is_text_input_active(self):
        if self.lacp_input_window is not None:
            return True
        if self.name_input is not None and self.name_input.active:
            return True
        if any(ti.active for ti in self.board_inputs.values()):
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
        for row_idx, row in enumerate(rows):
            ry = cr.y + self._row_y(row_idx) - self.scroll_y
            kind = row[0]
            if kind == "board":
                equip = row[1]
                ti = self.board_inputs.get(equip["id"])
                if ti is not None:
                    ti.set_rect((cr.x + COL_STATUS, ry + 6, 200, 26))
            elif kind == "port":
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
        for ti in self.board_inputs.values():
            yield ti
        if self.name_input is not None:
            yield self.name_input
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
                if self.game is not None and self.game.ui_manager is not None:
                    self.game.ui_manager.open_chassis_merge(self.equip)
                return True
            if self.chassis is not None and self._group_btn.collidepoint(event.pos):
                if self.game is not None and self.game.ui_manager is not None:
                    self.game.ui_manager.open_chassis_settings(self.chassis)
                return True
            if self.name_input is not None:
                if self.name_input.handle_event(event, self._cfg_font):
                    return True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._sync_positions()

            if event.type == pygame.KEYDOWN:
                if self.name_input is not None and self.name_input.active:
                    return self.name_input.handle_event(event, self._cfg_font)
                for ti in self.board_inputs.values():
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                for _, _, ti in self.inputs:
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                for _, _, ti in self.lacp_inputs:
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                return False

            if event.button == 1:
                if self.close_rect().collidepoint(event.pos):
                    self.close()
                    return True
                if self.titlebar_rect().collidepoint(event.pos):
                    self.dragging = True
                    self.drag_offset_x = event.pos[0] - self.x
                    self.drag_offset_y = event.pos[1] - self.y
                    return True
                if self._add_lacp_btn.collidepoint(event.pos):
                    self._open_lacp_input()
                    return True

                cr = self.content_rect()
                in_content = cr.collidepoint(event.pos)
                clicked_input = False
                if in_content:
                    for ti in self.board_inputs.values():
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
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

                if self.contains(event.pos):
                    for ti in self._all_inputs():
                        ti.active = False
                    return True
                self.close()
                return True

        return super().handle_event(event)

    def _free_for_lacp(self, equip, port_index):
        return port_in_lacp(equip, port_index) is None

    def _open_lacp_input(self):
        sw, sh = _screen_size()
        target = self.equip

        def on_submit(selected_ports):
            ports = sorted(p for p in selected_ports
                           if self._free_for_lacp(target, p))
            if len(ports) < 2:
                print("LACP: нужно выбрать минимум 2 свободных порта")
                return
            new_id = max([g["id"] for g in target["lacp_groups"]], default=0) + 1
            grp = {"id": new_id, "name": f"LACP-{new_id}",
                   "ports": ports, "speed": 1000, "label": ""}
            target["lacp_groups"].append(grp)
            self._persist_labels()
            self._build_inputs()
            self._compute_content_height()
            _notify_speed_changed(self.game)
            print(f"Создана группа {grp['name']} из портов "
                  f"{[p + 1 for p in ports]} (плата #{target['id']})")

        self.lacp_input_window = LACPInputWindow(
            on_submit, sw, sh, target, lambda p: self._free_for_lacp(target, p))

    def _persist_labels(self):
        for equip, i, ti in self.inputs:
            if port_in_lacp(equip, i) is None:
                equip["ports"][i]["label"] = ti.text
        for _, grp, ti in self.lacp_inputs:
            grp["label"] = ti.text
        if self.chassis is not None:
            if self.name_input is not None and self.name_input.text:
                self.chassis["name"] = self.name_input.text
            self.chassis.setdefault("board_labels", {})
            for eid, ti in self.board_inputs.items():
                if ti.text:
                    self.chassis["board_labels"][eid] = ti.text

    def _save_and_close(self):
        self._persist_labels()
        tgt = self.chassis.get("name") if self.chassis else f"#{self.equip['id']}"
        print(f"Настройки сохранены: {tgt}")
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

    def _draw_chassis_header(self, screen, small_font):
        if self.chassis is None:
            return
        y = self.y + HEADER_H + 6
        lbl = small_font.render("Шасси:", True, COLOR_TEXT_DIM)
        screen.blit(lbl, (self.x + 14, y + 4))
        if self.name_input is not None:
            self.name_input.set_rect((self.x + 70, y, 220, 26))
            self.name_input.draw(screen, self._cfg_font)
        boards_txt = small_font.render(
            f"плат: {len(self._boards())}", True, COLOR_TEXT_DIM)
        screen.blit(boards_txt, (self.x + 310, y + 4))

    def _render_content(self, surface, font, small_font):
        tiny = pygame.font.SysFont("arial,dejavusans", 12)
        rows = self._rows_layout()
        for row_idx, row in enumerate(rows):
            ry = self._row_y(row_idx) - self.scroll_y
            if ry + self.row_h < 0 or ry > surface.get_height():
                continue
            kind = row[0]
            if kind == "board":
                equip = row[1]
                bidx = self._boards().index(equip) + 1
                hdr = font.render(f"━ Плата {bidx}  (#{equip['id']}, "
                                  f"{equip_type_label(equip)})",
                                  True, COLOR_TITLE)
                surface.blit(hdr, (COL_NUM, ry + 6))
            elif kind == "port":
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
        self._draw_chassis_header(screen, small_font)
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
        for eid, ti in self.board_inputs.items():
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
        self._merge_btn = pygame.Rect(self.x + 12,
                                      self.y + self.height - FOOTER_H + 6, 130, 30)
        draw_button_screen(screen, small_font, self._save_btn, "💾 Сохранить")
        draw_button_screen(screen, small_font, self._merge_btn, "⛓ Коммутация")
        if self.chassis is not None:
            self._group_btn = pygame.Rect(self.x + self.width - 162,
                                          self.y + self.height - FOOTER_H + 6,
                                          150, 30)
            draw_button_screen(screen, small_font, self._group_btn,
                               "⚙ Настройки группы")
        else:
            self._group_btn = pygame.Rect(0, 0, 0, 0)

        if self.lacp_input_window is not None:
            self.lacp_input_window.draw(screen, font, small_font)


class RouterConfigWindow(SwitchConfigWindow):
    def __init__(self, equip, screen_w, screen_h, game=None):
        super().__init__(equip, screen_w, screen_h, game=game)
        if self.chassis is not None:
            self.width, self.height = 540, 520
        else:
            self.width, self.height = 540, 400
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self._compute_content_height()


# ============================================================================
# НОВОЕ: UniversalConfigWindow — одно окно на все устройства дома.
# ============================================================================
UCW_ROW_H = 45
UCW_X_PORT = 10
UCW_X_LINK = 50
UCW_LINK_W = 60
UCW_LINK_H = 25
UCW_X_DESC = 120
UCW_DESC_W = 130
UCW_X_SPEED = 260
UCW_SPEED_W = 60
UCW_X_MODE = 330
UCW_MODE_W = 80
UCW_X_VLAN = 420
UCW_VLAN_W = 120
UCW_HDR_H = 36
UCW_SECTION_GAP = 10

COLOR_LINK_UP = (60, 190, 90)
COLOR_LINK_DOWN = (210, 70, 70)
COLOR_LINK_EDGE = (230, 230, 230)
COLOR_BTN_DIS_BG = (60, 60, 66)
COLOR_BTN_DIS_EDGE = (95, 95, 105)


def _ensure_port_fields(port):
    port.setdefault("admin_state", "up")
    port.setdefault("vlan_string", "")
    port.setdefault("mode", "access")


def _link_state(port):
    """Возвращает 'shut' | 'down' | 'up'."""
    if port.get("admin_state", "up") == "shut":
        return "shut"
    return "down" if port.get("free", True) else "up"


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
    """Одно окно на все устройства дома. Шасси/одиночки — списком."""

    def __init__(self, devices, screen_w, screen_h, game=None):
        w, h = 720, 600
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Конфигурация оборудования")
        self.devices = devices
        self.game = game
        self.row_h = UCW_ROW_H
        self._cfg_font = pygame.font.SysFont("arial,dejavusans", 14)
        self._header_font = pygame.font.SysFont("arial,dejavusans", 13)
        self._tiny = pygame.font.SysFont("arial,dejavusans", 11)

        self.sections = self._build_sections(devices)
        # TextInput'ы (ключ (eq_id, port_index, "desc"/"vlan")):
        self.inputs = {}
        # LACP label-инпуты: (eq_id, grp_id)
        self.lacp_inputs = {}
        # Имя шасси: {chassis_id: TextInput}
        self.name_inputs = {}

        self._init_fields()
        self._build_inputs()

        # Хит-боксы (пересчитываются в _sync_positions):
        self._link_hits = []        # (rect, equip, port_index)
        self._speed_hits = []       # (rect, kind, equip, ref)   kind: "port"|"lacp"
        self._mode_hits = []        # (rect, equip, port_index)
        self._add_lacp_hits = []    # (rect, equip)
        self._merge_hits = []       # (rect, equip)
        self._group_hits = []       # (rect, chassis)

        # Футер:
        self._save_btn = pygame.Rect(0, 0, 0, 0)

        self._compute_content_height()

    # ----- подготовка -----
    def _build_sections(self, devices):
        """Группирует devices по шасси.
        Секция: {"chassis": grp|None, "title": str, "boards": [equip,...]}"""
        sections = []
        seen_chassis = set()
        for d in devices:
            grp = self.game.chassis_of(d["id"]) if self.game else None
            if grp is not None:
                if grp["id"] in seen_chassis:
                    continue
                seen_chassis.add(grp["id"])
                boards = (self.game.equipment_in_chassis(grp["id"])
                          if self.game else [d])
                title = f"Шасси: {grp.get('name', 'Chassis')}"
                sections.append({"chassis": grp, "title": title, "boards": boards})
            else:
                title = f"{equip_type_label(d)} #{d['id']}"
                sections.append({"chassis": None, "title": title, "boards": [d]})
        return sections

    def _init_fields(self):
        """Гарантирует наличие admin_state, vlan_string, mode у портов."""
        for sec in self.sections:
            for equip in sec["boards"]:
                equip.setdefault("lacp_groups", [])
                for port in equip["ports"]:
                    _ensure_port_fields(port)

    def _build_inputs(self):
        self.inputs = {}
        self.lacp_inputs = {}
        self.name_inputs = {}
        for sec in self.sections:
            if sec["chassis"] is not None:
                grp = sec["chassis"]
                self.name_inputs[grp["id"]] = TextInput(
                    (0, 0, 240, 26),
                    initial_text=grp.get("name", ""), max_length=20)
            for equip in sec["boards"]:
                for i, port in enumerate(equip["ports"]):
                    self.inputs[(equip["id"], i, "desc")] = TextInput(
                        (0, 0, UCW_DESC_W, 26),
                        initial_text=port.get("label", ""), max_length=15)
                    self.inputs[(equip["id"], i, "vlan")] = TextInput(
                        (0, 0, UCW_VLAN_W, 26),
                        initial_text=port.get("vlan_string", ""), max_length=32)
                for grp in equip.get("lacp_groups", []):
                    self.lacp_inputs[(equip["id"], grp["id"])] = TextInput(
                        (0, 0, UCW_DESC_W, 26),
                        initial_text=grp.get("label", ""), max_length=15)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _section_rows(self, sec):
        """Кол-во визуальных строк в секции: заголовок + имя-шасси + порты + LACP + футер секции."""
        n = 1  # заголовок
        if sec["chassis"] is not None:
            n += 1  # строка с TextInput имени шасси
        for equip in sec["boards"]:
            n += len(equip["ports"])
            n += len(equip.get("lacp_groups", []))
        n += 1  # кнопки секции (+ADD_LACP, Merge, Group settings)
        return n

    def _compute_content_height(self):
        total = 10
        for sec in self.sections:
            total += self._section_rows(sec) * self.row_h + UCW_SECTION_GAP
        self.content_height = total + 20

    # ----- хит-боксы и позиции -----
    def _sync_positions(self):
        cr = self.content_rect()
        self._link_hits = []
        self._speed_hits = []
        self._mode_hits = []
        self._add_lacp_hits = []
        self._merge_hits = []
        self._group_hits = []

        y = 10
        for sec in self.sections:
            # 1) Заголовок секции
            y += self.row_h
            # 2) Имя шасси (если шасси)
            if sec["chassis"] is not None:
                grp = sec["chassis"]
                ti = self.name_inputs[grp["id"]]
                ry = cr.y + y - self.scroll_y
                ti.set_rect((cr.x + UCW_X_PORT + 70, ry + 10, 240, 26))
                y += self.row_h
            # 3) Порты всех плат
            for equip in sec["boards"]:
                for i, port in enumerate(equip["ports"]):
                    ry = cr.y + y - self.scroll_y
                    in_lacp = port_in_lacp(equip, i) is not None
                    link_rect = pygame.Rect(cr.x + UCW_X_LINK, ry + 10,
                                            UCW_LINK_W, UCW_LINK_H)
                    self._link_hits.append((link_rect, equip, i))
                    desc_ti = self.inputs[(equip["id"], i, "desc")]
                    desc_ti.set_rect((cr.x + UCW_X_DESC, ry + 10, UCW_DESC_W, 26))
                    speed_rect = pygame.Rect(cr.x + UCW_X_SPEED, ry + 10,
                                             UCW_SPEED_W, 26)
                    if not in_lacp:
                        self._speed_hits.append((speed_rect, "port", equip, i))
                    mode_rect = pygame.Rect(cr.x + UCW_X_MODE, ry + 10,
                                            UCW_MODE_W, 26)
                    if not in_lacp:
                        self._mode_hits.append((mode_rect, equip, i))
                    vlan_ti = self.inputs[(equip["id"], i, "vlan")]
                    vlan_ti.set_rect((cr.x + UCW_X_VLAN, ry + 10, UCW_VLAN_W, 26))
                    y += self.row_h
                # LACP-строки
                for grp in equip.get("lacp_groups", []):
                    ry = cr.y + y - self.scroll_y
                    desc_ti = self.lacp_inputs[(equip["id"], grp["id"])]
                    desc_ti.set_rect((cr.x + UCW_X_DESC, ry + 10, UCW_DESC_W, 26))
                    speed_rect = pygame.Rect(cr.x + UCW_X_SPEED, ry + 10,
                                             UCW_SPEED_W, 26)
                    self._speed_hits.append((speed_rect, "lacp", equip, grp))
                    y += self.row_h
            # 4) Кнопки секции
            ry = cr.y + y - self.scroll_y
            add_lacp_rect = pygame.Rect(cr.x + UCW_X_PORT, ry + 8, 140, 28)
            self._add_lacp_hits.append((add_lacp_rect, sec["boards"][0]))
            merge_rect = pygame.Rect(cr.x + UCW_X_PORT + 150, ry + 8, 140, 28)
            self._merge_hits.append((merge_rect, sec["boards"][0]))
            if sec["chassis"] is not None:
                group_rect = pygame.Rect(cr.x + UCW_X_PORT + 300, ry + 8, 170, 28)
                self._group_hits.append((group_rect, sec["chassis"]))
            y += self.row_h + UCW_SECTION_GAP

    # ----- общие утилиты по событиям -----
    def _all_inputs(self):
        for ti in self.inputs.values():
            yield ti
        for ti in self.lacp_inputs.values():
            yield ti
        for ti in self.name_inputs.values():
            yield ti

    def is_text_input_active(self):
        return any(ti.active for ti in self._all_inputs())

    def _toggle_admin_state(self, port):
        st = port.get("admin_state", "up")
        port["admin_state"] = "up" if st == "shut" else "shut"

    def _toggle_mode(self, port):
        port["mode"] = "trunk" if port.get("mode", "access") == "access" else "access"

    def _max_vlan_len(self, port):
        return 6 if port.get("mode", "access") == "access" else 64

    def handle_event(self, event):
        # Футер (сохранить) — до sync
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._save_btn.collidepoint(event.pos):
                self._save_and_close()
                return True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._sync_positions()

            if event.type == pygame.KEYDOWN:
                for ti in self._all_inputs():
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                return False

            if event.button == 1:
                if self.close_rect().collidepoint(event.pos):
                    self.close()
                    return True
                if self.titlebar_rect().collidepoint(event.pos):
                    self.dragging = True
                    self.drag_offset_x = event.pos[0] - self.x
                    self.drag_offset_y = event.pos[1] - self.y
                    return True

                # Кнопки секций
                for rect, equip in self._add_lacp_hits:
                    if rect.collidepoint(event.pos):
                        self._open_lacp_input(equip)
                        return True
                for rect, equip in self._merge_hits:
                    if rect.collidepoint(event.pos):
                        if self.game and self.game.ui_manager:
                            self.game.ui_manager.open_chassis_merge(equip)
                        return True
                for rect, grp in self._group_hits:
                    if rect.collidepoint(event.pos):
                        if self.game and self.game.ui_manager:
                            self.game.ui_manager.open_chassis_settings(grp)
                        return True

                # Link
                for rect, equip, i in self._link_hits:
                    if rect.collidepoint(event.pos):
                        self._toggle_admin_state(equip["ports"][i])
                        return True

                # Speed (port или lacp)
                for rect, kind, equip, ref in self._speed_hits:
                    if rect.collidepoint(event.pos):
                        if kind == "port":
                            if _find_cable_100(self.game, equip["id"], ref):
                                print("Кабель 100Мб ограничивает скорость")
                                return True
                            toggle_port_speed(self.game, equip, ref)
                        else:
                            toggle_lacp_speed(ref, self.game)
                        return True

                # Mode
                for rect, equip, i in self._mode_hits:
                    if rect.collidepoint(event.pos):
                        self._toggle_mode(equip["ports"][i])
                        return True

                # TextInput'ы
                cr = self.content_rect()
                in_content = cr.collidepoint(event.pos)
                clicked_input = False
                if in_content:
                    for ti in self.name_inputs.values():
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                    for (eid, i, kind), ti in self.inputs.items():
                        equip = self._find_equip(eid)
                        if equip is None:
                            continue
                        if port_in_lacp(equip, i) is not None and kind in ("vlan",):
                            # VLAN в LACP-порту не редактируется
                            continue
                        if ti.handle_event(event, self._cfg_font):
                            # динамически ограничим длину для vlan по mode
                            if kind == "vlan":
                                ti.max_length = self._max_vlan_len(equip["ports"][i])
                            clicked_input = True
                    for key, ti in self.lacp_inputs.items():
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                else:
                    for ti in self._all_inputs():
                        ti.active = False
                if clicked_input:
                    return True

                if self.contains(event.pos):
                    for ti in self._all_inputs():
                        ti.active = False
                    return True
                self.close()
                return True

        return super().handle_event(event)

    def _find_equip(self, eid):
        for sec in self.sections:
            for e in sec["boards"]:
                if e["id"] == eid:
                    return e
        return None

    def _open_lacp_input(self, equip):
        sw, sh = _screen_size()
        target = equip

        def on_submit(selected_ports):
            ports = sorted(p for p in selected_ports
                           if port_in_lacp(target, p) is None)
            if len(ports) < 2:
                print("LACP: нужно выбрать минимум 2 свободных порта")
                return
            new_id = max([g["id"] for g in target["lacp_groups"]], default=0) + 1
            grp = {"id": new_id, "name": f"LACP-{new_id}",
                   "ports": ports, "speed": 1000, "label": ""}
            target["lacp_groups"].append(grp)
            self._persist()
            self._build_inputs()
            self._compute_content_height()
            _notify_speed_changed(self.game)
            print(f"Создана группа {grp['name']} из портов "
                  f"{[p + 1 for p in ports]} (плата #{target['id']})")

        self.lacp_input_window = LACPInputWindow(
            on_submit, sw, sh, target, lambda p: port_in_lacp(target, p) is None)
        # modal: menedjer сам прорисует поверх нашего окна
        if self.game and self.game.ui_manager:
            self.game.ui_manager.active_window = self.lacp_input_window

    def _persist(self):
        """Сохраняет все значения из TextInput в объекты модели."""
        for (eid, i, kind), ti in self.inputs.items():
            equip = self._find_equip(eid)
            if equip is None:
                continue
            port = equip["ports"][i]
            if kind == "desc":
                if port_in_lacp(equip, i) is None:
                    port["label"] = ti.text
            elif kind == "vlan":
                if port_in_lacp(equip, i) is None:
                    port["vlan_string"] = ti.text
        for (eid, gid), ti in self.lacp_inputs.items():
            equip = self._find_equip(eid)
            if equip is None:
                continue
            for grp in equip.get("lacp_groups", []):
                if grp["id"] == gid:
                    grp["label"] = ti.text
                    break
        for sec in self.sections:
            if sec["chassis"] is not None:
                grp = sec["chassis"]
                ti = self.name_inputs.get(grp["id"])
                if ti is not None and ti.text:
                    grp["name"] = ti.text

    def _save_and_close(self):
        self._persist()
        print("Настройки оборудования сохранены")
        self.close()

    # ----- отрисовка -----
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
        pygame.draw.ellipse(screen, color, rect)
        pygame.draw.ellipse(screen, COLOR_LINK_EDGE, rect, 1)
        surf = self._tiny.render(text, True, (255, 255, 255))
        screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                           rect.centery - surf.get_height() // 2))

    def _draw_mini_button(self, screen, rect, text, disabled=False):
        if disabled:
            pygame.draw.rect(screen, COLOR_BTN_DIS_BG, rect, border_radius=5)
            pygame.draw.rect(screen, COLOR_BTN_DIS_EDGE, rect, 1, border_radius=5)
            tcol = (140, 140, 150)
        else:
            mouse = pygame.mouse.get_pos()
            state = "hover" if rect.collidepoint(mouse) else "normal"
            draw_fancy_button(screen, self._tiny, rect, text, state=state, radius=5)
            return
        surf = self._tiny.render(text, True, tcol)
        screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                           rect.centery - surf.get_height() // 2))

    def _draw_disabled_input(self, screen, rect):
        pygame.draw.rect(screen, COLOR_BTN_DIS_BG, rect, border_radius=4)
        pygame.draw.rect(screen, COLOR_BTN_DIS_EDGE, rect, 1, border_radius=4)
        s = self._tiny.render("—", True, (140, 140, 150))
        screen.blit(s, (rect.centerx - s.get_width() // 2,
                        rect.centery - s.get_height() // 2))

    def _render_content(self, surface, font, small_font):
        """Рисуем только статические элементы (заголовки, номера портов, надписи LACP).
        Интерактивные (Link, Speed, Mode, TextInput'ы) — в draw() поверх."""
        y = 10
        for sec in self.sections:
            # Заголовок секции
            ry = y - self.scroll_y
            if 0 <= ry + self.row_h and ry < surface.get_height():
                hdr = self._header_font.render(sec["title"], True, COLOR_TITLE)
                surface.blit(hdr, (UCW_X_PORT, ry + 12))
            y += self.row_h
            # Имя шасси — только подпись слева (сам TextInput рисуется в draw)
            if sec["chassis"] is not None:
                ry = y - self.scroll_y
                if 0 <= ry + self.row_h and ry < surface.get_height():
                    lbl = self._tiny.render("Имя шасси:", True, COLOR_TEXT_DIM)
                    surface.blit(lbl, (UCW_X_PORT, ry + 16))
                y += self.row_h
            # Порты
            for equip in sec["boards"]:
                for i, port in enumerate(equip["ports"]):
                    ry = y - self.scroll_y
                    if 0 <= ry + self.row_h and ry < surface.get_height():
                        pname = (port_name(self.game, equip, i)
                                 if self.game else f"{i + 1}")
                        in_lacp = port_in_lacp(equip, i) is not None
                        col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
                        num = self._cfg_font.render(pname, True, col)
                        surface.blit(num, (UCW_X_PORT, ry + 14))
                    y += self.row_h
                # LACP-строки
                for grp in equip.get("lacp_groups", []):
                    ry = y - self.scroll_y
                    if 0 <= ry + self.row_h and ry < surface.get_height():
                        name = self._cfg_font.render(grp["name"], True, COLOR_LACP_ROW)
                        surface.blit(name, (UCW_X_PORT, ry + 14))
                        members = ",".join(str(p + 1) for p in grp["ports"])
                        meta = self._tiny.render(f"порты: {members}",
                                                 True, COLOR_LACP_ROW)
                        surface.blit(meta, (UCW_X_DESC - 50, ry + 30))
                    y += self.row_h
            # Кнопки секции (пустая строка — сами кнопки в draw)
            y += self.row_h + UCW_SECTION_GAP

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._sync_positions()

        cr = self.content_rect()
        old_clip = screen.get_clip()
        screen.set_clip(cr)

        # TextInput имени шасси
        for sec in self.sections:
            if sec["chassis"] is not None:
                ti = self.name_inputs[sec["chassis"]["id"]]
                if cr.y - 30 <= ti.rect.y <= cr.bottom:
                    ti.draw(screen, self._cfg_font)

        # Link pills
        for rect, equip, i in self._link_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            port = equip["ports"][i]
            self._draw_link_pill(screen, rect, _link_state(port))

        # Speed buttons
        for rect, kind, equip, ref in self._speed_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            if kind == "port":
                spd = equip["ports"][ref]["speed"]
            else:
                spd = ref.get("speed", 1000)
            self._draw_mini_button(screen, rect, speed_label(spd), disabled=False)

        # Для портов в LACP — заглушки speed/mode/vlan
        for sec in self.sections:
            for equip in sec["boards"]:
                for i, port in enumerate(equip["ports"]):
                    if port_in_lacp(equip, i) is None:
                        continue
                    # найти соответствующую строку по rect из link_hits
                    row_rect = None
                    for lr, e, pi in self._link_hits:
                        if e is equip and pi == i:
                            row_rect = lr
                            break
                    if row_rect is None:
                        continue
                    if not (cr.y - 30 <= row_rect.y <= cr.bottom):
                        continue
                    y = row_rect.y
                    sp = pygame.Rect(cr.x + UCW_X_SPEED, y, UCW_SPEED_W, 26)
                    md = pygame.Rect(cr.x + UCW_X_MODE, y, UCW_MODE_W, 26)
                    vl = pygame.Rect(cr.x + UCW_X_VLAN, y, UCW_VLAN_W, 26)
                    self._draw_mini_button(screen, sp, "LACP", disabled=True)
                    self._draw_mini_button(screen, md, "LACP", disabled=True)
                    self._draw_disabled_input(screen, vl)

        # Mode buttons
        for rect, equip, i in self._mode_hits:
            if not (cr.y - 30 <= rect.y <= cr.bottom):
                continue
            mode = equip["ports"][i].get("mode", "access")
            self._draw_mini_button(screen, rect, mode, disabled=False)

        # TextInput'ы desc/vlan (кроме LACP-портов, которые заглушены)
        for (eid, i, kind), ti in self.inputs.items():
            equip = self._find_equip(eid)
            if equip is None:
                continue
            if port_in_lacp(equip, i) is not None and kind == "vlan":
                continue  # VLAN в LACP не рисуем — выше нарисовали заглушку
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)
        # LACP-label (desc)
        for key, ti in self.lacp_inputs.items():
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)

        # Кнопки секций (ADD_LACP / Merge / Group)
        for rect, equip in self._add_lacp_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                draw_button_screen(screen, self._tiny, rect, "+ADD_LACP")
        for rect, equip in self._merge_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                draw_button_screen(screen, self._tiny, rect, "⛓ Коммутация")
        for rect, grp in self._group_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                draw_button_screen(screen, self._tiny, rect, "⚙ Настройки группы")

        screen.set_clip(old_clip)

        # Футер: Save по центру
        self._save_btn = pygame.Rect(self.x + self.width // 2 - 80,
                                     self.y + self.height - FOOTER_H + 6, 160, 30)
        draw_button_screen(screen, small_font, self._save_btn, "💾 Сохранить")
        
        