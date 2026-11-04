#!/usr/bin/env python3
"""
ui_windows.py - окна настройки оборудования для ISP Simulator.

НОВОЕ:
  - TextInput: поле ввода текста (подписи портов).
  - SwitchConfigWindow / RouterConfigWindow: конфиг со списком портов,
    подписями (label), статусом сигнала и скоростью.
  - Цвета портов учитывают signal_ok (ошибка >150м — ярко-красный).
  - Маршрутизация клавиатуры (is_text_input_active).
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

COLOR_PORT_DOWN = (200, 50, 50)          # свободен
COLOR_PORT_DOWN_HI = (235, 90, 90)
COLOR_PORT_UP = (50, 200, 50)            # занят, сигнал ok
COLOR_PORT_UP_HI = (90, 235, 90)
COLOR_PORT_ERROR = (255, 50, 50)         # занят, но сигнал потерян (>150м)
COLOR_PORT_ERROR_HI = (255, 90, 90)
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

HEADER_H = 40
TITLEBAR_H = 30
SCROLL_STEP = 28
FOOTER_H = 44           # нижняя панель для кнопок Config/Сохранить


def speed_label(speed):
    return "1G" if speed == 1000 else "100M"


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
        if cable["b"] == equip_id and cable["port_b"] == port_index:
            return cable
    return None


def toggle_port_speed(game, equip, port_index):
    port = equip["ports"][port_index]
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable["type"] == "cable_100":
            print("Кабель 100Мб ограничивает скорость")
            return
        port["speed"] = 100 if port["speed"] == 1000 else 1000
        return
    port["speed"] = 100 if port["speed"] == 1000 else 1000


def equip_type_label(equip):
    t = equip["type"]
    if t == "router":
        return "Роутер"
    n = len(equip["ports"])
    return f"Свитч {n}p"


def port_status_text_color(game, equip, port_index):
    """Возвращает (текст_статуса, цвет) для порта."""
    port = equip["ports"][port_index]
    if port["free"]:
        return "Down", COLOR_STATUS_DOWN
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None and not cable.get("signal_ok", True):
        return "ОШИБКА >150м", COLOR_STATUS_ERROR
    conn = port["connection"]
    if conn:
        return f"Up → #{conn['to_id']}:{conn['to_port'] + 1}", COLOR_STATUS_UP
    return "Up", COLOR_STATUS_UP


def port_fill_color(game, equip, port_index, hover=False):
    """Цвет заливки порта с учётом signal_ok."""
    port = equip["ports"][port_index]
    if port["free"]:
        return COLOR_PORT_DOWN_HI if hover else COLOR_PORT_DOWN
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None and not cable.get("signal_ok", True):
        return COLOR_PORT_ERROR_HI if hover else COLOR_PORT_ERROR
    return COLOR_PORT_UP_HI if hover else COLOR_PORT_UP


# --------------------------------------------------------------------------
# Поле ввода текста
# --------------------------------------------------------------------------
class TextInput:
    def __init__(self, rect, initial_text="", max_length=15):
        self.rect = pygame.Rect(rect)
        self.text = initial_text
        self.active = False
        self.max_length = max_length
        self._cursor_timer = 0

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def handle_event(self, event):
        """Возвращает True, если событие поглощено."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True
                return True
            else:
                self.active = False
                return False

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                self.active = False
                return True
            if event.key == pygame.K_ESCAPE:
                # снимаем фокус, но событие поглощаем (не закрывать окно)
                self.active = False
                return True
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            # обычные символы
            ch = event.unicode
            if ch and ch.isprintable() and len(self.text) < self.max_length:
                self.text += ch
            return True

        return False

    def draw(self, surface, font):
        pygame.draw.rect(surface, COLOR_INPUT_BG, self.rect, border_radius=4)
        edge = COLOR_INPUT_EDGE_ACTIVE if self.active else COLOR_INPUT_EDGE
        pygame.draw.rect(surface, edge, self.rect, 1, border_radius=4)
        txt = font.render(self.text, True, COLOR_TEXT)
        surface.blit(txt, (self.rect.x + 5,
                          self.rect.centery - txt.get_height() // 2))
        # мигающий курсор
        if self.active:
            self._cursor_timer = (self._cursor_timer + 1) % 60
            if self._cursor_timer < 30:
                cx = self.rect.x + 5 + txt.get_width() + 1
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
        visible = self.height - HEADER_H
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
                    local_x = event.pos[0]
                    local_y = event.pos[1] + self.scroll_y
                    self._on_content_click(local_x, local_y)
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
        if self.content_height <= self.height - HEADER_H:
            return
        track = pygame.Rect(self.x + self.width - 9, self.y + HEADER_H,
                           6, self.height - HEADER_H - 6)
        pygame.draw.rect(screen, COLOR_SCROLLBAR_BG, track, border_radius=3)
        visible = self.height - HEADER_H
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
# Главное окно свитчей
# --------------------------------------------------------------------------
class SwitchWindow(Window):
    def __init__(self, equipment_list, screen_w, screen_h, game=None, manager=None):
        w, h = 360, 460
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
        self.block_gap = 24
        self._hit_ports = []
        self._config_btn = pygame.Rect(0, 0, 0, 0)
        self._compute_content_height()

    def content_rect(self):
        # оставляем место под футер с кнопкой Config
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _compute_content_height(self):
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            n = len(equip["ports"])
            rows = (n + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap + 14) + self.block_gap  # +14 под label
        self.content_height = y + 10

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
            y += rows * (self.box + self.gap + 14) + self.block_gap

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
        # кнопка Config в футере обрабатывается до базового клика
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._config_btn.collidepoint(event.pos):
                if self.manager is not None:
                    self.manager.open_switch_config(self.equipment_list[0])
                return True
        return super().handle_event(event)

    def _render_content(self, surface, font, small_font):
        self._layout()
        tiny = pygame.font.SysFont("arial,dejavusans", 11)
        start_x = 14
        y = 10
        cr = self.content_rect()
        mouse = pygame.mouse.get_pos()
        for equip in self.equipment_list:
            hdr = small_font.render(f"Свитч {len(equip['ports'])}p #{equip['id']}",
                                    True, COLOR_TITLE)
            surface.blit(hdr, (start_x, y - self.scroll_y + 6))
            y += self.header_gap
            for i, port in enumerate(equip["ports"]):
                c = i % self.cols
                r = i // self.cols
                px = start_x + c * (self.box + self.gap)
                py = y + r * (self.box + self.gap + 14) - self.scroll_y
                if py + self.box + 14 < 0 or py > surface.get_height():
                    continue
                prect = pygame.Rect(px, py, self.box, self.box)
                hover = prect.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                base = port_fill_color(self.game, equip, i, hover)
                _vgrad_rect(surface, prect,
                            tuple(min(255, cc + 30) for cc in base), base, radius=6)
                edge = COLOR_PORT_EDGE_HOVER if hover else COLOR_PORT_EDGE
                pygame.draw.rect(surface, edge, prect, 2 if hover else 1, border_radius=6)
                num = small_font.render(str(i + 1), True, COLOR_TEXT)
                surface.blit(num, (px + 4, py + 3))
                sp = tiny.render(speed_label(port["speed"]), True, COLOR_TEXT)
                surface.blit(sp, (px + self.box // 2 - sp.get_width() // 2, py + self.box - 15))
                # подпись
                if port.get("label"):
                    lbl = tiny.render(port["label"], True, (200, 220, 255))
                    surface.blit(lbl, (px + self.box // 2 - lbl.get_width() // 2,
                                      py + self.box + 1))
            n = len(equip["ports"])
            rows = (n + self.cols - 1) // self.cols
            y += rows * (self.box + self.gap + 14) + self.block_gap

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        # футер с кнопкой Config
        self._config_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                       self.y + self.height - FOOTER_H + 6,
                                       140, 30)
        draw_button_screen(screen, small_font, self._config_btn, "⚙ Config")


# --------------------------------------------------------------------------
# Главное окно роутеров
# --------------------------------------------------------------------------
class RouterWindow(Window):
    def __init__(self, equipment_list, screen_w, screen_h, game=None, manager=None):
        w, h = 380, 320
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equipment_list = equipment_list
        self.game = game
        self.manager = manager
        n = len(equipment_list)
        title = f"Роутеры в доме ({n} шт.)" if n > 1 else f"Роутер #{equipment_list[0]['id']}"
        super().__init__(x, y, w, h, title)
        self.row_h = 42
        self.header_gap = 28
        self.block_gap = 16
        self._hit_buttons = []
        self._config_btn = pygame.Rect(0, 0, 0, 0)
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _compute_content_height(self):
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            y += len(equip["ports"]) * self.row_h + self.block_gap
        self.content_height = y + 10

    def _layout(self):
        self._hit_buttons = []
        y = 10
        for equip in self.equipment_list:
            y += self.header_gap
            for i, _ in enumerate(equip["ports"]):
                ry = y + i * self.row_h
                self._hit_buttons.append((pygame.Rect(230, ry, 110, 28), equip, i))
            y += len(equip["ports"]) * self.row_h + self.block_gap

    def _on_content_click(self, local_x, local_y):
        cr = self.content_rect()
        content_x = local_x - cr.x
        content_y = local_y - cr.y
        self._layout()
        for rect, equip, i in self._hit_buttons:
            if rect.collidepoint(content_x, content_y):
                toggle_port_speed(self.game, equip, i)
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
            for i, port in enumerate(equip["ports"]):
                ry = y + i * self.row_h - self.scroll_y
                if ry + self.row_h < 0 or ry > surface.get_height():
                    continue
                color = port_fill_color(self.game, equip, i)
                ind = pygame.Rect(14, ry, 20, 20)
                _vgrad_rect(surface, ind,
                            tuple(min(255, c + 30) for c in color), color, radius=4)
                pygame.draw.rect(surface, COLOR_PORT_EDGE, ind, 1, border_radius=4)
                status, col = port_status_text_color(self.game, equip, i)
                lbl_part = f"  [{port['label']}]" if port.get("label") else ""
                label = small_font.render(f"Порт {i + 1}: {status}{lbl_part}", True, col)
                surface.blit(label, (42, ry + 2))
                btn = pygame.Rect(230, ry, 110, 28)
                hover = btn.collidepoint(mouse[0] - cr.x, mouse[1] - cr.y)
                draw_fancy_button(surface, small_font, btn,
                                  f"Скорость: {speed_label(port['speed'])}",
                                  state="hover" if hover else "normal")
            y += len(equip["ports"]) * self.row_h + self.block_gap

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._config_btn = pygame.Rect(self.x + self.width // 2 - 70,
                                       self.y + self.height - FOOTER_H + 6,
                                       140, 30)
        draw_button_screen(screen, small_font, self._config_btn, "⚙ Config")


# --------------------------------------------------------------------------
# Окно конфигурации свитча (с подписями портов)
# --------------------------------------------------------------------------
class SwitchConfigWindow(Window):
    def __init__(self, equip, screen_w, screen_h, game=None):
        w, h = 400, 500
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.equip = equip
        self.game = game
        super().__init__(x, y, w, h,
                         f"Config: {equip_type_label(equip)} #{equip['id']}")
        self.row_h = 40
        self.inputs = []       # (port_index, TextInput)
        self._speed_buttons = []  # (rect_в_контенте, port_index)
        self._save_btn = pygame.Rect(0, 0, 0, 0)
        self._build_inputs()
        self._compute_content_height()

    def content_rect(self):
        return pygame.Rect(self.x, self.y + HEADER_H,
                           self.width, self.height - HEADER_H - FOOTER_H)

    def _build_inputs(self):
        self.inputs = []
        for i, port in enumerate(self.equip["ports"]):
            ti = TextInput((0, 0, 150, 26), initial_text=port.get("label", ""),
                           max_length=15)
            self.inputs.append((i, ti))

    def _compute_content_height(self):
        self.content_height = 10 + len(self.equip["ports"]) * self.row_h + 10

    def _row_y(self, i):
        """Y строки порта в системе контента (без scroll)."""
        return 10 + i * self.row_h

    def is_text_input_active(self):
        return any(ti.active for _, ti in self.inputs)

    def _sync_positions(self):
        """Обновляет rect'ы TextInput и кнопок с учётом scroll."""
        cr = self.content_rect()
        self._speed_buttons = []
        for (i, ti) in self.inputs:
            ry = cr.y + self._row_y(i) - self.scroll_y
            ti.set_rect((cr.x + 150, ry + 4, 150, 26))
            # кнопка скорости
            btn = pygame.Rect(cr.x + 310, ry + 4, 70, 26)
            self._speed_buttons.append((btn, i))

    def handle_event(self, event):
        # кнопка Сохранить (в футере)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._save_btn.collidepoint(event.pos):
                self._save_and_close()
                return True

        # перетаскивание/крестик/скролл-клик обрабатываем через базу,
        # но сначала — ввод текста и кнопки скорости
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._sync_positions()

            # клавиатура -> в активное поле
            if event.type == pygame.KEYDOWN:
                for _, ti in self.inputs:
                    if ti.active:
                        return ti.handle_event(event)
                # нет активного поля — не поглощаем (пусть ESC закроет окно)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return False
                return False

            # MOUSEBUTTONDOWN:
            if event.button == 1:
                # сначала крестик / титулбар через базовую логику (drag)
                if self.close_rect().collidepoint(event.pos):
                    self.close()
                    return True
                if self.titlebar_rect().collidepoint(event.pos):
                    self.dragging = True
                    self.drag_offset_x = event.pos[0] - self.x
                    self.drag_offset_y = event.pos[1] - self.y
                    return True
                # клики по полям ввода
                for _, ti in self.inputs:
                    if ti.handle_event(event):
                        return True
                # клики по кнопкам скорости
                for btn, i in self._speed_buttons:
                    if btn.collidepoint(event.pos):
                        toggle_port_speed(self.game, self.equip, i)
                        return True
                # клик внутри окна (но не по элементам) — снять фокус полей
                if self.contains(event.pos):
                    for _, ti in self.inputs:
                        ti.active = False
                    return True
                # клик вне окна — закрыть
                self.close()
                return True

        # движение мыши при drag / отпускание кнопки
        return super().handle_event(event)

    def _save_and_close(self):
        for i, ti in self.inputs:
            self.equip["ports"][i]["label"] = ti.text
        print(f"Подписи портов сохранены для {equip_type_label(self.equip)} "
              f"#{self.equip['id']}")
        self.close()

    def _render_content(self, surface, font, small_font):
        self._sync_positions()
        cr = self.content_rect()
        tiny = pygame.font.SysFont("arial,dejavusans", 12)
        for i, port in enumerate(self.equip["ports"]):
            ry = self._row_y(i) - self.scroll_y
            if ry + self.row_h < 0 or ry > surface.get_height():
                continue
            # номер порта
            num = font.render(f"{i + 1}", True, COLOR_TEXT)
            surface.blit(num, (10, ry + 8))
            # статус
            status, col = port_status_text_color(self.game, self.equip, i)
            st = tiny.render(status, True, col)
            surface.blit(st, (40, ry + 10))
            # TextInput рисуем на экране отдельно (нужны экранные координаты)
        # TextInput и кнопки скорости рисуем поверх в draw()

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        self._draw_content(screen, font, small_font)
        self._sync_positions()
        cr = self.content_rect()
        tiny = pygame.font.SysFont("arial,dejavusans", 12)

        # обрезаем поля/кнопки по области контента
        old_clip = screen.get_clip()
        screen.set_clip(cr)
        for (i, ti) in self.inputs:
            if cr.y - 30 <= ti.rect.y <= cr.bottom:
                ti.draw(screen, tiny)
        for btn, i in self._speed_buttons:
            if cr.y - 30 <= btn.y <= cr.bottom:
                port = self.equip["ports"][i]
                draw_button_screen(screen, tiny, btn, speed_label(port["speed"]))
        screen.set_clip(old_clip)

        # футер: кнопка Сохранить
        self._save_btn = pygame.Rect(self.x + self.width // 2 - 80,
                                     self.y + self.height - FOOTER_H + 6,
                                     160, 30)
        draw_button_screen(screen, small_font, self._save_btn, "💾 Сохранить")


# --------------------------------------------------------------------------
# Окно конфигурации роутера
# --------------------------------------------------------------------------
class RouterConfigWindow(SwitchConfigWindow):
    """Идентичен конфигу свитча — список портов с подписями."""
    def __init__(self, equip, screen_w, screen_h, game=None):
        super().__init__(equip, screen_w, screen_h, game=game)
        self.width = 400
        self.height = 300
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self.title = f"Config: Роутер #{equip['id']}"
        self._compute_content_height()


# --------------------------------------------------------------------------
# Окно ЦОД
# --------------------------------------------------------------------------
class DatacenterWindow(Window):
    UPLINK_SPEEDS = [100, 1000, 10000]
    UPLINK_LABELS = {100: "100 Мб", 1000: "1 Гб", 10000: "10 Гб"}

    def __init__(self, dc, screen_w, screen_h):
        w, h = 300, 200
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        super().__init__(x, y, w, h, f"ЦОД: {dc.get('name', 'DC')}")
        self.dc = dc
        self.uplink_index = 1
        self.ip_count = random.randint(1, 10)

    def _uplink_btn_rect(self):
        return pygame.Rect(self.x + 150, self.y + HEADER_H + 20, 130, 30)

    def _on_content_click(self, local_x, local_y):
        if self._uplink_btn_rect().collidepoint(local_x, local_y - self.scroll_y):
            self.uplink_index = (self.uplink_index + 1) % len(self.UPLINK_SPEEDS)

    def draw(self, screen, font, small_font):
        self._draw_frame(screen, font)
        lbl = small_font.render("Скорость аплинка:", True, COLOR_TEXT)
        screen.blit(lbl, (self.x + 14, self.y + HEADER_H + 25))
        btn = self._uplink_btn_rect()
        speed = self.UPLINK_SPEEDS[self.uplink_index]
        draw_button_screen(screen, small_font, btn, self.UPLINK_LABELS[speed])
        ip_lbl = small_font.render(f"IP-адресов: {self.ip_count}", True, COLOR_TEXT)
        screen.blit(ip_lbl, (self.x + 14, self.y + HEADER_H + 70))
        note = small_font.render("(демо-режим)", True, COLOR_TEXT_DIM)
        screen.blit(note, (self.x + 14, self.y + HEADER_H + 100))


# --------------------------------------------------------------------------
# Окно выбора порта (список устройств + прокрутка)
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
        return [i for i, p in enumerate(device["ports"]) if p["free"]]

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
        """True, если в активном окне есть поле ввода в фокусе."""
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

        # drag — отдаём все MOUSEMOTION
        if event.type == pygame.MOUSEMOTION and win.dragging:
            handled = win.handle_event(event)
            if win.is_closed:
                self.active_window = None
            return handled

        # прокрутка (но не когда поле ввода в фокусе и колесо — пусть скроллит окно)
        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if win.contains(mouse):
                win.scroll(event.y)
                return True
            return False

        handled = win.handle_event(event)
        if win.is_closed:
            self.active_window = None
        return handled

    def draw(self, screen, font, small_font):
        if self.active_window is not None and not self.active_window.is_closed:
            self.active_window.draw(screen, font, small_font)
            
            