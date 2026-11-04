#!/usr/bin/env python3
"""ui/port_select.py - окно выбора порта (с группировкой по платам шасси)."""

import pygame

from config import COLOR_TITLE, COLOR_TEXT_DIM
from ui.base import Window
from ui.widgets import draw_fancy_button
from ui.net_helpers import port_in_lacp, equip_type_label
from ui.chassis import board_label, port_name


class PortSelectWindow(Window):
    def __init__(self, devices_list, is_second_click, callback, screen_w, screen_h,
                 game=None):
        w, h = 340, 440
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.devices_list = devices_list
        self.is_second_click = is_second_click
        self.callback = callback
        self.game = game
        title = "Выбор порта (цель)" if is_second_click else "Выбор порта (старт)"
        super().__init__(x, y, w, h, title)
        self.cols = 4
        self.box = 44
        self.gap = 10
        self.header_gap = 26
        self.subheader_gap = 20
        self.block_gap = 16
        self._hit_ports = []
        # Собираем кластеры: один visible "root" для шасси (первая плата)
        # либо отдельное устройство, если не в шасси.
        self._clusters = self._build_clusters(devices_list)
        self._compute_content_height()

    # ---- кластеризация ----
    def _build_clusters(self, devices_list):
        """
        Возвращает список кластеров:
          {"root": equip, "chassis": grp or None, "boards": [equip,...]}
        Если несколько устройств из одного шасси — объединяются в один кластер
        (root = первое устройство этого шасси из devices_list).
        """
        clusters = []
        seen_chassis = set()
        for d in devices_list:
            grp = self.game.chassis_of(d["id"]) if self.game else None
            if grp is not None:
                if grp["id"] in seen_chassis:
                    continue
                seen_chassis.add(grp["id"])
                boards = (self.game.equipment_in_chassis(grp["id"])
                          if self.game else [d])
                clusters.append({"root": d, "chassis": grp, "boards": boards})
            else:
                clusters.append({"root": d, "chassis": None, "boards": [d]})
        return clusters

    def _free_ports(self, device):
        return [i for i, p in enumerate(device["ports"])
                if p["free"] and port_in_lacp(device, i) is None]

    def _block_h(self, cluster):
        """Высота блока одного кластера (устройства или шасси)."""
        h = self.header_gap
        any_rows = False
        for equip in cluster["boards"]:
            free = self._free_ports(equip)
            if not free:
                continue
            any_rows = True
            if cluster["chassis"] is not None:
                h += self.subheader_gap
            rows = (len(free) + self.cols - 1) // self.cols
            h += rows * (self.box + self.gap)
        if not any_rows:
            return 0
        return h + self.block_gap

    def _compute_content_height(self):
        y = 8
        for cl in self._clusters:
            y += self._block_h(cl)
        self.content_height = y + 8

    def _layout(self):
        self._hit_ports = []
        start_x = 14
        y = 8
        for cl in self._clusters:
            if self._block_h(cl) == 0:
                continue
            y += self.header_gap
            for equip in cl["boards"]:
                free = self._free_ports(equip)
                if not free:
                    continue
                if cl["chassis"] is not None:
                    y += self.subheader_gap
                for idx, pi in enumerate(free):
                    c = idx % self.cols
                    r = idx // self.cols
                    px = start_x + c * (self.box + self.gap)
                    py = y + r * (self.box + self.gap)
                    self._hit_ports.append(
                        (pygame.Rect(px, py, self.box, self.box), equip, pi))
                rows = (len(free) + self.cols - 1) // self.cols
                y += rows * (self.box + self.gap)
            y += self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        cx = local_x - cr.x
        cy = local_y - cr.y
        self._layout()
        for rect, equip, pi in self._hit_ports:
            if rect.collidepoint(cx, cy):
                cb = self.callback
                self.close()
                cb(equip, pi)
                return

    def _render_content(self, surface, font, small_font):
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        start_x = 14
        y = 8
        for cl in self._clusters:
            if self._block_h(cl) == 0:
                continue
            # заголовок кластера
            if cl["chassis"] is not None:
                hdr_text = f"Шасси: {cl['chassis'].get('name', 'Chassis')}"
            else:
                d = cl["root"]
                hdr_text = f"{equip_type_label(d)} #{d['id']}"
            hdr = small_font.render(hdr_text, True, COLOR_TITLE)
            surface.blit(hdr, (start_x, y - self.scroll_y + 4))
            y += self.header_gap

            for bidx, equip in enumerate(cl["boards"], 1):
                free = self._free_ports(equip)
                if not free:
                    continue
                if cl["chassis"] is not None:
                    bname = board_label(cl["chassis"], equip["id"], bidx)
                    sub = tiny.render(f"━ {bname} (#{equip['id']})",
                                      True, COLOR_TEXT_DIM)
                    surface.blit(sub, (start_x, y - self.scroll_y + 2))
                    y += self.subheader_gap
                for idx, pi in enumerate(free):
                    c = idx % self.cols
                    r = idx // self.cols
                    px = start_x + c * (self.box + self.gap)
                    py = y + r * (self.box + self.gap) - self.scroll_y
                    if py + self.box < 0 or py > surface.get_height():
                        continue
                    prect = pygame.Rect(px, py, self.box, self.box)
                    hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                    # имя: board/port (для шасси) либо просто номер
                    if cl["chassis"] is not None and self.game is not None:
                        label = port_name(self.game, equip, pi)
                    else:
                        label = str(pi + 1)
                    draw_fancy_button(surface, tiny, prect, label,
                                      state="hover" if hover else "normal")
                rows = (len(free) + self.cols - 1) // self.cols
                y += rows * (self.box + self.gap)
            y += self.block_gap
            
            