#!/usr/bin/env python3
"""
main_menu.py - главное меню Telecom INC (точка входа).

Экраны (state):
  MAIN       - 3 пульсирующие кнопки: Играть / Настройки / Выход.
  PLAY_SETUP - ввод сида, генерация, старт игры, назад.
  SETTINGS   - переключение режима экрана, назад.
"""

import math
import random
import sys

import pygame

import map_generator
import visualizer
from ui import TextInput, _vgrad_rect

WINDOWED_SIZE = (1280, 720)
MAP_SIZE = 100

COLOR_BG_TOP = (24, 30, 44)
COLOR_BG_BOT = (10, 14, 22)
COLOR_TITLE = (120, 200, 255)
COLOR_TITLE_SHADOW = (20, 60, 100)
COLOR_TEXT = (235, 235, 240)
COLOR_TEXT_DIM = (160, 165, 180)

GREEN = (50, 200, 50)
BLUE = (50, 150, 250)
RED = (200, 50, 50)
GRAY = (90, 100, 120)


def random_seed_16():
    """16 цифр, первая не 0."""
    return str(random.randint(1, 9)) + "".join(
        str(random.randint(0, 9)) for _ in range(15))


def _vgrad_fullscreen(surface, top, bot):
    w, h = surface.get_size()
    for i in range(h):
        t = i / h
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, i), (w, i))


