# gui/menu.py
#
# Hlavné menu. Od reworku rozlíšení (krok 4, claude/11_RESOLUTION_REWORK_
# ANALYSIS.md) kreslí cez gui/canvas.py — v logických súradniciach
# (1920×1080/1200, rovnaké čísla ako predtým), ale priamo v natívnom
# rozlíšení okna: ostrý text aj karty na 4K, pozadie stola aj v pásmach
# pri 21:9.
#
# Všetko okrem tlačidiel (pozadie, stmavenie, karty, logo) sa kreslí raz
# do statickej vrstvy (gui/canvas.py::StaticLayer) — každú snímku sa len
# blitne a navrch sa nakreslia tlačidlá s hoverom. Predtým sa pri každej
# snímke alokovali dva povrchy cez celú obrazovku (pri 4K ~10 ms).

import pygame
import sys
import random
import os
from gui import display
from gui.canvas import StaticLayer
from config import (
    SCREEN_WIDTH,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS,
    CARD_SIZE_MEDIUM,
    SUITS, RANKS,
)

BG_PATH = os.path.join("assets", "graphics", "table.jpg")
LOGO_PATH = os.path.join("assets", "graphics", "chuj_logo.png")
LOGO_W = 500


class Menu:
    def __init__(self, screen: pygame.Surface, show_continue: bool = False):
        # `screen` (logický povrch) sa už nepoužíva — kreslí sa cez Canvas
        # nad oknom. Parameter ostáva kvôli volajúcim (main.py).
        self.screen = screen
        self.canvas = display.canvas()
        self.clock = pygame.time.Clock()
        self.show_continue = show_continue

        self.font_button = self.canvas.font(FONT_SIZE_LARGE)
        self.font_medium = self.canvas.font(FONT_SIZE_MEDIUM)

        self.has_bg = os.path.exists(BG_PATH)

        try:
            raw = pygame.image.load(LOGO_PATH)
            logo_h = int(LOGO_W * (raw.get_height() / raw.get_width()))
            self.logo = self.canvas.image(LOGO_PATH, (LOGO_W, logo_h))
        except (FileNotFoundError, pygame.error):
            self.logo = None

        self.bg_cards = self._generate_bg_cards()
        self._layer: StaticLayer | None = None

        btn_w = 300
        btn_h = 65
        center_x = SCREEN_WIDTH // 2

        buttons_data = []
        if show_continue:
            buttons_data.append(("Pokračovať", "continue", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Nová hra", "new_game", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Tutoriál", "tutorial", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Profil", "profile", COLOR_BUTTON_SECONDARY))
        buttons_data.append(("Nastavenia", "settings", COLOR_BUTTON_SECONDARY))
        buttons_data.append(("Koniec", "quit", COLOR_BUTTON_SECONDARY))

        start_y = 420
        # Po pribudnutí tlačidiel "Profil" a "Tutoriál" je v menu až 6
        # položiek — na nižšom rozlíšení by posledná vypadla pod okraj,
        # preto blok v takom prípade posunieme nahor. Na 1080p sa nič
        # nemení. (Od reworku rozlíšení je logická výška vždy ≥ 1080,
        # takže sa to v praxi neuplatní — poistka ostáva.)
        last_bottom = start_y + (len(buttons_data) - 1) * 85 + btn_h
        if last_bottom > display.logical_height() - 40:
            start_y -= last_bottom - (display.logical_height() - 40)

        self.buttons = []
        for i, (label, action, color) in enumerate(buttons_data):
            self.buttons.append({
                "label": label,
                "action": action,
                "rect": pygame.Rect(
                    center_x - btn_w // 2,
                    start_y + i * 85,
                    btn_w, btn_h
                ),
                "color": color,
                "hover": False
            })

    def _generate_bg_cards(self) -> list[dict]:
        """Vygeneruje náhodné karty pre pozadie.

        Poradie volaní random je rovnaké ako pred reworkom (výber kariet,
        uhol, pozícia), takže pri rovnakom seede vznikne to isté menu."""
        cards = []
        used_positions = []
        card_names = [
            f"{suit}-{rank}.png"
            for suit in SUITS for rank in RANKS
        ]
        selected = random.sample(card_names, 12)
        w, h = CARD_SIZE_MEDIUM
        size = (int(w * 0.8), int(h * 0.8))

        for filename in selected:
            try:
                angle = random.uniform(-35, 35)
                img = self.canvas.card(filename, angle=angle, lsize=size).copy()

                attempts = 0
                x, y = 0, 0
                while attempts < 20:
                    x = random.randint(50, SCREEN_WIDTH - 200)
                    y = random.randint(50, display.logical_height() - 200)
                    cx, cy = SCREEN_WIDTH // 2, display.logical_height() // 2
                    if abs(x - cx) < 350 and abs(y - cy) < 300:
                        attempts += 1
                        continue
                    too_close = any(
                        abs(x - p[0]) < 120 and abs(y - p[1]) < 160
                        for p in used_positions
                    )
                    if too_close:
                        attempts += 1
                        continue
                    used_positions.append((x, y))
                    break

                img.set_alpha(240)
                cards.append({"image": img, "x": x, "y": y})
            except (FileNotFoundError, pygame.error):
                continue

        return cards

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = display.mouse_pos()

            for event in display.get_events():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        action = self._handle_click(event.pos)
                        if action:
                            return action

            self._update_hover(mouse_pos)
            self._draw()
            display.present()

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                return btn["action"]
        return None

    def _update_hover(self, mouse_pos: tuple[int, int]):
        for btn in self.buttons:
            btn["hover"] = btn["rect"].collidepoint(mouse_pos)

    def _draw(self):
        c = self.canvas
        if self._layer is None:
            self._layer = StaticLayer(c.target.get_size())
        if self._layer.needs_redraw("static"):
            with self._layer.drawing(c, key="static"):
                self._draw_static()
        self._layer.blit_to(c.target)
        self._draw_buttons()

    def _draw_static(self):
        """Pozadie, stmavenie, karty a logo — nemenia sa medzi snímkami."""
        c = self.canvas
        if self.has_bg:
            c.target.blit(c.background(BG_PATH, c.target.get_size()), (0, 0))
        else:
            c.fill_window((45, 28, 15))

        c.overlay_window((0, 0, 0, 130))

        for card in self.bg_cards:
            c.blit(card["image"], (card["x"], card["y"]))

        overlay_w = max(500, (self.logo.get_width() if self.logo else 0) + 60)
        c.overlay((SCREEN_WIDTH // 2 - overlay_w // 2, 0, overlay_w, display.logical_height()),
                  (0, 0, 0, 140))

        self._draw_logo()

    def _draw_logo(self):
        c = self.canvas
        logo_bottom_padding = 60
        first_btn_y = self.buttons[0]["rect"].top

        if self.logo:
            logo_rect = self.logo.get_rect(
                centerx=SCREEN_WIDTH // 2,
                bottom=first_btn_y - logo_bottom_padding
            )

            # Tmavý podklad pod logo
            pad = 20
            bg_rect = pygame.Rect(
                logo_rect.x - pad, logo_rect.y - pad,
                logo_rect.width + pad * 2, logo_rect.height + pad * 2
            )
            c.overlay(bg_rect, (0, 0, 0, 160))

            c.blit(self.logo, logo_rect)
        else:
            font_title = c.font(120)
            shadow = font_title.render("CHUJ", True, (0, 0, 0))
            title = font_title.render("CHUJ", True, COLOR_GOLD)
            rect = title.get_rect(
                centerx=SCREEN_WIDTH // 2,
                bottom=first_btn_y - logo_bottom_padding
            )
            c.blit(shadow, (rect.x + 3, rect.y + 3))
            c.blit(title, rect)

    def _draw_buttons(self):
        for btn in self.buttons:
            self._draw_button(btn)

    def _draw_button(self, btn: dict):
        c = self.canvas
        rect = btn["rect"]
        color = btn["color"]
        alpha = 240 if btn["hover"] else 200

        c.overlay(rect, (*color, alpha))

        if btn["hover"]:
            c.overlay(rect, (255, 255, 255, 25))

        border_color = COLOR_GOLD if btn["hover"] else COLOR_GRAY
        c.rect(border_color, rect, width=2, border_radius=BUTTON_RADIUS)

        text_color = COLOR_GOLD if btn["hover"] else COLOR_WHITE
        text_surf = self.font_button.render(btn["label"], True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        c.blit(text_surf, text_rect)

    def __repr__(self) -> str:
        return "Menu()"
