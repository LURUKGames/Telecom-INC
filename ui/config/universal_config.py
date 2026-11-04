#!/usr/bin/env python3
"""
ui/universal_config.py - Главное окно настройки оборудования в доме (UCW).
Показывает список всех устройств, их порты, LACP-группы, позволяет
настраивать скорость, режим (access/trunk) и VLAN.
"""



import pygame
from config import (
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TITLE, COLOR_STATUS_LACP, COLOR_LACP_ROW,
    HEADER_H, FOOTER_H, COL_NUM, COL_STATUS, COL_INPUT, COL_INPUT_W,
    COL_SPEED, COL_SPEED_W, ROW_H_CFG,
)
from ui.base import Window
from ui.widgets import (
    _vgrad_rect, draw_fancy_button, draw_button_screen,
    speed_label, TextInput, _screen_size,
)
from ui.net_helpers import (
    port_in_lacp, toggle_port_speed, toggle_lacp_speed,
    equip_type_label, _notify_speed_changed, find_cable_for_port,
)
from ui.chassis import port_name, board_of_port, boards_summary
from ui.config.lacp import LACPInputWindow
from ui.config.commut import CommutWindow
from ui.config.vlan_popup import VlanPopupWindow

# --- Константы геометрии окна UCW ---
UCW_ROW_H = 46
UCW_X_PORT = 10
UCW_X_LINK = 50
UCW_LINK_W = 60
UCW_LINK_H = 26
UCW_X_DESC = 120
UCW_DESC_W = 130
UCW_X_SPEED = 260
UCW_SPEED_W = 60
UCW_X_MODE = 330
UCW_MODE_W = 80
UCW_X_VLAN = 420
UCW_VLAN_W = 110
UCW_SECTION_HDR_H = 34
UCW_SECTION_GAP = 10
UCW_FOOTER_H = 50

# --- Цвета ---
COLOR_LINK_UP = (60, 190, 90)
COLOR_LINK_DOWN = (210, 70, 70)
COLOR_LINK_EDGE = (230, 230, 230)
COLOR_BTN_DIS_BG = (60, 60, 66)
COLOR_BTN_DIS_EDGE = (95, 95, 105)
COLOR_SEL_SECTION = (70, 130, 200)
COLOR_MODE_BANNER = (50, 90, 150)

# --- Хелперы ---
def _ensure_port_fields(port):
    """Гарантирует, что у порта есть все нужные поля."""
    port.setdefault("admin_state", "up")
    port.setdefault("vlan_string", "")
    port.setdefault("mode", "access")

def _ensure_lacp_fields(grp):
    """Гарантирует, что у LACP-группы есть все нужные поля."""
    grp.setdefault("admin_state", "up")
    grp.setdefault("vlan_string", "")
    grp.setdefault("mode", "trunk")
    grp.setdefault("label", "")

def _port_link_state(port):
    """Возвращает статус порта: up / down / shut."""
    if port.get("admin_state", "up") == "shut":
        return "shut"
    return "down" if port.get("free", True) else "up"

def _lacp_link_state(equip, grp):
    """LACP горит зеленым, если хотя бы один порт из группы имеет линк."""
    if grp.get("admin_state", "up") == "shut":
        return "shut"
    for pi in grp["ports"]:
        if 0 <= pi < len(equip["ports"]):
            if not equip["ports"][pi].get("free", True):
                return "up"
    return "down"

def _vlan_preview(text):
    """Показывает первые 4 VLAN'а внутри кнопки."""
    if not text: return "VLAN"
    import re
    parts = [p.strip() for p in re.split(r"[,\n]", text) if p.strip()]
    if not parts: return "VLAN"
    shown = parts[:4]
    suffix = "..." if len(parts) > 4 else ""
    return ",".join(shown) + suffix

def _find_cable_100(game, equip_id, port_index):
    """Проверяет, подключен ли к порту кабель 100Мб (чтобы заблокировать смену скорости)."""
    if game is None: return False
    for cable in game.cables:
        a_match = cable["a"] == equip_id and cable["port_a"] == port_index
        b_match = cable.get("b") == equip_id and cable.get("port_b") == port_index
        if a_match or b_match:
            return cable["type"] == "cable_100"
    return False


