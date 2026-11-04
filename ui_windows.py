#!/usr/bin/env python3
"""
ui_windows.py (v17) - окна ISP Simulator (Telecom INC).

НОВОЕ v17:
  - Spd Mismatch пересчитывается ДИНАМИЧЕСКИ через game.recompute_mismatch()
    после каждого изменения скорости порта/LACP.
  - Логические порты LACP отображаются в списке портов (SwitchWindow/RouterWindow)
    как отдельный пункт "LACP-N", физ.порты LACP берут имя группы как подпись.
  - LACPInputWindow: выбор портов КЛИКОМ по сетке (а не вводом цифр).

ИЗ v16:
  - Исправлен UIWindowManager (не затирает новое окно при смене).
  - HouseWindow(game); умное DCTariffWindow; speed_mismatch.
"""

import random
import pygame

COLOR_WIN_BG = (0, 0, 0, 210)
COLOR_WIN_EDGE = (150, 150, 150)
COLOR_WIN_EDGE_GLOW = (90, 180, 255)
COLOR_TITLE = (255, 255, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_TEXT_DIM = (170, 170, 170)

COLOR_BTN_TOP = (95, 95, 105)
COLOR_BTN_BOT = (60, 60, 68)
COLOR_BTN_HOVER_TOP = (120, 150, 200)
COLOR_BTN_HOVER_BOT = (70, 100, 150)
COLOR_BTN_ACTIVE_TOP = (90, 200, 110)
COLOR_BTN_ACTIVE_BOT = (45, 140, 70)
COLOR_BTN_DISABLED = (48, 48, 52)
COLOR_BTN_EDGE = (160, 160, 170)
COLOR_BTN_EDGE_HOVER = (180, 210, 255)

COLOR_CLOSE = (170, 60, 60)
COLOR_CLOSE_HOVER = (230, 80, 80)

COLOR_TITLEBAR = (55, 55, 62)
COLOR_TITLEBAR_HOVER = (78, 92, 120)
COLOR_TITLEBAR_DRAG = (95, 120, 165)

COLOR_PORT_DOWN = (200, 50, 50)
COLOR_PORT_DOWN_HI = (235, 90, 90)
COLOR_PORT_UP = (50, 200, 50)
COLOR_PORT_UP_HI = (90, 235, 90)
COLOR_PORT_ERROR = (255, 50, 50)
COLOR_PORT_ERROR_HI = (255, 90, 90)
COLOR_PORT_MISMATCH = (255, 20, 20)
COLOR_PORT_LACP = (110, 110, 120)
COLOR_PORT_LACP_SEL = (90, 160, 240)      # выбранный порт в окне создания LACP
COLOR_PORT_EDGE = (220, 220, 220)
COLOR_PORT_EDGE_HOVER = (255, 255, 255)

COLOR_INPUT_BG = (30, 30, 34)
COLOR_INPUT_EDGE = (120, 120, 130)
COLOR_INPUT_EDGE_ACTIVE = (80, 200, 100)

COLOR_SCROLLBAR_BG = (45, 45, 50)
COLOR_SCROLLBAR = (120, 120, 130)
COLOR_SCROLLBAR_HOVER = (160, 170, 190)

COLOR_STATUS_UP = (80, 220, 80)
COLOR_STATUS_DOWN = (170, 170, 170)
COLOR_STATUS_ERROR = (255, 70, 70)
COLOR_STATUS_LACP = (150, 150, 160)

COLOR_TARIFF = (200, 170, 60)
COLOR_LACP_ROW = (120, 180, 255)

HEADER_H = 40
TITLEBAR_H = 30
SCROLL_STEP = 28
FOOTER_H = 44


def speed_label(speed):
    if speed >= 10000:
        return "10G"
    if speed >= 1000:
        return "1G"
    return "100M"


def _screen_size():
    surf = pygame.display.get_surface()
    return surf.get_width(), surf.get_height()


# --------------------------------------------------------------------------
# Хелперы рисования
# --------------------------------------------------------------------------
def _vgrad_rect(surface, rect, top_color, bot_color, radius=6):
    tmp = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    h = max(1, rect.height)
    for i in range(h):
        t = i / h
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
        pygame.draw.line(tmp, (r, g, b), (0, i), (rect.width, i))
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255),
                     (0, 0, rect.width, rect.height), border_radius=radius)
    tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(tmp, (rect.x, rect.y))


