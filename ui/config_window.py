#!/usr/bin/env python3
"""ui/config_window.py - окна конфигурации свитча/роутера (подписи, скорость, LACP, шасси)."""

import pygame

from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TITLE, COLOR_STATUS_LACP, COLOR_LACP_ROW,
    HEADER_H, FOOTER_H,
    COL_NUM, COL_STATUS, COL_INPUT, COL_INPUT_W, COL_SPEED, COL_SPEED_W, ROW_H_CFG,
)
from ui.base import Window
from ui.widgets import (
    _vgrad_rect, draw_button_screen, speed_label, TextInput, _screen_size,
)
from ui.net_helpers import (
    port_in_lacp, toggle_port_speed, toggle_lacp_speed,
    equip_type_label, port_status_text_color, _notify_speed_changed,
)
from ui.lacp import LACPInputWindow
from ui.chassis import port_name, board_label


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
        self._add_vlan_btn = pygame.Rect(0, 0, 0, 0)
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
                self._add_vlan_btn = pygame.Rect(cr.x + COL_NUM + 160, ry + 6, 150, 28)

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

        # Футерные кнопки + поле имени шасси — только MOUSEBUTTONDOWN
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
                if self._add_vlan_btn.collidepoint(event.pos):
                    print("VLAN: В разработке")
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
        target = self.equip   # LACP строго внутри одной платы — текущая equip

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
        """Полоска с именем шасси (рисуется под титлбаром, перед колонками)."""
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
            draw_button_screen(screen, small_font, self._add_vlan_btn, "+ADD_VLAN")
        screen.set_clip(old_clip)

        # Футер: Save (центр), Merge (слева), Group settings (справа, если шасси)
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
        # Роутер по умолчанию компактнее (4 порта); в шасси — расширяем
        if self.chassis is not None:
            self.width, self.height = 540, 520
        else:
            self.width, self.height = 540, 400
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self._compute_content_height()
        
        