class MenuButton:
    """Пульсирующая кнопка меню."""
    def __init__(self, text, color, callback, big=False):
        self.text = text
        self.color = color
        self.callback = callback
        self.big = big
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._phase = random.uniform(0, math.pi * 2)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def handle_click(self, pos):
        if self.rect.collidepoint(pos):
            if self.callback is not None:
                self.callback()
            return True
        return False

    def draw(self, surface, font, t):
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)

        # пульсация: лёгкое "дыхание" яркости
        pulse = 0.5 + 0.5 * math.sin(t * 3.0 + self._phase)
        boost = int(30 * pulse) + (35 if hover else 0)

        top = tuple(min(255, c + boost + 20) for c in self.color)
        bot = tuple(max(0, c - 40) for c in self.color)
        _vgrad_rect(surface, self.rect, top, bot, radius=12)

        # обводка — усиливается при наведении + пульсе
        glow = int(120 + 100 * pulse)
        edge = (min(255, self.color[0] + glow),
                min(255, self.color[1] + glow),
                min(255, self.color[2] + glow))
        pygame.draw.rect(surface, edge, self.rect, 3 if hover else 2, border_radius=12)

        # блик сверху
        hi = pygame.Surface((self.rect.width, self.rect.height // 2), pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 45),
                         (0, 0, self.rect.width, self.rect.height // 2),
                         border_top_left_radius=12, border_top_right_radius=12)
        surface.blit(hi, (self.rect.x, self.rect.y))

        surf = font.render(self.text, True, COLOR_TEXT)
        surface.blit(surf, (self.rect.centerx - surf.get_width() // 2,
                            self.rect.centery - surf.get_height() // 2))


class SimpleButton:
    """Обычная кнопка (для PLAY_SETUP / SETTINGS)."""
    def __init__(self, text, callback, accent=BLUE):
        self.text = text
        self.callback = callback
        self.accent = accent
        self.rect = pygame.Rect(0, 0, 0, 0)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def handle_click(self, pos):
        if self.rect.collidepoint(pos):
            if self.callback is not None:
                self.callback()
            return True
        return False

    def draw(self, surface, font):
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)
        acc = self.accent
        if hover:
            top = tuple(min(255, c + 45) for c in acc)
            bot = tuple(max(0, c - 15) for c in acc)
            edge = (255, 255, 255)
        else:
            top = tuple(min(255, c + 15) for c in acc)
            bot = tuple(max(0, c - 45) for c in acc)
            edge = (200, 210, 225)
        _vgrad_rect(surface, self.rect, top, bot, radius=10)
        pygame.draw.rect(surface, edge, self.rect, 2 if hover else 1, border_radius=10)
        surf = font.render(self.text, True, COLOR_TEXT)
        surface.blit(surf, (self.rect.centerx - surf.get_width() // 2,
                            self.rect.centery - surf.get_height() // 2))


class MainMenu:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Telecom INC")
        self.fullscreen = False
        self.screen = self._make_screen()
        self.screen_w, self.screen_h = self.screen.get_size()

        names = "arial,dejavusans,liberationsans,freesans"
        self.font_title = pygame.font.SysFont(names, 64, bold=True)
        self.font_btn = pygame.font.SysFont(names, 28)
        self.font = pygame.font.SysFont(names, 22)
        self.font_small = pygame.font.SysFont(names, 18)

        self.state = "MAIN"
        self.clock = pygame.time.Clock()
        self.running = True
        self.time = 0.0

        # MAIN
        self.main_buttons = [
            MenuButton("Играть", GREEN, lambda: self._set_state("PLAY_SETUP"), big=True),
            MenuButton("Настройки", BLUE, lambda: self._set_state("SETTINGS"), big=True),
            MenuButton("Выход", RED, self._quit, big=True),
        ]

        # PLAY_SETUP
        self.seed_input = TextInput((0, 0, 420, 44),
                                    initial_text=random_seed_16(), max_length=16)
        self.btn_random = SimpleButton("🎲 Сгенерировать", self._gen_seed, accent=(80, 110, 160))
        self.btn_start = SimpleButton("▶ Начать игру", self._start_game, accent=GREEN)
        self.btn_back_play = SimpleButton("← Назад", lambda: self._set_state("MAIN"),
                                          accent=GRAY)

        # SETTINGS
        self.btn_mode = SimpleButton(self._mode_text(), self._toggle_fullscreen,
                                     accent=BLUE)
        self.btn_back_settings = SimpleButton("← Назад", lambda: self._set_state("MAIN"),
                                              accent=GRAY)

    # ---- служебное ----
    def _make_screen(self):
        if self.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode(WINDOWED_SIZE)

    def _mode_text(self):
        return "Режим: Полный экран" if self.fullscreen else "Режим: Оконный"

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.screen = self._make_screen()
        self.screen_w, self.screen_h = self.screen.get_size()
        self.btn_mode.text = self._mode_text()

    def _set_state(self, state):
        self.state = state
        self.seed_input.active = False

    def _quit(self):
        pygame.quit()
        sys.exit(0)

    def _gen_seed(self):
        self.seed_input.text = random_seed_16()
        self.seed_input.cursor_pos = len(self.seed_input.text)
        self.seed_input.active = False

    def _parse_seed(self):
        txt = self.seed_input.text.strip()
        if not txt:
            txt = random_seed_16()
            self.seed_input.text = txt
            self.seed_input.cursor_pos = len(txt)
        try:
            return int(txt)
        except ValueError:
            return abs(hash(txt)) % (10 ** 16)

    def _start_game(self):
        seed = self._parse_seed()
        print(f"Генерация карты: seed={seed}, size={MAP_SIZE}")
        try:
            data = map_generator.generate(seed, MAP_SIZE)
        except RuntimeError as e:
            print(f"Ошибка генерации: {e}. Пробуем другой сид.")
            seed = int(random_seed_16())
            data = map_generator.generate(seed, MAP_SIZE)
            self.seed_input.text = str(seed)
            self.seed_input.cursor_pos = len(self.seed_input.text)

        print("Запуск игры...")
        result = visualizer.run_game(data, self.screen, self.screen_w, self.screen_h)

        pygame.display.set_caption("Telecom INC")
        self.screen = self._make_screen()
        self.screen_w, self.screen_h = self.screen.get_size()
        if result == "quit":
            self._quit()
        print("Возврат в главное меню.")
        self.state = "MAIN"

    # ---- раскладка ----
    def _layout_main(self):
        cx = self.screen_w // 2
        bw, bh, gap = 320, 64, 24
        y = int(self.screen_h * 0.42)
        for b in self.main_buttons:
            b.set_rect((cx - bw // 2, y, bw, bh))
            y += bh + gap

    def _layout_play(self):
        cx = self.screen_w // 2
        col_w = 420
        col_x = cx - col_w // 2
        y = int(self.screen_h * 0.32)
        self.seed_input.set_rect((col_x, y, col_w, 44))
        y += 64
        self.btn_random.set_rect((col_x, y, col_w, 44))
        y += 70
        self.btn_start.set_rect((col_x, y, col_w, 56))
        y += 76
        self.btn_back_play.set_rect((col_x + col_w // 2 - 90, y, 180, 44))

    def _layout_settings(self):
        cx = self.screen_w // 2
        col_w = 420
        col_x = cx - col_w // 2
        y = int(self.screen_h * 0.38)
        self.btn_mode.set_rect((col_x, y, col_w, 54))
        y += 80
        self.btn_back_settings.set_rect((col_x + col_w // 2 - 90, y, 180, 44))

# ---- события ----
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._quit()
            return

        if self.state == "PLAY_SETUP":
            if self.seed_input.handle_event(event, self.font):
                return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.state == "MAIN":
                self._quit()
            else:
                self._set_state("MAIN")
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == "MAIN":
                self._layout_main()
                for b in self.main_buttons:
                    if b.handle_click(event.pos):
                        return
            elif self.state == "PLAY_SETUP":
                self._layout_play()
                for b in (self.btn_random, self.btn_start, self.btn_back_play):
                    if b.handle_click(event.pos):
                        return
            elif self.state == "SETTINGS":
                self._layout_settings()
                for b in (self.btn_mode, self.btn_back_settings):
                    if b.handle_click(event.pos):
                        return

        if event.type == pygame.KEYDOWN and self.state == "PLAY_SETUP":
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start_game()

    # ---- отрисовка ----
    def _draw_title(self):
        title = self.font_title.render("TELECOM INC", True, COLOR_TITLE)
        shadow = self.font_title.render("TELECOM INC", True, COLOR_TITLE_SHADOW)
        tx = self.screen_w // 2 - title.get_width() // 2
        ty = int(self.screen_h * 0.12)
        self.screen.blit(shadow, (tx + 3, ty + 3))
        self.screen.blit(title, (tx, ty))
        sub = self.font_small.render("Симулятор интернет-провайдера",
                                     True, COLOR_TEXT_DIM)
        self.screen.blit(sub, (self.screen_w // 2 - sub.get_width() // 2, ty + 74))

    def draw(self):
        _vgrad_fullscreen(self.screen, COLOR_BG_TOP, COLOR_BG_BOT)
        self._draw_title()

        if self.state == "MAIN":
            self._layout_main()
            for b in self.main_buttons:
                b.draw(self.screen, self.font_btn, self.time)

        elif self.state == "PLAY_SETUP":
            self._layout_play()
            lbl = self.font_small.render("Сид карты (16 цифр):", True, COLOR_TEXT)
            self.screen.blit(lbl, (self.seed_input.rect.x,
                                   self.seed_input.rect.y - 26))
            self.seed_input.draw(self.screen, self.font)
            self.btn_random.draw(self.screen, self.font)
            self.btn_start.draw(self.screen, self.font_btn)
            self.btn_back_play.draw(self.screen, self.font)
            hint = self.font_small.render("Enter — начать, Esc — назад",
                                          True, COLOR_TEXT_DIM)
            self.screen.blit(hint, (self.screen_w // 2 - hint.get_width() // 2,
                                    self.screen_h - 44))

        elif self.state == "SETTINGS":
            self._layout_settings()
            lbl = self.font.render("Настройки", True, COLOR_TEXT)
            self.screen.blit(lbl, (self.screen_w // 2 - lbl.get_width() // 2,
                                   int(self.screen_h * 0.30)))
            self.btn_mode.draw(self.screen, self.font)
            self.btn_back_settings.draw(self.screen, self.font)

        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.time += dt
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
        pygame.quit()
        sys.exit(0)


def main():
    MainMenu().run()


if __name__ == "__main__":
    main()
    
    