def draw_fancy_button(surface, font, rect, text, state="normal", radius=6):
    if state == "disabled":
        pygame.draw.rect(surface, COLOR_BTN_DISABLED, rect, border_radius=radius)
        edge = COLOR_BTN_EDGE
        tcol = COLOR_TEXT_DIM
    else:
        if state == "active":
            top, bot = COLOR_BTN_ACTIVE_TOP, COLOR_BTN_ACTIVE_BOT
            edge = COLOR_BTN_EDGE_HOVER
        elif state == "hover":
            top, bot = COLOR_BTN_HOVER_TOP, COLOR_BTN_HOVER_BOT
            edge = COLOR_BTN_EDGE_HOVER
        else:
            top, bot = COLOR_BTN_TOP, COLOR_BTN_BOT
            edge = COLOR_BTN_EDGE
        _vgrad_rect(surface, rect, top, bot, radius)
        tcol = COLOR_TEXT
        hi = pygame.Surface((rect.width, max(1, rect.height // 2)), pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 35),
                         (0, 0, rect.width, rect.height // 2),
                         border_top_left_radius=radius, border_top_right_radius=radius)
        surface.blit(hi, (rect.x, rect.y))
    pygame.draw.rect(surface, edge, rect, 1, border_radius=radius)
    surf = font.render(text, True, tcol)
    surface.blit(surf, (rect.centerx - surf.get_width() // 2,
                        rect.centery - surf.get_height() // 2))


def draw_button_on(surface, font, rect, text, active=False, enabled=True):
    state = "disabled" if not enabled else ("active" if active else "normal")
    draw_fancy_button(surface, font, rect, text, state)


def draw_button_screen(screen, font, rect, text, active=False):
    mouse = pygame.mouse.get_pos()
    state = "active" if active else ("hover" if rect.collidepoint(mouse) else "normal")
    draw_fancy_button(screen, font, rect, text, state)


def find_cable_for_port(game, equip_id, port_index):
    if game is None:
        return None
    for cable in game.cables:
        if cable["a"] == equip_id and cable["port_a"] == port_index:
            return cable
        if cable.get("b") == equip_id and cable.get("port_b") == port_index:
            return cable
    return None


def port_in_lacp(equip, port_index):
    for grp in equip.get("lacp_groups", []):
        if port_index in grp["ports"]:
            return grp
    return None


def _notify_speed_changed(game):
    """Просит game пересчитать speed_mismatch у всех кабелей."""
    if game is not None and hasattr(game, "recompute_mismatch"):
        game.recompute_mismatch()


def toggle_port_speed(game, equip, port_index):
    port = equip["ports"][port_index]
    if port_in_lacp(equip, port_index) is not None:
        print("Порт в составе LACP — настройка скорости через логический порт")
        return
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable["type"] == "cable_100":
            print("Кабель 100Мб ограничивает скорость")
            return
        port["speed"] = 100 if port["speed"] == 1000 else 1000
        _notify_speed_changed(game)
        return
    port["speed"] = 100 if port["speed"] == 1000 else 1000
    _notify_speed_changed(game)


def toggle_lacp_speed(grp, game=None):
    grp["speed"] = 100 if grp.get("speed", 1000) == 1000 else 1000
    # синхронизируем физ.порты группы со скоростью LACP
    _notify_speed_changed(game)


def equip_type_label(equip):
    t = equip["type"]
    if t == "router":
        return "Роутер"
    n = len(equip["ports"])
    return f"Свитч {n}p"


def port_status_text_color(game, equip, port_index):
    port = equip["ports"][port_index]
    grp = port_in_lacp(equip, port_index)
    if grp is not None:
        return f"В составе {grp['name']}", COLOR_STATUS_LACP
    if port["free"]:
        return "Down", COLOR_STATUS_DOWN
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable.get("speed_mismatch"):
            return "Speed Mismatch", COLOR_PORT_MISMATCH
        if not cable.get("signal_ok", True):
            return "ОШИБКА >150м", COLOR_STATUS_ERROR
    conn = port["connection"]
    if conn:
        if conn.get("to_dc"):
            tar = conn.get("tariff", "ЦОД")
            return f"Магистраль [{tar}]", COLOR_TARIFF
        return f"Up #{conn['to_id']}:{conn['to_port'] + 1}", COLOR_STATUS_UP
    return "Up", COLOR_STATUS_UP


def port_fill_color(game, equip, port_index, hover=False):
    port = equip["ports"][port_index]
    if port_in_lacp(equip, port_index) is not None:
        return COLOR_PORT_LACP
    if port["free"]:
        return COLOR_PORT_DOWN_HI if hover else COLOR_PORT_DOWN
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable.get("speed_mismatch"):
            return COLOR_PORT_MISMATCH
        if not cable.get("signal_ok", True):
            return COLOR_PORT_ERROR_HI if hover else COLOR_PORT_ERROR
    return COLOR_PORT_UP_HI if hover else COLOR_PORT_UP


def lacp_effective_label(equip, port_index):
    """Подпись физ.порта: если в LACP — имя группы, иначе своя подпись."""
    grp = port_in_lacp(equip, port_index)
    if grp is not None:
        return grp["name"]
    return equip["ports"][port_index].get("label", "")

# --------------------------------------------------------------------------
# Поле ввода текста (с курсором)
# --------------------------------------------------------------------------
class TextInput:
    def __init__(self, rect, initial_text="", max_length=15):
        self.rect = pygame.Rect(rect)
        self.text = initial_text
        self.active = False
        self.max_length = max_length
        self.cursor_pos = len(initial_text)
        self._cursor_timer = 0

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def _cursor_from_x(self, font, mouse_x):
        rel_x = mouse_x - (self.rect.x + 5)
        if rel_x <= 0:
            return 0
        for i in range(len(self.text)):
            w1 = font.size(self.text[:i])[0]
            w2 = font.size(self.text[:i + 1])[0]
            if w1 <= rel_x <= w2:
                return i if (rel_x - w1) < (w2 - rel_x) else i + 1
        return len(self.text)

    def handle_event(self, event, font=None):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True
                self._cursor_timer = 0
                if font is not None:
                    self.cursor_pos = self._cursor_from_x(font, event.pos[0])
                else:
                    self.cursor_pos = len(self.text)
                return True
            else:
                self.active = False
                return False

        if event.type == pygame.KEYDOWN and self.active:
            k = event.key
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False
                return True
            if k == pygame.K_ESCAPE:
                self.active = False
                return True
            if k == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
                self._cursor_timer = 0
                return True
            if k == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                self._cursor_timer = 0
                return True
            if k == pygame.K_HOME:
                self.cursor_pos = 0
                self._cursor_timer = 0
                return True
            if k == pygame.K_END:
                self.cursor_pos = len(self.text)
                self._cursor_timer = 0
                return True
            if k == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                self._cursor_timer = 0
                return True
            if k == pygame.K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                self._cursor_timer = 0
                return True
            ch = event.unicode
            if ch and ch.isprintable() and len(self.text) < self.max_length:
                self.text = self.text[:self.cursor_pos] + ch + self.text[self.cursor_pos:]
                self.cursor_pos += 1
                self._cursor_timer = 0
            return True

        return False

    def draw(self, surface, font):
        pygame.draw.rect(surface, COLOR_INPUT_BG, self.rect, border_radius=4)
        edge = COLOR_INPUT_EDGE_ACTIVE if self.active else COLOR_INPUT_EDGE
        pygame.draw.rect(surface, edge, self.rect, 1, border_radius=4)
        txt = font.render(self.text, True, COLOR_TEXT)
        surface.blit(txt, (self.rect.x + 5,
                          self.rect.centery - txt.get_height() // 2))
        if self.active:
            self._cursor_timer = (self._cursor_timer + 1) % 60
            if self._cursor_timer < 30:
                cx = self.rect.x + 5 + font.size(self.text[:self.cursor_pos])[0]
                pygame.draw.line(surface, COLOR_TEXT,
                               (cx, self.rect.y + 4),
                               (cx, self.rect.bottom - 4), 1)


# --------------------------------------------------------------------------
# Базовый класс окна
# --------------------------------------------------------------------------
class Window:
    def __init__(self, x, y, width, height, title):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title
        self.is_closed = False
        self.scroll_y = 0
        self.content_height = 0
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def close_rect(self):
        return pygame.Rect(self.x + self.width - 28, self.y + 8, 20, 20)

    def titlebar_rect(self):
        return pygame.Rect(self.x, self.y, self.width, TITLEBAR_H)

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H)

    def contains(self, mouse_pos):
        return self.rect().collidepoint(mouse_pos)

    def close(self):
        self.is_closed = True

    def max_scroll(self):
        visible = self.content_rect().height
        return max(0, self.content_height - visible)

    def scroll(self, direction):
        self.scroll_y -= direction * SCROLL_STEP
        self.scroll_y = max(0, min(self.scroll_y, self.max_scroll()))

    def _clamp_to_screen(self):
        sw, sh = _screen_size()
        self.x = max(0, min(self.x, sw - self.width))
        self.y = max(0, min(self.y, sh - self.height))

    def is_text_input_active(self):
        return False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.dragging:
            mx, my = event.pos
            self.x = mx - self.drag_offset_x
            self.y = my - self.drag_offset_y
            self._clamp_to_screen()
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            if self.contains(event.pos):
                if self.content_rect().collidepoint(event.pos):
                    self._on_content_click(event.pos[0], event.pos[1] + self.scroll_y)
                return True
            self.close()
            return True
        return False

    def _on_content_click(self, local_x, local_y):
        pass

    def _draw_frame(self, screen, font):
        panel = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, COLOR_WIN_BG, (0, 0, self.width, self.height),
                         border_radius=12)
        screen.blit(panel, (self.x, self.y))

        glow = pygame.Surface((self.width + 12, self.height + 12), pygame.SRCALPHA)
        for i, a in enumerate((30, 20, 12)):
            pygame.draw.rect(glow, (*COLOR_WIN_EDGE_GLOW, a),
                             (6 - i * 2, 6 - i * 2,
                              self.width + i * 4, self.height + i * 4),
                             2, border_radius=14)
        screen.blit(glow, (self.x - 6, self.y - 6))

        pygame.draw.rect(screen, COLOR_WIN_EDGE, self.rect(), 2, border_radius=12)

        mouse = pygame.mouse.get_pos()
        if self.dragging:
            bar_top, bar_bot = COLOR_TITLEBAR_DRAG, COLOR_TITLEBAR
        elif self.titlebar_rect().collidepoint(mouse):
            bar_top, bar_bot = COLOR_TITLEBAR_HOVER, COLOR_TITLEBAR
        else:
            bar_top, bar_bot = COLOR_TITLEBAR, (42, 42, 48)
        bar = pygame.Rect(self.x + 1, self.y + 1, self.width - 2, TITLEBAR_H)
        _vgrad_rect(screen, bar, bar_top, bar_bot, radius=11)

        for i in range(3):
            pygame.draw.circle(screen, (200, 200, 210),
                               (self.x + 10, self.y + 11 + i * 5), 1)

        title_surf = font.render(self.title, True, COLOR_TITLE)
        screen.blit(title_surf, (self.x + 22, self.y + 6))

        cr = self.close_rect()
        cc = COLOR_CLOSE_HOVER if cr.collidepoint(mouse) else COLOR_CLOSE
        pygame.draw.rect(screen, cc, cr, border_radius=5)
        cx, cy = cr.center
        pygame.draw.line(screen, (255, 255, 255), (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(screen, (255, 255, 255), (cx - 5, cy + 5), (cx + 5, cy - 5), 2)

    def _draw_scrollbar(self, screen):
        visible = self.content_rect().height
        if self.content_height <= visible:
            return
        track = pygame.Rect(self.x + self.width - 9, self.y + HEADER_H,
                           6, visible - 6)
        pygame.draw.rect(screen, COLOR_SCROLLBAR_BG, track, border_radius=3)
        frac = visible / self.content_height
        thumb_h = max(20, int(track.height * frac))
        max_s = self.max_scroll()
        pos_frac = (self.scroll_y / max_s) if max_s > 0 else 0
        thumb_y = track.y + int((track.height - thumb_h) * pos_frac)
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        mouse = pygame.mouse.get_pos()
        col = COLOR_SCROLLBAR_HOVER if thumb.collidepoint(mouse) else COLOR_SCROLLBAR
        pygame.draw.rect(screen, col, thumb, border_radius=3)

    def _draw_content(self, screen, font, small_font):
        cr = self.content_rect()
        content_surf = pygame.Surface((cr.width, cr.height), pygame.SRCALPHA)
        self._render_content(content_surf, font, small_font)
        screen.blit(content_surf, (cr.x, cr.y))
        self._draw_scrollbar(screen)

    def _render_content(self, surface, font, small_font):
        pass

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)


# --------------------------------------------------------------------------
# Окно информации о доме
# --------------------------------------------------------------------------
class HouseWindow(Window):
    def __init__(self, house, screen_w, screen_h, game=None):
        w, h = 350, 250
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"Дом #{house['id']}")
        self.house = house
        self.game = game
        self._equip_btn = pygame.Rect(0, 0, 0, 0)

    def _house_loc(self):
        return (self.house["x"] + self.house["width"] // 2,
                self.house["y"] + self.house["height"] // 2)

    def _house_devices(self):
        if self.game is None:
            return []
        return self.game.equipment_at.get(self._house_loc(), [])

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._equip_btn.collidepoint(event.pos):
                self._open_equipment()
                return True
        return super().handle_event(event)

    def _open_equipment(self):
        if self.game is None:
            return
        loc = self._house_loc()
        devices = self.game.equipment_at.get(loc, [])
        if not devices:
            print(f"В доме #{self.house['id']} нет оборудования")
            return
        switches = [d for d in devices if d["type"] in ("switch_12", "switch_24")]
        routers = [d for d in devices if d["type"] == "router"]
        self.close()
        if switches:
            self.game.ui_manager.open_switch(switches)
        elif routers:
            self.game.ui_manager.open_router(routers)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        x = self.x + 18
        y = self.y + HEADER_H + 16
        floors = self.house.get("floors", "?")
        clients = self.house.get("clients", "?")
        devices = self._house_devices()
        lines = [
            (f"Этажей: {floors}", COLOR_TEXT),
            (f"Жителей: {clients}", COLOR_TEXT),
            (f"Оборудования: {len(devices)}",
             COLOR_STATUS_UP if devices else COLOR_TEXT_DIM),
        ]
        for text, col in lines:
            surf = font.render(text, True, col)
            screen.blit(surf, (x, y))
            y += 34
        self._equip_btn = pygame.Rect(self.x + self.width // 2 - 90,
                                      self.y + self.height - FOOTER_H + 2, 180, 34)
        mouse = pygame.mouse.get_pos()
        if not devices:
            draw_fancy_button(screen, small_font, self._equip_btn,
                              "Нет оборудования", state="disabled")
        else:
            state = "hover" if self._equip_btn.collidepoint(mouse) else "normal"
            draw_fancy_button(screen, small_font, self._equip_btn,
                              "⚙ Оборудование", state=state)


# --------------------------------------------------------------------------
# Главное окно свитчей (с отдельными блоками LACP-N в списке)
# --------------------------------------------------------------------------
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
        # блоки LACP: заголовок + ряд иконок членов
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
        # физические порты
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
        # блоки LACP
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
        # подпись: имя LACP-группы (если в ней) или своя подпись
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
        """Собирает хит-боксы физических портов (для клика по скорости)."""
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
        self._hit_ports = []   # перезаполняется ниже (для рисования), но клики через _layout
        y = 10
        for equip in self.equipment_list:
            y = self._render_equip(surface, equip, y, tiny, small_font, cr, mouse)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._config_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                       self.y + self.height - FOOTER_H + 6, 140, 30)
        draw_button_screen(screen, small_font, self._config_btn, "⚙ Config")


# --------------------------------------------------------------------------
# Главное окно роутеров (список строк, + строки LACP)
# --------------------------------------------------------------------------
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
        # физ.порты + строки LACP
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
                # кнопка скорости только для портов НЕ в LACP
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
            # физические порты
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
            # строки LACP-групп
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
        
        # --------------------------------------------------------------------------
# Окно конфигурации (колонки, ширина 480, + LACP логические порты)
# --------------------------------------------------------------------------
COL_NUM = 10
COL_STATUS = 50
COL_INPUT = 180
COL_INPUT_W = 150
COL_SPEED = 350
COL_SPEED_W = 100
ROW_H_CFG = 40


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
        self.inputs = []          # (port_index, TextInput) физ.портов
        self.lacp_inputs = []     # (group, TextInput) логических портов
        self._speed_buttons = []  # (rect, kind, ref)
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
                        # поля ввода физ.портов, входящих в LACP, не активны
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
        """Можно ли добавить порт в LACP: не в другой группе."""
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


# --------------------------------------------------------------------------
# Мини-окно создания LACP — ВЫБОР ПОРТОВ КЛИКОМ ПО СЕТКЕ
# --------------------------------------------------------------------------
class LACPInputWindow(Window):
    def __init__(self, callback, screen_w, screen_h, equip, is_selectable):
        self.equip = equip
        self.is_selectable = is_selectable      # func(port_index) -> bool
        n = len(equip["ports"])
        self.cols = 6
        self.box = 40
        self.gap = 8
        rows = (n + self.cols - 1) // self.cols
        grid_h = rows * (self.box + self.gap)
        w = 60 + self.cols * (self.box + self.gap)
        h = HEADER_H + 40 + grid_h + 60
        w = max(w, 360)
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "LACP: выбери порты кликом")
        self.callback = callback
        self.selected = set()
        self._cells = []        # (rect, port_index)
        self._ok_btn = pygame.Rect(0, 0, 0, 0)
        self._cancel_btn = pygame.Rect(0, 0, 0, 0)
        self._tiny = pygame.font.SysFont("arial,dejavusans", 12)

    def is_text_input_active(self):
        return False

    def _layout(self):
        self._cells = []
        start_x = self.x + 30
        start_y = self.y + HEADER_H + 34
        for i in range(len(self.equip["ports"])):
            c = i % self.cols
            r = i // self.cols
            px = start_x + c * (self.box + self.gap)
            py = start_y + r * (self.box + self.gap)
            self._cells.append((pygame.Rect(px, py, self.box, self.box), i))
        by = self.y + self.height - 44
        self._ok_btn = pygame.Rect(self.x + 20, by, 140, 32)
        self._cancel_btn = pygame.Rect(self.x + self.width - 160, by, 140, 32)

    def _submit(self):
        cb = self.callback
        sel = set(self.selected)
        self.close()
        cb(sel)

    def handle_event(self, event):
        self._layout()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit()
                return True
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect().collidepoint(event.pos):
                self.close()
                return True
            if self._ok_btn.collidepoint(event.pos):
                self._submit()
                return True
            if self._cancel_btn.collidepoint(event.pos):
                self.close()
                return True
            if self.titlebar_rect().collidepoint(event.pos):
                self.dragging = True
                self.drag_offset_x = event.pos[0] - self.x
                self.drag_offset_y = event.pos[1] - self.y
                return True
            # клик по ячейке порта — переключаем выбор
            for rect, i in self._cells:
                if rect.collidepoint(event.pos):
                    if not self.is_selectable(i):
                        print(f"Порт {i + 1} уже занят LACP-группой")
                        return True
                    if i in self.selected:
                        self.selected.discard(i)
                    else:
                        self.selected.add(i)
                    return True
            return True   # модальное
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        mouse = pygame.mouse.get_pos()
        hint = small_font.render(f"Выбрано: {len(self.selected)} (мин. 2)",
                                 True, COLOR_TEXT)
        screen.blit(hint, (self.x + 30, self.y + HEADER_H + 8))
        for rect, i in self._cells:
            selectable = self.is_selectable(i)
            hover = rect.collidepoint(mouse)
            if not selectable:
                base = COLOR_PORT_LACP           # уже в другой LACP — серый
            elif i in self.selected:
                base = COLOR_PORT_LACP_SEL       # выбран — синий
            else:
                base = (70, 120, 70) if not hover else (90, 150, 90)
            _vgrad_rect(screen, rect,
                        tuple(min(255, c + 30) for c in base), base, radius=6)
            edge = (255, 255, 255) if (i in self.selected) else COLOR_PORT_EDGE
            pygame.draw.rect(screen, edge, rect, 2 if (hover or i in self.selected) else 1,
                             border_radius=6)
            num = small_font.render(str(i + 1), True, COLOR_TEXT)
            screen.blit(num, (rect.centerx - num.get_width() // 2,
                              rect.centery - num.get_height() // 2))
        draw_button_screen(screen, small_font, self._ok_btn,
                           f"✔ Создать ({len(self.selected)})")
        draw_button_screen(screen, small_font, self._cancel_btn, "Отмена")
        
        
        # --------------------------------------------------------------------------
# Окно ЦОД (инфо)
# --------------------------------------------------------------------------
class DatacenterWindow(Window):
    def __init__(self, dc, screen_w, screen_h):
        w, h = 300, 180
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"ЦОД: {dc.get('name', 'DC')}")
        self.dc = dc

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        lbl = small_font.render("Магистральный узел конкурента.", True, COLOR_TEXT)
        screen.blit(lbl, (self.x + 14, self.y + HEADER_H + 20))
        note = small_font.render("Подключите роутер кабелем к ЦОД,", True, COLOR_TEXT_DIM)
        screen.blit(note, (self.x + 14, self.y + HEADER_H + 50))
        note2 = small_font.render("чтобы выбрать тариф аплинка.", True, COLOR_TEXT_DIM)
        screen.blit(note2, (self.x + 14, self.y + HEADER_H + 75))


# --------------------------------------------------------------------------
# Умное окно выбора тарифа ЦОД
# --------------------------------------------------------------------------
class DCTariffWindow(Window):
    TARIFFS = [
        ("Тариф Эконом", 100, 1),
        ("Тариф Стандарт", 1000, 4),
        ("Тариф Премиум", 10000, 16),
    ]

    def __init__(self, callback, screen_w, screen_h, existing_tariff=None):
        w, h = 400, 340
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, "Подключение к ЦОД")
        self.callback = callback
        self.existing = existing_tariff   # (name, speed, ips) или None
        self._buttons = []

    def _layout(self):
        self._buttons = []
        bw, bh = self.width - 60, 42
        bx = self.x + 30
        by = self.y + HEADER_H + 30
        if self.existing is not None:
            name, speed, ips = self.existing
            rect = pygame.Rect(bx, by, bw, bh)
            self._buttons.append((rect, f"Использовать текущий: {name}",
                                  speed, ips, True))
            by += bh + 14
        for (label, speed, ips) in self.TARIFFS:
            rect = pygame.Rect(bx, by, bw, bh)
            full = f"{label} ({speed_label(speed)}, {ips} IP)"
            self._buttons.append((rect, full, speed, ips, False))
            by += bh + 12

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.dragging:
            return super().handle_event(event)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            return super().handle_event(event)

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
            for rect, label, speed, ips, is_existing in self._buttons:
                if rect.collidepoint(event.pos):
                    cb = self.callback
                    name = label.replace("Использовать текущий: ", "")
                    name = name.split(" (")[0]
                    self.close()
                    print(f"Выбран тариф: {name} "
                          f"({speed_label(speed)}, {ips} IP)"
                          f"{' [повтор]' if is_existing else ''}")
                    cb(speed, name, ips)
                    return True
            if self.contains(event.pos):
                return True
            self.close()
            return True
        return super().handle_event(event)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._layout()
        mouse = pygame.mouse.get_pos()
        hint = small_font.render("Выберите тариф магистрали:", True, COLOR_TEXT_DIM)
        screen.blit(hint, (self.x + 30, self.y + HEADER_H + 6))
        for rect, label, speed, ips, is_existing in self._buttons:
            hover = rect.collidepoint(mouse)
            if is_existing:
                top = (90, 180, 120) if hover else (60, 130, 85)
                bot = (60, 130, 85) if hover else (40, 90, 60)
                edge = (150, 255, 180) if hover else (90, 180, 120)
                tcol = (240, 255, 245)
            else:
                top = (210, 180, 70) if hover else (160, 135, 55)
                bot = (150, 120, 45) if hover else (110, 90, 35)
                edge = (255, 230, 150) if hover else (200, 170, 90)
                tcol = (30, 25, 10)
            _vgrad_rect(screen, rect, top, bot, radius=8)
            pygame.draw.rect(screen, edge, rect, 2 if hover else 1, border_radius=8)
            txt = small_font.render(label, True, tcol)
            screen.blit(txt, (rect.centerx - txt.get_width() // 2,
                              rect.centery - txt.get_height() // 2))


# --------------------------------------------------------------------------
# Окно выбора порта для кабеля (список устройств + прокрутка)
# --------------------------------------------------------------------------
class PortSelectWindow(Window):
    def __init__(self, devices_list, is_second_click, callback, screen_w, screen_h):
        w, h = 300, 400
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.devices_list = devices_list
        self.is_second_click = is_second_click
        self.callback = callback
        title = "Выбор порта (цель)" if is_second_click else "Выбор порта (старт)"
        super().__init__(x, y, w, h, title)
        self.cols = 4
        self.box = 40
        self.gap = 10
        self.header_gap = 26
        self.block_gap = 16
        self._hit_ports = []
        self._compute_content_height()

    def _free_ports(self, device):
        # порты в LACP недоступны для прямого подключения кабелем
        return [i for i, p in enumerate(device["ports"])
                if p["free"] and port_in_lacp(device, i) is None]

    def _compute_content_height(self):
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            y += self.header_gap
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap
        self.content_height = y + 8

    def _layout(self):
        self._hit_ports = []
        start_x = 12
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            y += self.header_gap
            for idx, port_index in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap)
                self._hit_ports.append((pygame.Rect(px, py, self.box, self.box),
                                       device, port_index))
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        content_x = local_x - cr.x
        content_y = local_y - cr.y
        self._layout()
        for rect, device, port_index in self._hit_ports:
            if rect.collidepoint(content_x, content_y):
                cb = self.callback
                self.close()
                cb(device, port_index)
                return

    def _render_content(self, surface, font, small_font):
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        start_x = 12
        y = 8
        for device in self.devices_list:
            free = self._free_ports(device)
            if not free:
                continue
            hdr = small_font.render(f"{equip_type_label(device)} #{device['id']}",
                                    True, COLOR_TITLE)
            surface.blit(hdr, (start_x, y - self.scroll_y + 4))
            y += self.header_gap
            for idx, port_index in enumerate(free):
                c = idx % self.cols
                r = idx // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap) - self.scroll_y
                if py + self.box < 0 or py > surface.get_height():
                    continue
                prect = pygame.Rect(px, py, self.box, self.box)
                hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                draw_fancy_button(surface, tiny, prect, str(port_index + 1),
                                  state="hover" if hover else "normal")
            rows = (len(free) + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap) + self.block_gap


# --------------------------------------------------------------------------
# Менеджер окон
# --------------------------------------------------------------------------
class UIWindowManager:
    def __init__(self, game):
        self.game = game
        self.active_window = None

    def _screen_size(self):
        surf = pygame.display.get_surface()
        return surf.get_width(), surf.get_height()

    def open_house(self, house):
        if house is None:
            return
        sw, sh = self._screen_size()
        self.active_window = HouseWindow(house, sw, sh, game=self.game)

    def open_switch(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self.active_window = SwitchWindow(equipment_list, sw, sh,
                                         game=self.game, manager=self)

    def open_router(self, equipment_list):
        if not equipment_list:
            return
        sw, sh = self._screen_size()
        self.active_window = RouterWindow(equipment_list, sw, sh,
                                         game=self.game, manager=self)

    def open_switch_config(self, equip):
        sw, sh = self._screen_size()
        self.active_window = SwitchConfigWindow(equip, sw, sh, game=self.game)

    def open_router_config(self, equip):
        sw, sh = self._screen_size()
        self.active_window = RouterConfigWindow(equip, sw, sh, game=self.game)

    def open_datacenter(self, dc):
        sw, sh = self._screen_size()
        self.active_window = DatacenterWindow(dc, sw, sh)

    def open_dc_tariff_selection(self, callback, existing_tariff=None):
        sw, sh = self._screen_size()
        self.active_window = DCTariffWindow(callback, sw, sh,
                                            existing_tariff=existing_tariff)

    def open_port_selection(self, devices_list, is_second_click, callback):
        if not devices_list:
            return
        sw, sh = self._screen_size()
        self.active_window = PortSelectWindow(devices_list, is_second_click,
                                             callback, sw, sh)

    def close_active(self):
        if self.active_window is not None:
            self.active_window.close()
            self.active_window = None

    def has_active(self):
        return self.active_window is not None and not self.active_window.is_closed

    def is_port_selection_active(self):
        return (isinstance(self.active_window, PortSelectWindow)
                and not self.active_window.is_closed)

    def is_text_input_active(self):
        return (self.active_window is not None
                and not self.active_window.is_closed
                and self.active_window.is_text_input_active())

    def handle_event(self, event):
        if self.active_window is None:
            return False
        if self.active_window.is_closed:
            self.active_window = None
            return False

        win = self.active_window

        if event.type == pygame.MOUSEMOTION and win.dragging:
            handled = win.handle_event(event)
            if self.active_window is win and win.is_closed:
                self.active_window = None
            return handled

        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if win.contains(mouse):
                win.scroll(event.y)
                return True
            return False

        handled = win.handle_event(event)
        # не затираем новое окно, если старое закрылось в процессе обработки
        if self.active_window is win and win.is_closed:
            self.active_window = None
        return handled

    def draw(self, screen, font, small_font):
        if self.active_window is not None and not self.active_window.is_closed:
            self.active_window.draw(screen, font, small_font)
            
            