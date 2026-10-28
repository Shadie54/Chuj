# gui/tutorial_menu.py
#
# Podmenu "Tutoriál" — výber kapitoly. Zoznam kapitol (ich id a poradie)
# dostáva zvonku (main.py, z tutorial_main.py::CHAPTERS), aby to ostalo
# jediné miesto pravdy — tu sa id iba prekladajú na zobrazované mená
# (CHAPTER_LABELS). Vizuálne kopíruje gui/menu.py (rovnaké farby, rovnaký
# štýl tlačidiel), aby pôsobilo ako súčasť tej istej obrazovky.
#
# Od reworku rozlíšení (krok 4) kreslí rovnako ako gui/menu.py cez
# gui/canvas.py — natívne rozlíšenie, statická vrstva, tlačidlá navrch.
# Vzhľad (grafický rework 2026-10-27): gui/ui_style.py — kapitoly sú
# tlačidlá úrovne 2, Späť úrovne 3.

import pygame
import sys
from gui import display
from gui.canvas import StaticLayer
from gui import ui_style
from config import (
    SCREEN_WIDTH,
    FONT_SIZE_LARGE,
)

BTN_W, BTN_H, BTN_GAP = 380, 60, 16

CHAPTER_LABELS = {
    "zaklady": "Základy",
    "zavazky": "Záväzky a pravidlá",
    "trening": "Tréningová hra",
}


class TutorialMenu:
    """Výber kapitoly tutoriálu.

    run() vráti buď id zvolenej kapitoly (napr. "zaklady"), alebo "back"
    (návrat do hlavného menu bez spustenia kapitoly).
    """

    def __init__(self, screen: pygame.Surface, chapter_ids: list[str]):
        # `screen` (logický povrch) sa nepoužíva — kreslí sa cez Canvas.
        self.screen = screen
        self.canvas = display.canvas()
        self.clock = pygame.time.Clock()

        self.font_button = self.canvas.font(FONT_SIZE_LARGE)
        self.font_title = self.canvas.font(60)

        self._layer: StaticLayer | None = None

        btn_w, btn_h = BTN_W, BTN_H
        step = BTN_H + BTN_GAP
        center_x = SCREEN_WIDTH // 2

        buttons_data = [
            (CHAPTER_LABELS.get(cid, cid), cid, 2)
            for cid in chapter_ids
        ]
        buttons_data.append(("Späť", "back", 3))

        # Nadpis + tlačidlá zvislo na strede (aj pri 16:10).
        block_h = 140 + len(buttons_data) * step - BTN_GAP
        start_y = (display.logical_height() - block_h) // 2 + 140
        # Rovnaký ochranný posun ako v gui/menu.py — na nižšom rozlíšení by
        # posledné tlačidlo vypadlo pod okraj.
        last_bottom = start_y + (len(buttons_data) - 1) * step + btn_h
        if last_bottom > display.logical_height() - 40:
            start_y -= last_bottom - (display.logical_height() - 40)

        self.buttons = []
        for i, (label, action, tier) in enumerate(buttons_data):
            self.buttons.append({
                "label": label,
                "action": action,
                "rect": pygame.Rect(
                    center_x - btn_w // 2,
                    start_y + i * step,
                    btn_w, btn_h
                ),
                "tier": tier,
                "hover": False
            })

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
                ui_style.draw_backdrop(c)
                self._draw_title()
        self._layer.blit_to(c.target)
        for btn in self.buttons:
            self._draw_button(btn)

    def _draw_title(self):
        first_btn_y = self.buttons[0]["rect"].top
        ui_style.draw_screen_title(
            self.canvas, "TUTORIÁL", self.font_title,
            (SCREEN_WIDTH // 2, first_btn_y - 100), line_half_w=220)

    def _draw_button(self, btn: dict):
        ui_style.draw_button(self.canvas, btn["rect"], btn["label"],
                             self.font_button, btn["tier"], btn["hover"])

    def __repr__(self) -> str:
        return "TutorialMenu()"
