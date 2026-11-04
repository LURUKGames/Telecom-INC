#!/usr/bin/env python3
"""ui/config_window.py - окна конфигурации свитча/роутера (подписи, скорость, LACP)."""

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


class SwitchConfigWindow(Window):
    def __init__(self, equip, screen_w, screen_h, game=None):
        w, h = 480, 520
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equip = equip
        self.game = game
        self.equip.setdefault("lacp_groups", [])
        super().__init__(x, y, w, h,
                         f"Config: {equip_type_label(equip)} #{equip['id']}")
        self.row_h = ROW_H_CFG
        self.inputs = []
        self.lacp_inputs = []
        self._speed_buttons = []
        self._save_btn = pygame.Rect(0, 0, 0, 0)
        self._add_lacp_btn = pygame.Rect(0, 0, 0, 0)
        self._add_vlan_btn = pygame.Rect(0, 0, 0, 0)
        self._cfg_font = pygame.font.SysFont("arial,dejavusans", 14)
        self._header_font = pygame.font.SysFont("arial,dejavusans", 12)
        self.lacp_input_window = None
        self._build_inputs()
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H + 22,
                           self.width, self.height - HEADER_H - FOOTER_H - 22)

    def _build_inputs(self):
        self.inputs = []
        for i, port in enumerate(self.equip["ports"]):
            ti = TextInput((0, 0, COL_INPUT_W, 26),
                           initial_text=port.get("label", ""), max_length=15)
            self.inputs.append((i, ti))
        self.lacp_inputs = []
        for grp in self.equip["lacp_groups"]:
            ti = TextInput((0, 0, COL_INPUT_W, 26),
                           initial_text=grp.get("label", ""), max_length=15)
            self.lacp_inputs.append((grp, ti))

    def _n_rows(self):
        return len(self.equip["ports"]) + len(self.equip["lacp_groups"]) + 1

    def _compute_content_height(self):
        self.content_height = 10 + self._n_rows() * self.row_h + 20

    def _row_y(self, row_index):
        return 10 + row_index * self.row_h

    def is_text_input_active(self):
        if self.lacp_input_window is not None:
            return True
        return (any(ti.active for _, ti in self.inputs)
                or any(ti.active for _, ti in self.lacp_inputs))

    def _sync_positions(self):
        cr = self.content_rect()
        self._speed_buttons = []
        row = 0
        for (i, ti) in self.inputs:
            ry = cr.y + self._row_y(row) - self.scroll_y
            ti.set_rect((cr.x + COL_INPUT, ry + 6, COL_INPUT_W, 26))
            if port_in_lacp(self.equip, i) is None:
                btn = pygame.Rect(cr.x + COL_SPEED, ry + 6, COL_SPEED_W, 26)
                self._speed_buttons.append((btn, "port", i))
            row += 1
        for (grp, ti) in self.lacp_inputs:
            ry = cr.y + self._row_y(row) - self.scroll_y
            ti.set_rect((cr.x + COL_INPUT, ry + 6, COL_INPUT_W, 26))
            btn = pygame.Rect(cr.x + COL_SPEED, ry + 6, COL_SPEED_W, 26)
            self._speed_buttons.append((btn, "lacp", grp))
            row += 1
        ry = cr.y + self._row_y(row) - self.scroll_y
        self._add_lacp_btn = pygame.Rect(cr.x + COL_NUM, ry + 6, 150, 28)
        self._add_vlan_btn = pygame.Rect(cr.x + COL_NUM + 160, ry + 6, 150, 28)

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

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._sync_positions()

            if event.type == pygame.KEYDOWN:
                for _, ti in self.inputs:
                    if ti.active:
                        return ti.handle_event(event, self._cfg_font)
                for _, ti in self.lacp_inputs:
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
                    for i, ti in self.inputs:
                        if port_in_lacp(self.equip, i) is not None:
                            continue
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                    for _, ti in self.lacp_inputs:
                        if ti.handle_event(event, self._cfg_font):
                            clicked_input = True
                else:
                    for _, ti in self.inputs:
                        ti.active = False
                    for _, ti in self.lacp_inputs:
                        ti.active = False
                if clicked_input:
                    return True

                if in_content:
                    for btn, kind, ref in self._speed_buttons:
                        if btn.collidepoint(event.pos):
                            if kind == "port":
                                toggle_port_speed(self.game, self.equip, ref)
                            else:
                                toggle_lacp_speed(ref, self.game)
                            return True

                if self.contains(event.pos):
                    for _, ti in self.inputs:
                        ti.active = False
                    for _, ti in self.lacp_inputs:
                        ti.active = False
                    return True
                self.close()
                return True

        return super().handle_event(event)

    def _free_for_lacp(self, port_index):
        return port_in_lacp(self.equip, port_index) is None

    def _open_lacp_input(self):
        sw, sh = _screen_size()

        def on_submit(selected_ports):
            ports = sorted(p for p in selected_ports
                           if self._free_for_lacp(p))
            if len(ports) < 2:
                print("LACP: нужно выбрать минимум 2 свободных порта")
                return
            new_id = max([g["id"] for g in self.equip["lacp_groups"]], default=0) + 1
            grp = {
                "id": new_id,
                "name": f"LACP-{new_id}",
                "ports": ports,
                "speed": 1000,
                "label": "",
            }
            self.equip["lacp_groups"].append(grp)
            for i, ti in self.inputs:
                self.equip["ports"][i]["label"] = ti.text
            self._build_inputs()
            self._compute_content_height()
            _notify_speed_changed(self.game)
            print(f"Создана группа {grp['name']} из портов "
                  f"{[p + 1 for p in ports]}")

        self.lacp_input_window = LACPInputWindow(
            on_submit, sw, sh, self.equip, self._free_for_lacp)

    def _save_and_close(self):
        for i, ti in self.inputs:
            if port_in_lacp(self.equip, i) is None:
                self.equip["ports"][i]["label"] = ti.text
        for grp, ti in self.lacp_inputs:
            grp["label"] = ti.text
        print(f"Настройки сохранены для {equip_type_label(self.equip)} "
              f"#{self.equip['id']}")
        self.close()

    def _draw_col_headers(self, screen):
        cr = self.content_rect()
        y = self.y + HEADER_H + 4
        headers = [(COL_NUM, "#"), (COL_STATUS, "Статус"),
                   (COL_INPUT, "Подпись"), (COL_SPEED, "Скорость")]
        for col_x, text in headers:
            surf = self._header_font.render(text, True, COLOR_TEXT_DIM)
            screen.blit(surf, (cr.x + col_x, y))
        pygame.draw.line(screen, (90, 90, 100),
                         (self.x + 8, self.y + HEADER_H + 20),
                         (self.x + self.width - 8, self.y + HEADER_H + 20), 1)

    def _render_content(self, surface, font, small_font):
        tiny = pygame.font.SysFont("arial,dejavusans", 12)
        row = 0
        for i, port in enumerate(self.equip["ports"]):
            ry = self._row_y(row) - self.scroll_y
            row += 1
            if ry + self.row_h < 0 or ry > surface.get_height():
                continue
            in_lacp = port_in_lacp(self.equip, i)
            num_col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
            num = font.render(f"{i + 1}", True, num_col)
            surface.blit(num, (COL_NUM, ry + 8))
            status, col = port_status_text_color(self.game, self.equip, i)
            st = tiny.render(status, True, col)
            surface.blit(st, (COL_STATUS, ry + 10))

        for grp, _ in self.lacp_inputs:
            ry = self._row_y(row) - self.scroll_y
            row += 1
            if ry + self.row_h < 0 or ry > surface.get_height():
                continue
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
        for (i, ti) in self.inputs:
            if port_in_lacp(self.equip, i) is not None:
                continue
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)
        for (grp, ti) in self.lacp_inputs:
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, self._cfg_font)
        for btn, kind, ref in self._speed_buttons:
            if cr.y - 30 <= btn.y <= cr.bottom:
                spd = (self.equip["ports"][ref]["speed"] if kind == "port"
                       else ref.get("speed", 1000))
                draw_button_screen(screen, small_font, btn, speed_label(spd))
        if cr.y - 30 <= self._add_lacp_btn.y <= cr.bottom:
            draw_button_screen(screen, small_font, self._add_lacp_btn, "+ADD_LACP")
            draw_button_screen(screen, small_font, self._add_vlan_btn, "+ADD_VLAN")
        screen.set_clip(old_clip)

        self._save_btn = pygame.Rect(self.x + self.width // 2 - 80,
                                     self.y + self.height - FOOTER_H + 6, 160, 30)
        draw_button_screen(screen, small_font, self._save_btn, "💾 Сохранить")

        if self.lacp_input_window is not None:
            self.lacp_input_window.draw(screen, font, small_font)


class RouterConfigWindow(SwitchConfigWindow):
    def __init__(self, equip, screen_w, screen_h, game=None):
        super().__init__(equip, screen_w, screen_h, game=game)
        self.width = 480
        self.height = 360
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self.title = f"Config: Роутер #{equip['id']}"
        self._compute_content_height()