class UniversalConfigWindow(Window):
    """
    Главное окно. Собирает в себе все устройства дома.
    Обрабатывает настройки портов, создание LACP и коммутацию.
    """
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

        self.active_section_eid = (self.devices[0]["id"] if self.devices else None)
        self.popup = None

        self._section_hits = []
        self._link_hits = []
        self._desc_rects = {}
        self._speed_hits = []
        self._mode_hits = []
        self._vlan_hits = []

        self._btn_lacp = pygame.Rect(0, 0, 0, 0)
        self._btn_commut = pygame.Rect(0, 0, 0, 0)
        self._btn_save = pygame.Rect(0, 0, 0, 0)

        self._compute_content_height()

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
            if d["id"] == eid: return d
        return None

    def _sync_positions(self):
        """Пересчитывает хитбоксы (где находятся кнопки) в зависимости от прокрутки."""
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
            self._section_hits.append((pygame.Rect(cr.x, ry, cr.width, UCW_SECTION_HDR_H), equip))
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
            if ti is not None: ti.set_rect(rect)

        fx = self.x + 10
        fy = self.y + self.height - UCW_FOOTER_H + 10
        bw, bh, gap = 110, 30, 6
        self._btn_lacp = pygame.Rect(fx, fy, bw, bh)
        self._btn_commut = pygame.Rect(fx + (bw + gap), fy, bw, bh)
        self._btn_save = pygame.Rect(self.x + self.width - bw - 10, fy, bw, bh)

    def is_text_input_active(self):
        if self.popup is not None: return True
        return any(ti.active for ti in self.inputs.values())

    # --- ЛОГИКА ОКОН ---
    def _open_lacp_window(self):
        sw, sh = _screen_size()
        def on_submit(selected, gid, name, is_edit):
            if not selected: return
            eq_id = selected[0][0]
            eq = self._find_equip(eq_id)
            if not eq: return
            ports = sorted(pi for e, pi in selected if e == eq_id)
            if is_edit:
                for g in eq.get("lacp_groups", []):
                    if g["id"] == gid:
                        g["ports"] = ports
                        g["name"] = name
                        break
            else:
                g = {"id": gid, "name": name, "ports": ports, "speed": 1000,
                     "label": "", "mode": "trunk", "vlan_string": "", "admin_state": "up"}
                eq.setdefault("lacp_groups", []).append(g)
            _notify_speed_changed(self.game)
            self._build_inputs()
            self._compute_content_height()
        self.popup = LACPInputWindow(self.devices, self.game, None, on_submit, sw, sh)

        def _open_merge_window(self):
            sw, sh = _screen_size()
            def on_merge(host_id, other_ids, name, is_new, remove_board_ids):
                host = self._find_equip(host_id)
                if not host: return
                
                # 1. Отсоединяем платы (если редактировали)
                for bid in remove_board_ids:
                    if bid == 1: continue # Базовую плату 1 не трогаем
                    self.game.unmerge_equipment(host, bid)
                    
                # 2. Присоединяем новые
                for oid in other_ids:
                    other = self._find_equip(oid)
                    if other: 
                        self.game.merge_equipment(host, other)
                
                # 3. Применяем имя (сработает и для создания, и для редактирования)
                if name:
                    host["name"] = name
                    
                # 4. Обновляем UI
                self.devices = self._visible_devices(self.devices)
                self._init_fields()
                self._build_inputs()
                self._compute_content_height()
                self.active_section_eid = host["id"]
            self.popup = CommutWindow(self.devices, self.game, on_merge, sw, sh)

    def _toggle_admin_state(self, obj):
        obj["admin_state"] = "up" if obj.get("admin_state", "up") == "shut" else "shut"

    def _toggle_mode(self, obj):
        obj["mode"] = "trunk" if obj.get("mode", "access") == "access" else "access"

    def _open_vlan_popup(self, kind, equip, ref):
        sw, sh = _screen_size()
        if kind == "port":
            port = equip["ports"][ref]
            text, mode = port.get("vlan_string", ""), port.get("mode", "access")
            def cb(txt):
                port["vlan_string"] = txt
                self.popup = None
        else:
            grp = ref
            text, mode = grp.get("vlan_string", ""), grp.get("mode", "trunk")
            def cb(txt):
                grp["vlan_string"] = txt
                self.popup = None
        self.popup = VlanPopupWindow(sw, sh, text, mode, cb)

    def handle_event(self, event):
        if self.popup is not None:
            handled = self.popup.handle_event(event)
            if self.popup is not None and self.popup.is_closed: self.popup = None
            return handled or True

        # Если клик по ползунку скролла - отдаем базовому классу, чтобы он его потаскал
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            thumb = self._scrollbar_thumb()
            if thumb and thumb.collidepoint(event.pos):
                return super().handle_event(event)

        if event.type == pygame.KEYDOWN:
            for ti in self.inputs.values():
                if ti.active: return ti.handle_event(event, self._cfg_font)
            return super().handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._sync_positions()

            if self._btn_save.collidepoint(event.pos):
                self._save(); return True
            if self._btn_lacp.collidepoint(event.pos):
                self._open_lacp_window(); return True
            if self._btn_commut.collidepoint(event.pos):
                self._open_merge_window(); return True

            if self.content_rect().collidepoint(event.pos):
                for rect, equip in self._section_hits:
                    if rect.collidepoint(event.pos):
                        self.active_section_eid = equip["id"]; return True

                for rect, equip, pi, kind, ref in self._link_hits:
                    if rect.collidepoint(event.pos):
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

    def _draw_link_pill(self, screen, rect, state):
        color = COLOR_LINK_UP if state == "up" else COLOR_LINK_DOWN
        pygame.draw.rect(screen, color, rect, border_radius=18)
        pygame.draw.rect(screen, COLOR_LINK_EDGE, rect, 1, border_radius=18)
        surf = self._tiny.render(state, True, (255, 255, 255))
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
            if equip["id"] == self.active_section_eid:
                pygame.draw.rect(surface, (50, 70, 100), hdr_rect)
            title = equip_type_label(equip)
            boards_n = len(equip.get("boards", []))
            label_text = f"{title} #{equip['id']}" + (f"  [ШАССИ, плат: {boards_n}]" if boards_n > 1 else "")
            hdr = self._header_font.render(label_text, True, COLOR_TITLE)
            surface.blit(hdr, (UCW_X_PORT, ry + 10))
            y += self.row_h

            for i, port in enumerate(equip["ports"]):
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h; continue
                pname = port_name(self.game, equip, i) if self.game else f"{i + 1}"
                in_lacp = port_in_lacp(equip, i) is not None
                col = COLOR_STATUS_LACP if in_lacp else COLOR_TEXT
                num = self._cfg_font.render(pname, True, col)
                surface.blit(num, (UCW_X_PORT, ry + 15))
                y += self.row_h

            for grp in equip["lacp_groups"]:
                ry = y - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    y += self.row_h; continue
                name = self._cfg_font.render(grp["name"], True, COLOR_LACP_ROW)
                surface.blit(name, (UCW_X_PORT, ry + 10))
                members = ",".join(str(p + 1) for p in grp["ports"])
                meta = self._tiny.render(f"порты: {members}", True, COLOR_LACP_ROW)
                surface.blit(meta, (UCW_X_PORT, ry + 28))
                y += self.row_h
            y += UCW_SECTION_GAP

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
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
                self._draw_mini_button(screen, rect, "—", disabled=True); continue
            if cr.y - 30 <= rect.y <= cr.bottom:
                ti = self.inputs.get(key)
                if ti: ti.draw(screen, self._cfg_font)

        for rect, kind, equip, ref in self._speed_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "LACP", disabled=True); continue
                    self._draw_mini_button(screen, rect, speed_label(equip["ports"][ref].get("speed", 1000)))
                else:
                    self._draw_mini_button(screen, rect, speed_label(ref.get("speed", 1000)))

        for rect, kind, equip, ref in self._mode_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "LACP", disabled=True); continue
                    self._draw_mini_button(screen, rect, equip["ports"][ref].get("mode", "access"))
                else:
                    self._draw_mini_button(screen, rect, ref.get("mode", "trunk"))

        for rect, kind, equip, ref in self._vlan_hits:
            if cr.y - 30 <= rect.y <= cr.bottom:
                if kind == "port":
                    if port_in_lacp(equip, ref) is not None:
                        self._draw_mini_button(screen, rect, "—", disabled=True); continue
                    text = _vlan_preview(equip["ports"][ref].get("vlan_string", ""))
                else:
                    text = _vlan_preview(ref.get("vlan_string", ""))
                self._draw_mini_button(screen, rect, text)

        screen.set_clip(old_clip)

        footer_bg = pygame.Rect(self.x, self.y + self.height - UCW_FOOTER_H, self.width, UCW_FOOTER_H)
        pygame.draw.rect(screen, (40, 42, 50), footer_bg)
        pygame.draw.line(screen, (90, 90, 100), (footer_bg.x, footer_bg.y), (footer_bg.right, footer_bg.y), 1)

        self._draw_mini_button(screen, self._btn_lacp, "LACP")
        self._draw_mini_button(screen, self._btn_commut, "Commut")
        self._draw_mini_button(screen, self._btn_save, "Save")

        if self.popup is not None:
            self.popup.draw(screen, font, small_font)
            
            