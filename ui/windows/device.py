#!/usr/bin/env python3
"""ui/device.py - главные окна свитчей и роутеров (просмотр портов + LACP)."""

import pygame

from config import (
    COLOR_TITLE, COLOR_TEXT, COLOR_PORT_EDGE, COLOR_PORT_EDGE_HOVER,
    COLOR_PORT_LACP, COLOR_LACP_ROW,
    HEADER_H, FOOTER_H,
)
from ui.base import Window
from ui.widgets import (
    _vgrad_rect, draw_fancy_button, draw_button_screen, speed_label,
)
from ui.net_helpers import (
    find_cable_for_port, port_in_lacp, toggle_port_speed, toggle_lacp_speed,
    port_fill_color, port_status_text_color, lacp_effective_label,
)


class SwitchWindow(Window):
    def __init__(self, equipment_list, screen_w, screen_h, game=None, manager=None):
        w, h = 380, 480
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equipment_list = equipment_list
        self.game = game
        self.manager = manager
        n = len(equipment_list)
        title = f"Свитчи в доме ({n} шт.)" if n > 1 else \
                f"Свитч {len(equipment_list[0]['ports'])}p #{equipment_list[0]['id']}"
        super().__init__(x, y, w, h, title)
        self.cols = 4
        self.box = 46
        self.gap = 12
        self.header_gap = 30
        self.lacp_gap = 22
        self.block_gap = 24
        self._hit_ports = []
        self._config_btn = pygame.Rect(0, 0, 0, 0)
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _equip_block_h(self, equip):
        n = len(equip["ports"])
        rows = (n + self.cols - 1) // self.cols
        h = self.header_gap + rows * (self.box + self.gap + 14)
        for grp in equip.get("lacp_groups", []):
            m = len(grp["ports"])
            lrows = (m + self.cols - 1) // self.cols
            h += self.lacp_gap + lrows * (self.box + self.gap + 14)
        return h + self.block_gap

    def _compute_content_height(self):
        y = 10
        for equip in self.equipment_list:
            y += self._equip_block_h(equip)
        self.content_height = y + 10

    def _render_equip(self, surface, equip, y, tiny, small_font, cr, mouse):
        start_x = 14
        hdr = small_font.render(f"Свитч {len(equip['ports'])}p #{equip['id']}",
                                True, COLOR_TITLE)
        surface.blit(hdr, (start_x, y - self.scroll_y + 6))
        y += self.header_gap
        for i, port in enumerate(equip["ports"]):
            c = i % self.cols
            r = i // self.cols
            px = start_x + c * (self.box + self.gap)
            py = y + r * (self.box + self.gap + 14) - self.scroll_y
            if not (py + self.box + 14 < 0 or py > surface.get_height()):
                self._draw_port(surface, equip, i, px, py, tiny, small_font, cr, mouse)
            self._hit_ports.append((pygame.Rect(px, py + self.scroll_y - cr.y + cr.y,
                                                self.box, self.box), equip, i, "port"))
        n = len(equip["ports"])
        rows = (n + self.cols - 1) // self.cols
        y += rows * (self.box + self.gap + 14)
        for grp in equip.get("lacp_groups", []):
            lbl = small_font.render(f"⛓ {grp['name']}  ({speed_label(grp.get('speed', 1000))})",
                                    True, COLOR_LACP_ROW)
            surface.blit(lbl, (start_x, y - self.scroll_y + 4))
            y += self.lacp_gap
            for idx, pidx in enumerate(grp["ports"]):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap + 14) - self.scroll_y
                if not (py + self.box + 14 < 0 or py > surface.get_height()):
                    self._draw_lacp_member(surface, grp, pidx, px, py, tiny, small_font)
            m = len(grp["ports"])
            lrows = (m + self.cols - 1) // self.cols
            y += lrows * (self.box + self.gap + 14)
        return y + self.block_gap

    def _draw_port(self, surface, equip, i, px, py, tiny, small_font, cr, mouse):
        prect = pygame.Rect(px, py, self.box, self.box)
        hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
        base = port_fill_color(self.game, equip, i, hover)
        _vgrad_rect(surface, prect,
                    tuple(min(255, cc + 30) for cc in base), base, radius=6)
        edge = COLOR_PORT_EDGE_HOVER if hover else COLOR_PORT_EDGE
        pygame.draw.rect(surface, edge, prect, 2 if hover else 1, border_radius=6)
        num = small_font.render(str(i + 1), True, COLOR_TEXT)
        surface.blit(num, (px + 4, py + 3))
        cable = find_cable_for_port(self.game, equip["id"], i)
        if cable is not None and cable.get("speed_mismatch"):
            sm = tiny.render("SM!", True, (255, 255, 255))
            surface.blit(sm, (px + self.box // 2 - sm.get_width() // 2,
                              py + self.box - 15))
        else:
            sp = tiny.render(speed_label(equip["ports"][i]["speed"]), True, COLOR_TEXT)
            surface.blit(sp, (px + self.box // 2 - sp.get_width() // 2,
                              py + self.box - 15))
        lbl_text = lacp_effective_label(equip, i)
        if lbl_text:
            lbl = tiny.render(lbl_text, True, (200, 220, 255))
            surface.blit(lbl, (px + self.box // 2 - lbl.get_width() // 2,
                              py + self.box + 1))

    def _draw_lacp_member(self, surface, grp, pidx, px, py, tiny, small_font):
        prect = pygame.Rect(px, py, self.box, self.box)
        _vgrad_rect(surface, prect,
                    tuple(min(255, c + 30) for c in COLOR_PORT_LACP),
                    COLOR_PORT_LACP, radius=6)
        pygame.draw.rect(surface, COLOR_LACP_ROW, prect, 2, border_radius=6)
        num = small_font.render(str(pidx + 1), True, COLOR_TEXT)
        surface.blit(num, (px + 4, py + 3))
        sp = tiny.render(speed_label(grp.get("speed", 1000)), True, COLOR_TEXT)
        surface.blit(sp, (px + self.box // 2 - sp.get_width() // 2,
                          py + self.box - 15))
        lbl = tiny.render(grp["name"], True, COLOR_LACP_ROW)
        surface.blit(lbl, (px + self.box // 2 - lbl.get_width() // 2,
                          py + self.box + 1))

    def _layout(self):
        self._hit_ports = []
        start_x = 14
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            for i, _ in enumerate(equip["ports"]):
                c = i % self.cols
                r = i // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap + 14)
                self._hit_ports.append((pygame.Rect(px, py, self.box, self.box), equip, i))
            n = len(equip["ports"])
            rows = (n + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap + 14)
            for grp in equip.get("lacp_groups", []):
                y += self.lacp_gap
                m = len(grp["ports"])
                lrows = (m + self.cols - 1) // self.cols
                y += lrows * (self.box + self.gap + 14)
            y += self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        content_x = local_x - cr.x
        content_y = local_y - cr.y
        self._layout()
        for rect, equip, i in self._hit_ports:
            if rect.collidepoint(content_x, content_y):
                toggle_port_speed(self.game, equip, i)
                return

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._config_btn.collidepoint(event.pos):
                if self.manager is not None:
                    self.manager.open_switch_config(self.equipment_list[0])
                return True
        return super().handle_event(event)

    def _render_content(self, surface, font, small_font):
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        self._hit_ports = []
        y = 10
        for equip in self.equipment_list:
            y = self._render_equip(surface, equip, y, tiny, small_font, cr, mouse)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._config_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                       self.y + self.height - FOOTER_H + 6, 140, 30)
        draw_button_screen(screen, small_font, self._config_btn, "⚙ Config")


class RouterWindow(Window):
    def __init__(self, equipment_list, screen_w, screen_h, game=None, manager=None):
        w, h = 440, 340
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equipment_list = equipment_list
        self.game = game
        self.manager = manager
        n = len(equipment_list)
        title = f"Роутеры в доме ({n} шт.)" if n > 1 else f"Роутер #{equipment_list[0]['id']}"
        super().__init__(x, y, w, h, title)
        self.row_h = 40
        self.header_gap = 28
        self.block_gap = 16
        self._hit_buttons = []
        self._config_btn = pygame.Rect(0, 0, 0, 0)
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _equip_rows(self, equip):
        return len(equip["ports"]) + len(equip.get("lacp_groups", []))

    def _compute_content_height(self):
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            y += self._equip_rows(equip) * self.row_h + self.block_gap
        self.content_height = y + 10

    def _layout(self):
        self._hit_buttons = []
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            row = 0
            for i, _ in enumerate(equip["ports"]):
                ry = y + row * self.row_h
                if port_in_lacp(equip, i) is None:
                    self._hit_buttons.append((pygame.Rect(310, ry, 110, 26),
                                              "port", equip, i))
                row += 1
            for grp in equip.get("lacp_groups", []):
                ry = y + row * self.row_h
                self._hit_buttons.append((pygame.Rect(310, ry, 110, 26),
                                          "lacp", equip, grp))
                row += 1
            y += self._equip_rows(equip) * self.row_h + self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        content_x = local_x - cr.x
        content_y = local_y - cr.y
        self._layout()
        for rect, kind, equip, ref in self._hit_buttons:
            if rect.collidepoint(content_x, content_y):
                if kind == "port":
                    toggle_port_speed(self.game, equip, ref)
                else:
                    toggle_lacp_speed(ref, self.game)
                return

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._config_btn.collidepoint(event.pos):
                if self.manager is not None:
                    self.manager.open_router_config(self.equipment_list[0])
                return True
        return super().handle_event(event)

    def _render_content(self, surface, font, small_font):
        self._layout()
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        y = 10
        for equip in self.equipment_list:
            hdr = small_font.render(f"Роутер #{equip['id']}", True, COLOR_TITLE)
            surface.blit(hdr, (14, y - self.scroll_y + 4))
            y += self.header_gap
            row = 0
            for i, port in enumerate(equip["ports"]):
                ry = y + row * self.row_h - self.scroll_y
                row += 1
                if ry + self.row_h < 0 or ry > surface.get_height():
                    continue
                color = port_fill_color(self.game, equip, i)
                ind = pygame.Rect(14, ry, 20, 20)
                _vgrad_rect(surface, ind,
                            tuple(min(255, c + 30) for c in color), color, radius=4)
                pygame.draw.rect(surface, COLOR_PORT_EDGE, ind, 1, border_radius=4)
                status, col = port_status_text_color(self.game, equip, i)
                lbl_text = lacp_effective_label(equip, i)
                lbl_part = f"  [{lbl_text}]" if lbl_text else ""
                label = small_font.render(f"Порт {i + 1}: {status}{lbl_part}", True, col)
                surface.blit(label, (42, ry + 2))
                btn = pygame.Rect(310, ry, 110, 26)
                hover = btn.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                if port_in_lacp(equip, i) is not None:
                    draw_fancy_button(surface, small_font, btn, "LACP", state="disabled")
                else:
                    draw_fancy_button(surface, small_font, btn,
                                      f"Скор: {speed_label(port['speed'])}",
                                      state="hover" if hover else "normal")
            for grp in equip.get("lacp_groups", []):
                ry = y + row * self.row_h - self.scroll_y
                row += 1
                if ry + self.row_h < 0 or ry > surface.get_height():
                    continue
                ind = pygame.Rect(14, ry, 20, 20)
                _vgrad_rect(surface, ind,
                            tuple(min(255, c + 30) for c in COLOR_LACP_ROW),
                            COLOR_LACP_ROW, radius=4)
                pygame.draw.rect(surface, (200, 230, 255), ind, 1, border_radius=4)
                members = ",".join(str(p + 1) for p in grp["ports"])
                lbl = grp.get("label", "")
                lbl_part = f"  [{lbl}]" if lbl else ""
                label = small_font.render(f"{grp['name']} (порты {members}){lbl_part}",
                                          True, COLOR_LACP_ROW)
                surface.blit(label, (42, ry + 2))
                btn = pygame.Rect(310, ry, 110, 26)
                hover = btn.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                draw_fancy_button(surface, small_font, btn,
                                  f"Скор: {speed_label(grp.get('speed', 1000))}",
                                  state="hover" if hover else "normal")
            y += self._equip_rows(equip) * self.row_h + self.block_gap

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._config_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                       self.y + self.height - FOOTER_H + 6, 140, 30)
        draw_button_screen(screen, small_font, self._config_btn, "⚙ Config")
        